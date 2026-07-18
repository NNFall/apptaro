from __future__ import annotations

import asyncio

from src.domain.billing_plans import get_plan_by_store_product_id
from src.domain.billing_service import BillingService, BillingSummary
from src.integrations.app_store_gateway import AppStoreGateway, VerifiedAppStoreTransaction
from src.repositories.app_store_billing import (
    AppStoreBillingRepository,
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
            owner_client = self._repository.client_id_for_app_account_token(signed_token)
            if owner_client is not None:
                stored = self._stored_transaction(
                    verified,
                    client_id=owner_client,
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
