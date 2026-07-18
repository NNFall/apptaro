from __future__ import annotations

import sys
import asyncio
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from appstoreserverlibrary.models.Environment import Environment
from fastapi.testclient import TestClient


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.core.dependencies import (  # noqa: E402
    get_app_store_billing_service,
    get_billing_service,
)
from src.domain.app_store_billing_service import AppStoreBillingService  # noqa: E402
from src.domain.billing_service import BillingService  # noqa: E402
from src.integrations.app_store_gateway import VerifiedAppStoreTransaction  # noqa: E402
from src.integrations.app_store_gateway import AppStoreValidationError  # noqa: E402
from src.main import create_app  # noqa: E402
from src.repositories.app_store_billing import AppStoreBillingRepository  # noqa: E402
from src.repositories.storage import init_storage  # noqa: E402


NOW = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)


class FakeYooKassaGateway:
    @property
    def is_configured(self) -> bool:
        return False


class FakeNotifier:
    async def notify_subscription_canceled(self, client_id: str) -> None:
        return None


class FakeAppStoreGateway:
    def __init__(self) -> None:
        self.transaction: VerifiedAppStoreTransaction | None = None
        self.client_transaction: VerifiedAppStoreTransaction | Exception | None = None
        self.calls: list[str] = []
        self.signed_calls: list[tuple[str, Environment, str | None]] = []

    def get_verified_transaction(self, transaction_id: str) -> VerifiedAppStoreTransaction:
        self.calls.append(transaction_id)
        if self.transaction is None:
            raise RuntimeError('test transaction is not configured')
        return self.transaction

    def verify_signed_transaction(
        self,
        signed_transaction: str,
        *,
        expected_environment: Environment,
        requested_transaction_id: str | None = None,
    ) -> VerifiedAppStoreTransaction:
        self.signed_calls.append(
            (signed_transaction, expected_environment, requested_transaction_id),
        )
        outcome = self.client_transaction or self.transaction
        if isinstance(outcome, Exception):
            raise outcome
        if outcome is None:
            raise RuntimeError('test client transaction is not configured')
        return outcome


def _transaction(
    *,
    transaction_id: str,
    product_id: str,
    app_account_token: str | None,
    original_transaction_id: str | None = None,
) -> VerifiedAppStoreTransaction:
    recurring = product_id in {'weekly_readings', 'monthly_readings'}
    return VerifiedAppStoreTransaction(
        transaction_id=transaction_id,
        original_transaction_id=original_transaction_id or transaction_id,
        bundle_id='com.nexwit.tarot',
        product_id=product_id,
        environment=Environment.SANDBOX,
        app_account_token=app_account_token,
        purchase_date_ms=int(NOW.timestamp() * 1000),
        expires_date_ms=(
            int((NOW + timedelta(days=7)).timestamp() * 1000)
            if recurring
            else None
        ),
        revocation_date_ms=None,
        transaction_type=None,
        signed_transaction=f'signed-{transaction_id}',
    )


