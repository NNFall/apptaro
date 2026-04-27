from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from yookassa import Configuration, Payment

from src.domain.billing_plans import BillingPlan


@dataclass(frozen=True)
class YooKassaPaymentInfo:
    payment_id: str
    status: str
    confirmation_url: str | None
    payment_method_id: str | None


class YooKassaGateway:
    def __init__(
        self,
        *,
        shop_id: str,
        secret_key: str,
        return_url: str,
        receipt_email: str,
        receipt_phone: str,
        tax_system_code: int,
        vat_code: int,
        item_name: str,
        payment_subject: str,
        payment_mode: str,
    ) -> None:
        self._shop_id = shop_id.strip()
        self._secret_key = secret_key.strip()
        self._return_url = return_url.strip()
        self._receipt_email = receipt_email.strip()
        self._receipt_phone = receipt_phone.strip()
        self._tax_system_code = tax_system_code
        self._vat_code = vat_code
        self._item_name = item_name.strip() or 'Подписка на генерации AppSlides'
        self._payment_subject = payment_subject or 'service'
        self._payment_mode = payment_mode or 'full_prepayment'

    @property
    def is_configured(self) -> bool:
        return bool(self._shop_id and self._secret_key)

    def create_redirect_payment(
        self,
        *,
        plan: BillingPlan,
        client_id: str,
        return_url: str | None = None,
        save_payment_method: bool = True,
    ) -> YooKassaPaymentInfo:
        payload: dict[str, Any] = {
            'amount': {'value': f'{plan.price_rub:.2f}', 'currency': 'RUB'},
            'confirmation': {
                'type': 'redirect',
                'return_url': return_url or self._return_url or 'https://yookassa.ru',
            },
            'capture': True,
            'description': f'Подписка {plan.title}',
            'metadata': {'client_id': client_id, 'plan_key': plan.key},
        }
        receipt = self._build_receipt(plan.price_rub, f'{self._item_name}: {plan.title}')
        if receipt:
            payload['receipt'] = receipt
        if save_payment_method:
            payload['save_payment_method'] = True
        payment = self._payment_create(payload)
        return self._to_payment_info(payment)

    def create_recurring_payment(
        self,
        *,
        plan: BillingPlan,
        client_id: str,
        payment_method_id: str,
    ) -> YooKassaPaymentInfo:
        payload: dict[str, Any] = {
            'amount': {'value': f'{plan.price_rub:.2f}', 'currency': 'RUB'},
            'capture': True,
            'description': f'Подписка {plan.title} - продление',
            'metadata': {
                'client_id': client_id,
                'plan_key': plan.key,
                'type': 'auto_renew',
            },
            'payment_method_id': payment_method_id,
        }
        receipt = self._build_receipt(plan.price_rub, f'{self._item_name}: {plan.title}')
        if receipt:
            payload['receipt'] = receipt
        payment = self._payment_create(payload)
        return self._to_payment_info(payment)

    def get_payment(self, payment_id: str) -> YooKassaPaymentInfo | None:
        self._configure()
        payment = Payment.find_one(payment_id)
        if payment is None:
            return None
        return self._to_payment_info(payment)

    def _payment_create(self, payload: dict[str, Any]):
        self._configure()
        idempotence_key = str(uuid.uuid4())
        return Payment.create(payload, idempotence_key)

    def _configure(self) -> None:
        if not self.is_configured:
            raise RuntimeError('YooKassa is not configured')
        Configuration.account_id = self._shop_id
        Configuration.secret_key = self._secret_key

    def _build_receipt(self, amount_rub: int, description: str) -> dict[str, Any] | None:
        customer: dict[str, str] = {}
        if self._receipt_email:
            customer['email'] = self._receipt_email
        if self._receipt_phone:
            customer['phone'] = self._receipt_phone
        if not customer:
            return None
        return {
            'customer': customer,
            'tax_system_code': self._tax_system_code,
            'items': [
                {
                    'description': description[:128],
                    'quantity': '1.00',
                    'amount': {'value': f'{amount_rub:.2f}', 'currency': 'RUB'},
                    'vat_code': self._vat_code,
                    'payment_subject': self._payment_subject,
                    'payment_mode': self._payment_mode,
                }
            ],
        }

    @staticmethod
    def _to_payment_info(payment) -> YooKassaPaymentInfo:
        confirmation = getattr(payment, 'confirmation', None)
        payment_method = getattr(payment, 'payment_method', None)
        return YooKassaPaymentInfo(
            payment_id=str(getattr(payment, 'id', '')),
            status=str(getattr(payment, 'status', 'pending') or 'pending'),
            confirmation_url=getattr(confirmation, 'confirmation_url', None),
            payment_method_id=getattr(payment_method, 'id', None),
        )
