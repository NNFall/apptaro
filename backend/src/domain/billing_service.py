from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Literal

from src.domain.billing_plans import BillingPlan, get_plan, list_plans
from src.integrations.yookassa_gateway import YooKassaGateway, YooKassaPaymentInfo
from src.repositories import billing as billing_repo


PaymentStatus = Literal['pending', 'paid', 'canceled', 'failed', 'succeeded']


@dataclass(frozen=True)
class BillingSummary:
    client_id: str
    plans: list[BillingPlan]
    support_username: str
    offer_url: str
    test_mode: bool
    active_subscription: billing_repo.StoredSubscription | None
    latest_valid_subscription: billing_repo.StoredSubscription | None


@dataclass(frozen=True)
class BillingPaymentResult:
    payment_id: str
    plan: BillingPlan
    status: str
    confirmation_url: str | None
    test_mode: bool
    summary: BillingSummary


class BillingService:
    def __init__(
        self,
        *,
        gateway: YooKassaGateway,
        offer_url: str,
        support_username: str,
        return_url: str,
        test_mode: bool,
    ) -> None:
        self._gateway = gateway
        self._offer_url = offer_url
        self._support_username = support_username
        self._return_url = return_url
        self._test_mode = test_mode

    @property
    def is_configured(self) -> bool:
        return self._gateway.is_configured

    async def get_summary(self, client_id: str) -> BillingSummary:
        billing_repo.touch_client(client_id)
        active = billing_repo.get_active_subscription(client_id)
        latest = active or billing_repo.get_latest_valid_subscription(client_id)
        return BillingSummary(
            client_id=client_id,
            plans=list_plans(),
            support_username=self._support_username,
            offer_url=self._offer_url,
            test_mode=self._test_mode,
            active_subscription=active,
            latest_valid_subscription=latest,
        )

    async def can_start_generation(self, client_id: str) -> bool:
        billing_repo.touch_client(client_id)
        return billing_repo.get_subscription_for_use(client_id) is not None

    async def consume_generation(self, client_id: str) -> bool:
        return billing_repo.decrement_subscription(client_id)

    async def create_payment(
        self,
        *,
        client_id: str,
        plan_key: str,
        context: str = 'new',
    ) -> BillingPaymentResult:
        if not self.is_configured:
            raise RuntimeError('YooKassa is not configured')

        billing_repo.touch_client(client_id)
        plan = get_plan(plan_key)

        if context == 'renew' and plan.recurring:
            active = billing_repo.get_active_subscription(client_id)
            if active and active.provider == 'yookassa' and active.payment_method_id:
                payment = await asyncio.to_thread(
                    self._gateway.create_recurring_payment,
                    plan=plan,
                    client_id=client_id,
                    payment_method_id=active.payment_method_id,
                )
                billing_repo.create_payment(
                    client_id=client_id,
                    provider='yookassa',
                    amount=plan.price_rub,
                    currency='RUB',
                    plan_key=plan.key,
                    external_payment_id=payment.payment_id,
                    status='paid' if payment.status == 'succeeded' else payment.status,
                    payment_method_id=payment.payment_method_id,
                    confirmation_url=payment.confirmation_url,
                )
                if payment.status == 'succeeded':
                    billing_repo.renew_subscription(active.id, plan.key, plan.limit, plan.days)
                summary = await self.get_summary(client_id)
                return BillingPaymentResult(
                    payment_id=payment.payment_id,
                    plan=plan,
                    status='paid' if payment.status == 'succeeded' else payment.status,
                    confirmation_url=payment.confirmation_url,
                    test_mode=self._test_mode,
                    summary=summary,
                )

        payment = await asyncio.to_thread(
            self._gateway.create_redirect_payment,
            plan=plan,
            client_id=client_id,
            return_url=self._return_url or self._offer_url,
            save_payment_method=plan.recurring,
        )
        billing_repo.create_payment(
            client_id=client_id,
            provider='yookassa',
            amount=plan.price_rub,
            currency='RUB',
            plan_key=plan.key,
            external_payment_id=payment.payment_id,
            status='pending',
            confirmation_url=payment.confirmation_url,
        )
        summary = await self.get_summary(client_id)
        return BillingPaymentResult(
            payment_id=payment.payment_id,
            plan=plan,
            status='pending',
            confirmation_url=payment.confirmation_url,
            test_mode=self._test_mode,
            summary=summary,
        )

    async def sync_payment(self, *, client_id: str, payment_id: str) -> BillingPaymentResult:
        payment = billing_repo.get_payment(payment_id)
        if payment is None or payment.client_id != client_id:
            raise LookupError('Payment not found')

        plan = get_plan(payment.plan_key)
        if payment.status not in {'pending', 'waiting_for_capture'}:
            summary = await self.get_summary(client_id)
            return BillingPaymentResult(
                payment_id=payment.external_payment_id,
                plan=plan,
                status=payment.status,
                confirmation_url=payment.confirmation_url,
                test_mode=self._test_mode,
                summary=summary,
            )

        remote = await asyncio.to_thread(self._gateway.get_payment, payment.external_payment_id)
        if remote is None:
            summary = await self.get_summary(client_id)
            return BillingPaymentResult(
                payment_id=payment.external_payment_id,
                plan=plan,
                status='pending',
                confirmation_url=payment.confirmation_url,
                test_mode=self._test_mode,
                summary=summary,
            )

        status = await self._apply_remote_payment(client_id, payment.plan_key, remote)
        stored = billing_repo.get_payment(payment.external_payment_id) or payment
        summary = await self.get_summary(client_id)
        return BillingPaymentResult(
            payment_id=stored.external_payment_id,
            plan=plan,
            status=status,
            confirmation_url=stored.confirmation_url,
            test_mode=self._test_mode,
            summary=summary,
        )

    async def cancel_subscription(self, client_id: str) -> BillingSummary:
        billing_repo.cancel_subscription(client_id)
        return await self.get_summary(client_id)

    async def process_due_auto_renewals_once(self) -> int:
        if not self.is_configured:
            return 0

        processed = 0
        for subscription in billing_repo.get_due_auto_renew_subscriptions():
            plan = get_plan(subscription.plan_key)
            payment_method_id = (subscription.payment_method_id or '').strip()
            if not payment_method_id:
                billing_repo.expire_subscription(subscription.id)
                processed += 1
                continue

            try:
                remote = await asyncio.to_thread(
                    self._gateway.create_recurring_payment,
                    plan=plan,
                    client_id=subscription.client_id,
                    payment_method_id=payment_method_id,
                )
            except Exception:  # noqa: BLE001
                billing_repo.postpone_autorenew_attempt(subscription.id, days=1)
                processed += 1
                continue

            billing_repo.create_payment(
                client_id=subscription.client_id,
                provider='yookassa',
                amount=plan.price_rub,
                currency='RUB',
                plan_key=plan.key,
                external_payment_id=remote.payment_id,
                status='paid' if remote.status == 'succeeded' else remote.status,
                payment_method_id=remote.payment_method_id or payment_method_id,
                confirmation_url=remote.confirmation_url,
            )
            if remote.status == 'succeeded':
                billing_repo.renew_subscription(
                    subscription.id,
                    plan.key,
                    plan.limit,
                    plan.days,
                )
            elif remote.status == 'canceled':
                billing_repo.postpone_autorenew_attempt(subscription.id, days=1)
            else:
                billing_repo.postpone_autorenew_attempt(subscription.id, days=1)
            processed += 1

        return processed

    async def _apply_remote_payment(
        self,
        client_id: str,
        plan_key: str,
        remote: YooKassaPaymentInfo,
    ) -> str:
        plan = get_plan(plan_key)
        if remote.status == 'succeeded':
            auto_renew = 1 if plan.recurring and remote.payment_method_id else 0
            billing_repo.create_subscription(
                client_id=client_id,
                plan_key=plan.key,
                limit=plan.limit,
                days=plan.days,
                provider='yookassa',
                auto_renew=auto_renew,
                payment_method_id=remote.payment_method_id,
            )
            billing_repo.update_payment_status(
                remote.payment_id,
                'paid',
                payment_method_id=remote.payment_method_id,
                confirmation_url=remote.confirmation_url,
            )
            return 'paid'
        if remote.status == 'canceled':
            billing_repo.update_payment_status(
                remote.payment_id,
                'canceled',
                payment_method_id=remote.payment_method_id,
                confirmation_url=remote.confirmation_url,
            )
            return 'canceled'

        billing_repo.update_payment_status(
            remote.payment_id,
            remote.status,
            payment_method_id=remote.payment_method_id,
            confirmation_url=remote.confirmation_url,
        )
        return remote.status