class TestAppStoreBillingApi:
    def setup_method(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app()
        init_storage(Path(self.temp_dir.name) / 'apple-api.db')
        self.repository = AppStoreBillingRepository()
        self.gateway = FakeAppStoreGateway()
        self.billing_service = BillingService(
            gateway=FakeYooKassaGateway(),  # type: ignore[arg-type]
            google_play_gateway=None,
            app_store_repository=self.repository,
            offer_url='https://example.com/terms',
            support_username='@support',
            support_max_url='https://max.example/support',
            return_url='https://example.com/return',
            test_mode=False,
            notifier=FakeNotifier(),  # type: ignore[arg-type]
        )
        self.apple_service = AppStoreBillingService(
            repository=self.repository,
            gateway=self.gateway,  # type: ignore[arg-type]
            billing_service=self.billing_service,
        )
        self.app.dependency_overrides[get_billing_service] = lambda: self.billing_service
        self.app.dependency_overrides[get_app_store_billing_service] = lambda: self.apple_service
        self.client = TestClient(self.app)

    def teardown_method(self) -> None:
        self.client.close()
        self.app.dependency_overrides.clear()
        self.temp_dir.cleanup()

    @staticmethod
    def _headers(client_id: str) -> dict[str, str]:
        return {'X-Apptaro-Client-Id': client_id}

    def _account_token(self, client_id: str) -> str:
        response = self.client.post(
            '/v1/billing/apple/account-token',
            json={},
            headers=self._headers(client_id),
        )
        assert response.status_code == 200, response.text
        return str(response.json()['app_account_token'])

    def _verify(
        self,
        client_id: str,
        *,
        transaction_id: str,
        product_id: str,
        operation: str = 'purchase',
    ):
        return self.client.post(
            '/v1/billing/apple/verify',
            json={
                'transaction_id': transaction_id,
                'product_id': product_id,
                'operation': operation,
                'client_signed_data': f'client-signed-{transaction_id}',
            },
            headers=self._headers(client_id),
        )

    def test_account_token_is_stable_without_gateway_credentials(self) -> None:
        unconfigured = AppStoreBillingService(
            repository=self.repository,
            gateway=None,
            billing_service=self.billing_service,
        )
        self.app.dependency_overrides[get_app_store_billing_service] = lambda: unconfigured

        first = self._account_token('client_apple_token')
        second = self._account_token('client_apple_token')
        assert first == second

        response = self._verify(
            'client_apple_token',
            transaction_id='tx-unconfigured',
            product_id='weekly_readings',
        )
        assert response.status_code == 503
        assert response.json()['detail'] == 'App Store verification is temporarily unavailable'

    def test_purchase_is_idempotent_and_balance_is_consumed_by_main_service(self) -> None:
        client_id = 'client_apple_purchase'
        token = self._account_token(client_id)
        self.gateway.transaction = _transaction(
            transaction_id='tx-purchase',
            product_id='weekly_readings',
            app_account_token=token,
        )

        first = self._verify(
            client_id,
            transaction_id='tx-purchase',
            product_id='weekly_readings',
        )
        replay = self._verify(
            client_id,
            transaction_id='tx-purchase',
            product_id='weekly_readings',
        )

        assert first.status_code == 200, first.text
        assert replay.status_code == 200, replay.text
        assert first.json()['active_subscription']['remaining'] == 15
        assert replay.json()['active_subscription']['remaining'] == 15
        assert self.repository.remaining_readings(client_id, at=NOW) == 15
        assert asyncio.run(self.billing_service.consume_generation(client_id)) is True
        assert self.repository.remaining_readings(client_id, at=NOW) == 14

    def test_product_mismatch_and_consumable_restore_are_rejected(self) -> None:
        client_id = 'client_apple_rejected'
        token = self._account_token(client_id)
        self.gateway.transaction = _transaction(
            transaction_id='tx-mismatch',
            product_id='weekly_readings',
            app_account_token=token,
        )
        mismatch = self._verify(
            client_id,
            transaction_id='tx-mismatch',
            product_id='monthly_readings',
        )
        assert mismatch.status_code == 400

        self.gateway.transaction = _transaction(
            transaction_id='tx-consumable',
            product_id='one10_readings',
            app_account_token=token,
        )
        restore = self._verify(
            client_id,
            transaction_id='tx-consumable',
            product_id='one10_readings',
            operation='restore',
        )
        assert restore.status_code == 400
        assert self.repository.remaining_readings(client_id, at=NOW) == 0

    def test_rejects_tampered_or_mismatched_client_signed_transaction(self) -> None:
        client_id = 'client_apple_signed_mismatch'
        token = self._account_token(client_id)
        self.gateway.transaction = _transaction(
            transaction_id='tx-client-jws',
            product_id='weekly_readings',
            app_account_token=token,
        )
        self.gateway.client_transaction = _transaction(
            transaction_id='tx-client-jws',
            product_id='monthly_readings',
            app_account_token=token,
        )

        mismatch = self._verify(
            client_id,
            transaction_id='tx-client-jws',
            product_id='weekly_readings',
        )

        assert mismatch.status_code == 400
        assert self.repository.remaining_readings(client_id, at=NOW) == 0
        assert self.gateway.signed_calls == [
            ('client-signed-tx-client-jws', Environment.SANDBOX, 'tx-client-jws'),
        ]

        self.gateway.client_transaction = AppStoreValidationError('raw signature details')
        tampered = self._verify(
            client_id,
            transaction_id='tx-client-jws',
            product_id='weekly_readings',
        )
        assert tampered.status_code == 400
        assert tampered.json()['detail'] == 'Apple purchase could not be verified'

    def test_restore_transfers_active_subscription_without_double_grant(self) -> None:
        old_client = 'client_apple_restore_old'
        old_token = self._account_token(old_client)
        self.gateway.transaction = _transaction(
            transaction_id='tx-restore',
            original_transaction_id='original-restore',
            product_id='weekly_readings',
            app_account_token=old_token,
        )
        purchased = self._verify(
            old_client,
            transaction_id='tx-restore',
            product_id='weekly_readings',
        )
        assert purchased.status_code == 200, purchased.text

        new_client = 'client_apple_restore_new'
        self._account_token(new_client)
        restored = self._verify(
            new_client,
            transaction_id='tx-restore',
            product_id='weekly_readings',
            operation='restore',
        )

        assert restored.status_code == 200, restored.text
        assert restored.json()['active_subscription']['remaining'] == 15
        assert self.repository.remaining_readings(old_client, at=NOW) == 0
        assert self.repository.remaining_readings(new_client, at=NOW) == 15
