from __future__ import annotations

import asyncio

from src.domain.billing_plans import get_plan_by_store_product_id
from src.domain.billing_service import BillingService, BillingSummary
from src.integrations.admin_notifier import AdminNotifier
from src.integrations.app_store_gateway import (
    AppStoreGateway,
    VerifiedAppStoreNotification,
    VerifiedAppStoreTransaction,
)
from src.repositories.app_store_billing import (
    AppStoreBillingRepository,
    ProcessNotificationResult,
    VerifiedAppStoreTransaction as StoredAppStoreTransaction,
)


class AppStoreBillingService:
    def __init__(
        self,
        *,
        repository: AppStoreBillingRepository,
        gateway: AppStoreGateway | None,
        billing_service: BillingService,
    ) -> None:
        self._repository = repository
        self._gateway = gateway
        self._billing_service = billing_service

    def get_or_create_account_token(self, client_id: str) -> str:
        return self._repository.get_or_create_app_account_token(client_id)

    async def verify_transaction(
        self,
        *,
        client_id: str,
        transaction_id: str,
        product_id: str,
        operation: str,
        client_signed_data: str,
    ) -> BillingSummary:
        if self._gateway is None:
            raise RuntimeError('App Store verification is not configured')
        if not client_signed_data.strip():
            raise ValueError('client signed data is required')

        verified = await asyncio.to_thread(
            self._gateway.get_verified_transaction,
            transaction_id,
        )
        client_verified = await asyncio.to_thread(
            self._gateway.verify_signed_transaction,
            client_signed_data,
            expected_environment=verified.environment,
            requested_transaction_id=verified.transaction_id,
        )
        if client_verified.product_id != verified.product_id:
            raise ValueError('Client-signed Apple product does not match server verification')
        if _normalized_token(client_verified.app_account_token) != _normalized_token(
            verified.app_account_token
        ):
            raise ValueError('Client-signed Apple app account token does not match server verification')
        if verified.product_id != product_id.strip():
            raise ValueError('Apple product does not match the requested product')
        plan = get_plan_by_store_product_id(verified.product_id)
        account_token = self._repository.get_or_create_app_account_token(client_id)
        stored = self._stored_transaction(
            verified,
            client_id=client_id,
            app_account_token=account_token,
            readings=plan.limit,
            recurring=plan.recurring,
        )

        if operation == 'purchase':
            if (verified.app_account_token or '').strip().lower() != account_token.lower():
                raise ValueError('Apple purchase belongs to another app account')
            self._repository.apply_verified_transaction(stored)
        elif operation == 'restore':
            if not plan.recurring:
                raise ValueError('Consumable purchases cannot be restored')
            signed_token = (verified.app_account_token or '').strip()
            owner_client = self._repository.subscription_owner(
                verified.original_transaction_id
            ) or self._repository.client_id_for_app_account_token(signed_token)
            stored = self._stored_transaction(
                verified,
                client_id=owner_client or client_id,
                app_account_token=signed_token,
                readings=plan.limit,
                recurring=True,
            )
            self._repository.restore_subscription_chain(
                transaction=stored,
                target_client_id=client_id,
                target_app_account_token=account_token,
            )
        else:  # pragma: no cover - schema enforces this
            raise ValueError('Unsupported App Store operation')
        return await self._billing_service.get_summary(client_id)

    async def process_notification(self, signed_payload: str) -> ProcessNotificationResult:
        if self._gateway is None:
            raise RuntimeError('App Store verification is not configured')
        verified = await asyncio.to_thread(
            self._gateway.verify_notification,
            signed_payload,
        )
        return await asyncio.to_thread(self._persist_notification, verified)

    def _persist_notification(
        self,
        notification: VerifiedAppStoreNotification,
    ) -> ProcessNotificationResult:
        transaction = notification.transaction
        renewal = notification.renewal_info
        original_transaction_id = (
            transaction.original_transaction_id
            if transaction is not None
            else renewal.original_transaction_id if renewal is not None else None
        )
        transaction_id = transaction.transaction_id if transaction is not None else None
        notification_type = notification.notification_type
        subtype = notification.subtype

        lifecycle_action = 'none'
        admin_type: str | None = None
        stored_transaction: StoredAppStoreTransaction | None = None
        if notification_type in {'SUBSCRIBED', 'ONE_TIME_CHARGE', 'DID_RENEW'}:
            if transaction is None:
                raise ValueError('Apple purchase notification is missing transaction data')
            plan = get_plan_by_store_product_id(transaction.product_id)
            client_id = self._client_for_notification(transaction)
            account_token = (
                transaction.app_account_token
                or self._repository.get_or_create_app_account_token(client_id)
            )
            stored_transaction = self._stored_transaction(
                transaction,
                client_id=client_id,
                app_account_token=account_token,
                readings=plan.limit,
                recurring=plan.recurring,
            )
            lifecycle_action = 'grant'
            admin_type = 'renewal' if notification_type == 'DID_RENEW' else 'purchase'
        elif notification_type in {'EXPIRED', 'GRACE_PERIOD_EXPIRED'}:
            lifecycle_action = 'expire'
            admin_type = 'expiration'
        elif notification_type == 'DID_FAIL_TO_RENEW':
            if subtype == 'GRACE_PERIOD':
                lifecycle_action = 'grace'
            else:
                lifecycle_action = 'billing_retry'
            admin_type = 'billing_retry'
        elif notification_type == 'REFUND':
            lifecycle_action = 'refund'
            admin_type = 'refund'
        elif notification_type == 'REVOKE':
            lifecycle_action = 'revoke'
            admin_type = 'revocation'

        client_id = self._client_id_for_event(transaction, original_transaction_id)
        admin_event = None
        if admin_type is not None:
            admin_event = {
                'event_type': admin_type,
                'client_id': client_id or '',
                'product_id': transaction.product_id if transaction is not None else '',
                'transaction_id': transaction_id or '',
                'notification_uuid': notification.notification_uuid,
                'detail': '/'.join(
                    value for value in (notification_type, subtype) if value
                ),
            }

        return self._repository.process_notification(
            notification_uuid=notification.notification_uuid,
            notification_type=notification_type,
            subtype=subtype,
            signed_payload=notification.signed_payload,
            transaction=stored_transaction,
            lifecycle_action=lifecycle_action,
            original_transaction_id=original_transaction_id,
            transaction_id=transaction_id,
            grace_expires_at=(
                renewal.grace_period_expires_date_ms if renewal is not None else None
            ),
            lifecycle_cutoff_at=(
                transaction.expires_date_ms
                if transaction is not None and transaction.expires_date_ms is not None
                else notification.signed_date_ms
            ),
            auto_renew=renewal.auto_renew if renewal is not None else None,
            renewal_signed_date_ms=renewal.signed_date_ms if renewal is not None else None,
            admin_event=admin_event,
        )

    async def record_validation_failure(self, signed_payload: str, detail: str) -> bool:
        return await asyncio.to_thread(
            self._repository.enqueue_validation_failure,
            signed_payload,
            detail,
        )

    def _client_for_notification(self, transaction: VerifiedAppStoreTransaction) -> str:
        client_id = self._client_id_for_event(
            transaction,
            transaction.original_transaction_id,
        )
        if client_id is None:
            raise ValueError('Apple transaction app account is unknown')
        return client_id

    def _client_id_for_event(
        self,
        transaction: VerifiedAppStoreTransaction | None,
        original_transaction_id: str | None,
    ) -> str | None:
        if original_transaction_id:
            owner = self._repository.subscription_owner(original_transaction_id)
            if owner is not None:
                return owner
        if transaction is not None and transaction.app_account_token:
            return self._repository.client_id_for_app_account_token(
                transaction.app_account_token
            )
        return None

    async def deliver_admin_events(
        self,
        notifier: AdminNotifier,
        *,
        limit: int = 20,
    ) -> int:
        delivered = 0
        for _ in range(limit):
            event = await asyncio.to_thread(self._repository.claim_admin_event)
            if event is None:
                break
            payload = dict(event.payload)
            if event.event_type == 'apple_subscription_restored':
                payload.setdefault('event_type', 'restore')
            elif event.event_type == 'apple_transaction_applied':
                payload.setdefault('event_type', 'purchase')
            recipients = tuple(notifier.delivery_recipients)
            if not recipients:
                await asyncio.to_thread(
                    self._repository.release_admin_event,
                    event.id,
                    event.lease_token,
                )
                raise RuntimeError('Admin notifier is not configured')
            delivered_recipients = payload.get('_delivered_admin_ids', [])
            if not isinstance(delivered_recipients, list):
                await asyncio.to_thread(
                    self._repository.release_admin_event,
                    event.id,
                    event.lease_token,
                )
                raise ValueError('invalid admin delivery progress')
            delivered_ids = {str(value) for value in delivered_recipients}
            try:
                for recipient_id in recipients:
                    if recipient_id in delivered_ids:
                        continue
                    await _shield_recipient_checkpoint(
                        self._deliver_admin_recipient(
                            notifier,
                            event_id=event.id,
                            lease_token=event.lease_token,
                            recipient_id=recipient_id,
                            payload=payload,
                        )
                    )
            except asyncio.CancelledError:
                await asyncio.to_thread(
                    self._repository.release_admin_event,
                    event.id,
                    event.lease_token,
                )
                raise
            except Exception:
                await asyncio.to_thread(
                    self._repository.release_admin_event,
                    event.id,
                    event.lease_token,
                )
                raise
            completed = await asyncio.to_thread(
                self._repository.complete_admin_event,
                event.id,
                event.lease_token,
            )
            if not completed:
                raise RuntimeError('Admin outbox lease ownership was lost')
            delivered += 1
        return delivered

    async def _deliver_admin_recipient(
        self,
        notifier: AdminNotifier,
        *,
        event_id: int,
        lease_token: str,
        recipient_id: str,
        payload: dict[str, object],
    ) -> None:
        renewed = await asyncio.to_thread(
            self._repository.renew_admin_event_lease,
            event_id,
            lease_token,
        )
        if not renewed:
            raise RuntimeError('Admin outbox lease ownership was lost')
        await notifier.notify_app_store_event_to(
            recipient_id,
            event_type=str(payload.get('event_type', 'purchase')),
            client_id=str(payload.get('client_id', '')),
            product_id=str(payload.get('product_id', '')),
            transaction_id=str(payload.get('transaction_id', '')),
            notification_uuid=str(payload.get('notification_uuid', '')),
            detail=str(payload.get('detail', '')),
        )
        marked = await asyncio.to_thread(
            self._repository.mark_admin_recipient_delivered,
            event_id,
            lease_token,
            recipient_id,
        )
        if not marked:
            raise RuntimeError('Admin outbox lease ownership was lost')

    @staticmethod
    def _stored_transaction(
        transaction: VerifiedAppStoreTransaction,
        *,
        client_id: str,
        app_account_token: str,
        readings: int,
        recurring: bool,
    ) -> StoredAppStoreTransaction:
        if transaction.purchase_date_ms is None:
            raise ValueError('Apple transaction purchase date is missing')
        if recurring and transaction.expires_date_ms is None:
            raise ValueError('Apple subscription expiry is missing')
        return StoredAppStoreTransaction(
            transaction_id=transaction.transaction_id,
            original_transaction_id=transaction.original_transaction_id,
            client_id=client_id,
            app_account_token=app_account_token,
            product_id=transaction.product_id,
            product_type='subscription' if recurring else 'consumable',
            readings=readings,
            purchased_at=transaction.purchase_date_ms,
            expires_at=transaction.expires_date_ms,
            environment=transaction.environment.value,
            signed_transaction=transaction.signed_transaction,
        )


def _normalized_token(value: str | None) -> str:
    return (value or '').strip().lower()


async def _shield_recipient_checkpoint(operation) -> None:
    task = asyncio.create_task(operation)
    try:
        await asyncio.shield(task)
    except asyncio.CancelledError:
        await task
        raise
