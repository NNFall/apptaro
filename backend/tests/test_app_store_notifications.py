from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
import httpx
from appstoreserverlibrary.models.Environment import Environment
from fastapi.testclient import TestClient


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.core.dependencies import get_admin_notifier, get_app_store_billing_service  # noqa: E402
import src.api.app_store_billing as apple_api_module  # noqa: E402
from src.domain.app_store_billing_service import AppStoreBillingService  # noqa: E402
from src.domain.billing_service import BillingService  # noqa: E402
from src.integrations.admin_notifier import AdminNotifier  # noqa: E402
from src.integrations.app_store_gateway import (  # noqa: E402
    APP_STORE_PRODUCT_IDS,
    AppStoreGateway,
    AppStoreGatewayError,
    AppStoreValidationError,
    VerifiedAppStoreNotification,
    VerifiedAppStoreRenewalInfo,
    VerifiedAppStoreTransaction,
)
from src.main import create_app  # noqa: E402
from src.main import _app_store_outbox_loop  # noqa: E402
import src.main as main_module  # noqa: E402
import src.repositories.app_store_billing as app_store_repository_module  # noqa: E402
from src.repositories.app_store_billing import AppStoreBillingRepository  # noqa: E402
from src.repositories.storage import connect, init_storage  # noqa: E402


NOW = datetime.now(UTC)
MISSING = object()


class FakeBillingService:
    async def get_summary(self, client_id: str):  # pragma: no cover - notification path only
        raise AssertionError('billing summary is not used by notifications')


class FakeNotificationGateway:
    def __init__(self) -> None:
        self.notification: VerifiedAppStoreNotification | Exception | None = None
        self.calls: list[str] = []

    def verify_notification(self, signed_payload: str) -> VerifiedAppStoreNotification:
        self.calls.append(signed_payload)
        if isinstance(self.notification, Exception):
            raise self.notification
        if self.notification is None:
            raise RuntimeError('notification is not configured')
        return self.notification


class CapturingNotifier:
    def __init__(self) -> None:
        self.events: list[dict[str, object]] = []

    @property
    def delivery_recipients(self) -> tuple[str, ...]:
        return ('test-admin',)

    async def notify_app_store_event(self, **event: object) -> None:
        self.events.append(event)

    async def notify_app_store_event_to(
        self,
        recipient_id: str,
        **event: object,
    ) -> None:
        assert recipient_id == 'test-admin'
        self.events.append(event)


def _transaction(
    transaction_id: str,
    *,
    product_id: str = 'weekly_readings',
    original_transaction_id: str = 'original-weekly',
    app_account_token: str = '00000000-0000-4000-8000-000000000001',
    purchased_at: datetime | None = None,
    expires_at: datetime | None = None,
    revoked: bool = False,
) -> VerifiedAppStoreTransaction:
    recurring = product_id in {'weekly_readings', 'monthly_readings'}
    return VerifiedAppStoreTransaction(
        transaction_id=transaction_id,
        original_transaction_id=original_transaction_id,
        bundle_id='com.nexwit.tarot',
        product_id=product_id,
        environment=Environment.SANDBOX,
        app_account_token=app_account_token,
        purchase_date_ms=int((purchased_at or NOW).timestamp() * 1000),
        expires_date_ms=(
            int((expires_at or NOW + timedelta(days=7)).timestamp() * 1000)
            if recurring
            else None
        ),
        revocation_date_ms=int(NOW.timestamp() * 1000) if revoked else None,
        transaction_type=None,
        signed_transaction=f'signed-{transaction_id}',
    )


def _renewal(
    *,
    grace_expires_at: datetime | None = None,
    billing_retry: bool = False,
    auto_renew: bool | None = None,
    signed_at: datetime | None = NOW,
) -> VerifiedAppStoreRenewalInfo:
    return VerifiedAppStoreRenewalInfo(
        original_transaction_id='original-weekly',
        product_id='weekly_readings',
        environment=Environment.SANDBOX,
        app_account_token='00000000-0000-4000-8000-000000000001',
        grace_period_expires_date_ms=(
            int(grace_expires_at.timestamp() * 1000) if grace_expires_at else None
        ),
        is_in_billing_retry_period=billing_retry,
        expiration_intent=None,
        signed_renewal_info='signed-renewal',
        auto_renew=auto_renew,
        signed_date_ms=int(signed_at.timestamp() * 1000) if signed_at is not None else None,
    )


def _notification(
    uuid: str,
    notification_type: str,
    *,
    subtype: str | None = None,
    transaction: VerifiedAppStoreTransaction | None = None,
    renewal_info: VerifiedAppStoreRenewalInfo | None = None,
    signed_at: datetime = NOW,
) -> VerifiedAppStoreNotification:
    return VerifiedAppStoreNotification(
        notification_uuid=uuid,
        notification_type=notification_type,
        subtype=subtype,
        signed_date_ms=int(signed_at.timestamp() * 1000),
        environment=Environment.SANDBOX,
        transaction=transaction,
        renewal_info=renewal_info,
        signed_payload=f'outer-{uuid}',
    )


@pytest.fixture
def notification_api():
    temp_dir = tempfile.TemporaryDirectory()
    app = create_app()
    init_storage(Path(temp_dir.name) / 'notifications.db')
    repository = AppStoreBillingRepository()
    gateway = FakeNotificationGateway()
    service = AppStoreBillingService(
        repository=repository,
        gateway=gateway,  # type: ignore[arg-type]
        billing_service=FakeBillingService(),  # type: ignore[arg-type]
    )
    notifier = CapturingNotifier()
    app.dependency_overrides[get_app_store_billing_service] = lambda: service
    app.dependency_overrides[get_admin_notifier] = lambda: notifier
    client = TestClient(app)
    yield client, repository, gateway, notifier
    client.close()
    app.dependency_overrides.clear()
    temp_dir.cleanup()


def _register_account(repository: AppStoreBillingRepository) -> str:
    token = repository.get_or_create_app_account_token('apple-client-001')
    return token


def _post(client: TestClient, payload: str = 'signed-outer'):
    return client.post('/v1/billing/apple/notifications', json={'signedPayload': payload})


def test_notification_endpoint_needs_no_client_header_and_dedupes_purchase(notification_api) -> None:
    client, repository, gateway, notifier = notification_api
    token = _register_account(repository)
    transaction = _transaction('tx-initial', app_account_token=token)
    gateway.notification = _notification(
        'uuid-initial',
        'SUBSCRIBED',
        subtype='INITIAL_BUY',
        transaction=transaction,
    )

    first = _post(client)
    duplicate = _post(client)
    gateway.notification = _notification(
        'uuid-initial-redelivery',
        'SUBSCRIBED',
        subtype='INITIAL_BUY',
        transaction=transaction,
    )
    redelivery = _post(client)

    assert first.status_code == 200, first.text
    assert duplicate.status_code == 200, duplicate.text
    assert redelivery.status_code == 200, redelivery.text
    assert first.json() == {'status': 'ok'}
    assert repository.remaining_readings('apple-client-001') == 15
    assert len(notifier.events) == 1
    assert notifier.events[0]['event_type'] == 'purchase'
    with closing(connect()) as conn:
        assert conn.execute('SELECT COUNT(*) FROM apple_notifications').fetchone()[0] == 2
        assert conn.execute('SELECT COUNT(*) FROM apple_transactions').fetchone()[0] == 1


def test_renewal_grants_once_and_duplicate_sends_admin_once(notification_api) -> None:
    client, repository, gateway, notifier = notification_api
    token = _register_account(repository)
    repository.apply_verified_transaction(
        AppStoreBillingService._stored_transaction(
            _transaction('tx-old', app_account_token=token, expires_at=NOW + timedelta(days=1)),
            client_id='apple-client-001',
            app_account_token=token,
            readings=15,
            recurring=True,
        )
    )
    gateway.notification = _notification(
        'uuid-renewal',
        'DID_RENEW',
        transaction=_transaction(
            'tx-renewal',
            app_account_token=token,
            expires_at=NOW + timedelta(days=8),
        ),
        renewal_info=_renewal(),
    )

    assert _post(client).status_code == 200
    assert _post(client).status_code == 200

    assert repository.remaining_readings('apple-client-001') == 30
    renewal_events = [event for event in notifier.events if event['event_type'] == 'renewal']
    assert len(renewal_events) == 1


def test_newer_auto_renew_off_updates_summary_and_stale_on_does_not_revert(
    notification_api,
) -> None:
    client, repository, gateway, _ = notification_api
    token = _register_account(repository)
    repository.apply_verified_transaction(
        AppStoreBillingService._stored_transaction(
            _transaction('tx-auto-renew', app_account_token=token),
            client_id='apple-client-001',
            app_account_token=token,
            readings=15,
            recurring=True,
        )
    )
    billing_service = BillingService(
        gateway=SimpleNamespace(is_configured=False),  # type: ignore[arg-type]
        google_play_gateway=None,
        app_store_repository=repository,
        offer_url='https://example.com/terms',
        support_username='@support',
        support_max_url='https://max.example/support',
        return_url='https://example.com/return',
        test_mode=False,
        notifier=SimpleNamespace(),  # type: ignore[arg-type]
    )

    unknown = asyncio.run(billing_service.get_summary('apple-client-001'))
    assert unknown.active_subscription is not None
    assert unknown.active_subscription.auto_renew == 1

    gateway.notification = _notification(
        'uuid-auto-renew-on',
        'DID_CHANGE_RENEWAL_STATUS',
        renewal_info=_renewal(auto_renew=True, signed_at=NOW),
        signed_at=NOW,
    )
    assert _post(client).status_code == 200

    gateway.notification = _notification(
        'uuid-auto-renew-off',
        'DID_CHANGE_RENEWAL_STATUS',
        renewal_info=_renewal(auto_renew=False, signed_at=NOW + timedelta(minutes=2)),
        signed_at=NOW + timedelta(minutes=1),
    )
    assert _post(client).status_code == 200

    off = asyncio.run(billing_service.get_summary('apple-client-001'))
    assert off.active_subscription is not None
    assert off.active_subscription.remaining == 15
    assert off.active_subscription.auto_renew == 0
    assert repository.entitlement_snapshot('apple-client-001').auto_renew is False

    gateway.notification = _notification(
        'uuid-auto-renew-stale-on',
        'DID_CHANGE_RENEWAL_STATUS',
        renewal_info=_renewal(auto_renew=True, signed_at=NOW + timedelta(minutes=1)),
        signed_at=NOW + timedelta(minutes=3),
    )
    assert _post(client).status_code == 200

    stale = asyncio.run(billing_service.get_summary('apple-client-001'))
    assert stale.active_subscription is not None
    assert stale.active_subscription.remaining == 15
    assert stale.active_subscription.auto_renew == 0

    gateway.notification = _notification(
        'uuid-auto-renew-undated-on',
        'DID_CHANGE_RENEWAL_STATUS',
        renewal_info=_renewal(auto_renew=True, signed_at=None),
        signed_at=NOW + timedelta(minutes=4),
    )
    assert _post(client).status_code == 200

    undated = asyncio.run(billing_service.get_summary('apple-client-001'))
    assert undated.active_subscription is not None
    assert undated.active_subscription.remaining == 15
    assert undated.active_subscription.auto_renew == 0


def test_pending_newer_off_survives_reopen_and_delayed_chain_creation(
    notification_api,
) -> None:
    client, repository, gateway, _ = notification_api
    gateway.notification = _notification(
        'uuid-pending-auto-renew-off',
        'DID_CHANGE_RENEWAL_STATUS',
        renewal_info=_renewal(auto_renew=False, signed_at=NOW + timedelta(minutes=2)),
        signed_at=NOW,
    )
    assert _post(client).status_code == 200

    gateway.notification = _notification(
        'uuid-pending-stale-auto-renew-on',
        'DID_CHANGE_RENEWAL_STATUS',
        renewal_info=_renewal(auto_renew=True, signed_at=NOW + timedelta(minutes=1)),
        signed_at=NOW + timedelta(minutes=3),
    )
    assert _post(client).status_code == 200

    with closing(connect()) as conn:
        database_path = Path(
            conn.execute("PRAGMA database_list").fetchone()['file']
        )
    init_storage(database_path)

    token = _register_account(repository)
    repository.apply_verified_transaction(
        AppStoreBillingService._stored_transaction(
            _transaction('tx-delayed-grant', app_account_token=token),
            client_id='apple-client-001',
            app_account_token=token,
            readings=15,
            recurring=True,
        )
    )
    billing_service = BillingService(
        gateway=SimpleNamespace(is_configured=False),  # type: ignore[arg-type]
        google_play_gateway=None,
        app_store_repository=repository,
        offer_url='https://example.com/terms',
        support_username='@support',
        support_max_url='https://max.example/support',
        return_url='https://example.com/return',
        test_mode=False,
        notifier=SimpleNamespace(),  # type: ignore[arg-type]
    )

    summary = asyncio.run(billing_service.get_summary('apple-client-001'))

    assert summary.active_subscription is not None
    assert summary.active_subscription.remaining == 15
    assert summary.active_subscription.auto_renew == 0
    assert repository.entitlement_snapshot('apple-client-001').auto_renew is False


@pytest.mark.parametrize(
    ('notification_type', 'subtype', 'expected_event'),
    [
        ('EXPIRED', 'VOLUNTARY', 'expiration'),
        ('GRACE_PERIOD_EXPIRED', None, 'expiration'),
        ('REFUND', None, 'refund'),
        ('REVOKE', None, 'revocation'),
    ],
)
def test_terminal_subscription_events_revoke_remaining_entitlement(
    notification_api,
    notification_type: str,
    subtype: str | None,
    expected_event: str,
) -> None:
    client, repository, gateway, notifier = notification_api
    token = _register_account(repository)
    transaction = _transaction('tx-active', app_account_token=token)
    repository.apply_verified_transaction(
        AppStoreBillingService._stored_transaction(
            transaction,
            client_id='apple-client-001',
            app_account_token=token,
            readings=15,
            recurring=True,
        )
    )
    gateway.notification = _notification(
        f'uuid-{notification_type}',
        notification_type,
        subtype=subtype,
        transaction=_transaction(
            'tx-active',
            app_account_token=token,
            revoked=notification_type in {'REFUND', 'REVOKE'},
        ),
        renewal_info=_renewal(),
    )

    response = _post(client)

    assert response.status_code == 200, response.text
    assert repository.remaining_readings('apple-client-001') == 0
    assert notifier.events[-1]['event_type'] == expected_event
    with closing(connect()) as conn:
        assert conn.execute('SELECT COUNT(*) FROM apple_transactions').fetchone()[0] == 1


def test_grace_period_extends_access_and_billing_retry_without_grace_stops_it(
    notification_api,
) -> None:
    client, repository, gateway, notifier = notification_api
    token = _register_account(repository)
    repository.apply_verified_transaction(
        AppStoreBillingService._stored_transaction(
            _transaction(
                'tx-old-expired',
                app_account_token=token,
                purchased_at=NOW - timedelta(days=10),
                expires_at=NOW - timedelta(days=3),
            ),
            client_id='apple-client-001',
            app_account_token=token,
            readings=15,
            recurring=True,
        )
    )
    original_expiry = NOW + timedelta(minutes=5)
    transaction = _transaction(
        'tx-grace',
        app_account_token=token,
        expires_at=original_expiry,
    )
    repository.apply_verified_transaction(
        AppStoreBillingService._stored_transaction(
            transaction,
            client_id='apple-client-001',
            app_account_token=token,
            readings=15,
            recurring=True,
        )
    )
    grace_expiry = NOW + timedelta(days=3)
    gateway.notification = _notification(
        'uuid-grace',
        'DID_FAIL_TO_RENEW',
        subtype='GRACE_PERIOD',
        transaction=transaction,
        renewal_info=_renewal(grace_expires_at=grace_expiry, billing_retry=True),
    )

    grace = _post(client)
    assert grace.status_code == 200, grace.text
    assert repository.remaining_readings(
        'apple-client-001', at=NOW + timedelta(days=2)
    ) == 15

    gateway.notification = _notification(
        'uuid-retry',
        'DID_FAIL_TO_RENEW',
        transaction=transaction,
        renewal_info=_renewal(billing_retry=True),
    )
    retry = _post(client)

    assert retry.status_code == 200, retry.text
    assert repository.remaining_readings('apple-client-001') == 0
    assert [
        event['event_type']
        for event in notifier.events
        if event['event_type'] == 'billing_retry'
    ] == [
        'billing_retry',
        'billing_retry',
    ]


def test_consumable_refund_revokes_only_refunded_lot(notification_api) -> None:
    client, repository, gateway, _ = notification_api
    token = _register_account(repository)
    for transaction_id in ('tx-consumable-a', 'tx-consumable-b'):
        repository.apply_verified_transaction(
            AppStoreBillingService._stored_transaction(
                _transaction(
                    transaction_id,
                    product_id='one10_readings',
                    original_transaction_id=transaction_id,
                    app_account_token=token,
                ),
                client_id='apple-client-001',
                app_account_token=token,
                readings=10,
                recurring=False,
            )
        )
    gateway.notification = _notification(
        'uuid-consumable-refund',
        'REFUND',
        transaction=_transaction(
            'tx-consumable-a',
            product_id='one10_readings',
            original_transaction_id='tx-consumable-a',
            app_account_token=token,
            revoked=True,
        ),
    )

    assert _post(client).status_code == 200
    assert repository.remaining_readings('apple-client-001') == 10
    with closing(connect()) as conn:
        assert conn.execute('SELECT COUNT(*) FROM apple_transactions').fetchone()[0] == 2
        assert conn.execute('SELECT COUNT(*) FROM entitlement_lots').fetchone()[0] == 2


@pytest.mark.parametrize(
    ('notification_type', 'subtype'),
    [
        ('EXPIRED', 'BILLING_RETRY'),
        ('REFUND', None),
        ('REVOKE', None),
        ('DID_FAIL_TO_RENEW', None),
    ],
)
def test_old_lifecycle_event_never_revokes_newer_renewal_lot(
    notification_api,
    notification_type: str,
    subtype: str | None,
) -> None:
    client, repository, gateway, _ = notification_api
    token = _register_account(repository)
    old = _transaction(
        'tx-period-old',
        app_account_token=token,
        purchased_at=NOW - timedelta(days=14),
        expires_at=NOW - timedelta(days=7),
    )
    newer = _transaction(
        'tx-period-new',
        app_account_token=token,
        purchased_at=NOW - timedelta(days=7),
        expires_at=NOW + timedelta(days=1),
    )
    for verified in (old, newer):
        repository.apply_verified_transaction(
            AppStoreBillingService._stored_transaction(
                verified,
                client_id='apple-client-001',
                app_account_token=token,
                readings=15,
                recurring=True,
            )
        )
    gateway.notification = _notification(
        f'uuid-old-{notification_type}',
        notification_type,
        subtype=subtype,
        transaction=_transaction(
            'tx-period-old',
            app_account_token=token,
            purchased_at=NOW - timedelta(days=14),
            expires_at=NOW - timedelta(days=7),
            revoked=notification_type in {'REFUND', 'REVOKE'},
        ),
        renewal_info=_renewal(billing_retry=notification_type == 'DID_FAIL_TO_RENEW'),
    )

    response = _post(client)

    assert response.status_code == 200, response.text
    assert repository.remaining_readings('apple-client-001') == 15
    with closing(connect()) as conn:
        old_remaining = conn.execute(
            'SELECT remaining FROM entitlement_lots WHERE source_transaction_id = ?',
            ('tx-period-old',),
        ).fetchone()['remaining']
        new_remaining = conn.execute(
            'SELECT remaining FROM entitlement_lots WHERE source_transaction_id = ?',
            ('tx-period-new',),
        ).fetchone()['remaining']
    assert old_remaining == 0
    assert new_remaining == 15


def test_chain_lifecycle_without_transaction_uses_signed_date_cutoff(notification_api) -> None:
    client, repository, gateway, _ = notification_api
    token = _register_account(repository)
    for verified in (
        _transaction(
            'tx-cutoff-old',
            app_account_token=token,
            purchased_at=NOW - timedelta(days=14),
            expires_at=NOW - timedelta(days=7),
        ),
        _transaction(
            'tx-cutoff-new',
            app_account_token=token,
            purchased_at=NOW - timedelta(days=1),
            expires_at=NOW + timedelta(days=6),
        ),
    ):
        repository.apply_verified_transaction(
            AppStoreBillingService._stored_transaction(
                verified,
                client_id='apple-client-001',
                app_account_token=token,
                readings=15,
                recurring=True,
            )
        )
    notification = _notification(
        'uuid-cutoff',
        'DID_FAIL_TO_RENEW',
        renewal_info=_renewal(billing_retry=True),
    )
    gateway.notification = VerifiedAppStoreNotification(
        **{
            **notification.__dict__,
            'signed_date_ms': int((NOW - timedelta(days=5)).timestamp() * 1000),
        }
    )

    response = _post(client)

    assert response.status_code == 200, response.text
    assert repository.remaining_readings('apple-client-001') == 15


@pytest.mark.parametrize('terminal_type', ['REFUND', 'REVOKE'])
def test_terminal_notification_seen_before_grant_blocks_matching_transaction(
    notification_api,
    terminal_type: str,
) -> None:
    client, repository, gateway, _ = notification_api
    token = _register_account(repository)
    transaction = _transaction(
        'tx-terminal-before-grant',
        app_account_token=token,
        revoked=True,
    )
    gateway.notification = _notification(
        f'uuid-terminal-first-{terminal_type}',
        terminal_type,
        transaction=transaction,
        renewal_info=_renewal(),
    )
    assert _post(client).status_code == 200

    gateway.notification = _notification(
        f'uuid-late-grant-{terminal_type}',
        'DID_RENEW',
        transaction=_transaction(
            'tx-terminal-before-grant',
            app_account_token=token,
        ),
        renewal_info=_renewal(),
    )
    response = _post(client)

    assert response.status_code == 200, response.text
    assert repository.remaining_readings('apple-client-001') == 0
    with closing(connect()) as conn:
        lot = conn.execute(
            'SELECT granted, remaining FROM entitlement_lots WHERE source_transaction_id = ?',
            ('tx-terminal-before-grant',),
        ).fetchone()
    assert dict(lot) == {'granted': 15, 'remaining': 0}


@pytest.mark.parametrize('terminal_type', ['REFUND', 'REVOKE'])
def test_terminal_before_grant_blocks_only_old_period_in_same_chain(
    notification_api,
    terminal_type: str,
) -> None:
    client, repository, gateway, _ = notification_api
    token = _register_account(repository)
    old_expiry = NOW + timedelta(days=1)
    gateway.notification = _notification(
        f'uuid-chain-terminal-{terminal_type}',
        terminal_type,
        transaction=_transaction(
            'tx-chain-terminal',
            app_account_token=token,
            purchased_at=NOW - timedelta(days=6),
            expires_at=old_expiry,
            revoked=True,
        ),
        renewal_info=_renewal(),
    )
    assert _post(client).status_code == 200

    gateway.notification = _notification(
        f'uuid-chain-late-old-{terminal_type}',
        'DID_RENEW',
        transaction=_transaction(
            'tx-chain-late-old',
            app_account_token=token,
            purchased_at=NOW - timedelta(days=6),
            expires_at=old_expiry,
        ),
        renewal_info=_renewal(),
    )
    assert _post(client).status_code == 200

    gateway.notification = _notification(
        f'uuid-chain-newer-{terminal_type}',
        'DID_RENEW',
        transaction=_transaction(
            'tx-chain-newer',
            app_account_token=token,
            purchased_at=NOW + timedelta(days=1),
            expires_at=NOW + timedelta(days=8),
        ),
        renewal_info=_renewal(),
    )
    assert _post(client).status_code == 200

    with closing(connect()) as conn:
        old_remaining = conn.execute(
            'SELECT remaining FROM entitlement_lots WHERE source_transaction_id = ?',
            ('tx-chain-late-old',),
        ).fetchone()['remaining']
        newer_remaining = conn.execute(
            'SELECT remaining FROM entitlement_lots WHERE source_transaction_id = ?',
            ('tx-chain-newer',),
        ).fetchone()['remaining']
    assert old_remaining == 0
    assert newer_remaining == 15
    assert repository.remaining_readings(
        'apple-client-001',
        at=NOW + timedelta(days=2),
    ) == 15


def test_stale_outbox_sending_lease_is_reclaimed_after_crash(notification_api) -> None:
    _, repository, _, _ = notification_api
    token = _register_account(repository)
    repository.apply_verified_transaction(
        AppStoreBillingService._stored_transaction(
            _transaction('tx-stale-outbox', app_account_token=token),
            client_id='apple-client-001',
            app_account_token=token,
            readings=15,
            recurring=True,
        )
    )
    claimed_at = NOW - timedelta(minutes=10)
    with closing(connect()) as conn:
        conn.execute(
            "UPDATE admin_outbox SET status = ? WHERE dedupe_key = ?",
            (f'sending:{claimed_at.isoformat()}', 'apple-transaction:tx-stale-outbox'),
        )
        conn.commit()

    event = repository.claim_admin_event(lease_seconds=60, now=NOW)

    assert event is not None
    assert event.payload['transaction_id'] == 'tx-stale-outbox'


def test_fresh_outbox_sending_lease_is_not_double_claimed(notification_api) -> None:
    _, repository, _, _ = notification_api
    token = _register_account(repository)
    repository.apply_verified_transaction(
        AppStoreBillingService._stored_transaction(
            _transaction('tx-fresh-outbox', app_account_token=token),
            client_id='apple-client-001',
            app_account_token=token,
            readings=15,
            recurring=True,
        )
    )
    with closing(connect()) as conn:
        conn.execute(
            "UPDATE admin_outbox SET status = ? WHERE dedupe_key = ?",
            (f'sending:{NOW.isoformat()}', 'apple-transaction:tx-fresh-outbox'),
        )
        conn.commit()

    assert repository.claim_admin_event(lease_seconds=60, now=NOW) is None


def test_reclaimed_outbox_lease_rejects_stale_worker_complete_and_release(notification_api) -> None:
    _, repository, _, _ = notification_api
    token = _register_account(repository)
    repository.apply_verified_transaction(
        AppStoreBillingService._stored_transaction(
            _transaction('tx-lease-owner', app_account_token=token),
            client_id='apple-client-001',
            app_account_token=token,
            readings=15,
            recurring=True,
        )
    )

    stale = repository.claim_admin_event(lease_seconds=60, now=NOW)
    reclaimed = repository.claim_admin_event(
        lease_seconds=60,
        now=NOW + timedelta(seconds=60),
    )

    assert stale is not None and reclaimed is not None
    assert stale.id == reclaimed.id
    assert stale.lease_token != reclaimed.lease_token
    assert repository.release_admin_event(reclaimed.id, '%') is False
    assert repository.complete_admin_event(stale.id, stale.lease_token) is False
    assert repository.release_admin_event(stale.id, stale.lease_token) is False
    assert repository.complete_admin_event(reclaimed.id, reclaimed.lease_token) is True
    with closing(connect()) as conn:
        status_value = conn.execute(
            'SELECT status FROM admin_outbox WHERE id = ?',
            (reclaimed.id,),
        ).fetchone()['status']
    assert status_value == 'delivered'


def test_validation_failure_is_durable_deduped_and_contains_no_payload(notification_api) -> None:
    client, _, gateway, notifier = notification_api
    gateway.notification = AppStoreValidationError('invalid signature')

    first = _post(client, 'secret-signed-payload')
    replay = _post(client, 'secret-signed-payload')

    assert first.status_code == 400
    assert replay.status_code == 400
    assert len(notifier.events) == 1
    with closing(connect()) as conn:
        rows = conn.execute(
            "SELECT payload, status FROM admin_outbox WHERE event_type = 'apple_validation_failure'",
        ).fetchall()
    assert len(rows) == 1
    assert 'secret-signed-payload' not in rows[0]['payload']
    assert 'signedPayload' not in rows[0]['payload']


@pytest.mark.parametrize(
    'body',
    [
        {},
        {'signedPayload': None},
        {'signedPayload': ''},
        {'signedPayload': {'secret': 'must-not-be-stored'}},
    ],
)
def test_malformed_or_missing_signed_payload_is_400_and_durable_deduped(
    notification_api,
    body: dict[str, object],
) -> None:
    client, _, _, _ = notification_api

    first = client.post('/v1/billing/apple/notifications', json=body)
    replay = client.post('/v1/billing/apple/notifications', json=body)

    assert first.status_code == 400, first.text
    assert replay.status_code == 400, replay.text
    with closing(connect()) as conn:
        rows = conn.execute(
            "SELECT dedupe_key, payload FROM admin_outbox WHERE event_type = 'apple_validation_failure'",
        ).fetchall()
    assert len(rows) == 1
    assert 'must-not-be-stored' not in rows[0]['payload']
    assert 'signedPayload' not in rows[0]['payload']


def test_many_unique_invalid_payloads_coalesce_alert_and_keep_valid_notifications_working(
    notification_api,
) -> None:
    client, repository, gateway, notifier = notification_api
    gateway.notification = AppStoreValidationError('invalid signature')

    for index in range(40):
        response = _post(client, f'unique-invalid-payload-{index}')
        assert response.status_code == 400

    with closing(connect()) as conn:
        outbox_count = conn.execute(
            "SELECT COUNT(*) FROM admin_outbox WHERE event_type = 'apple_validation_failure'",
        ).fetchone()[0]
        bucket = conn.execute(
            'SELECT attempt_count FROM apple_validation_failure_buckets',
        ).fetchone()
    assert outbox_count == 1
    assert bucket['attempt_count'] == 40
    assert len(notifier.events) == 1

    token = _register_account(repository)
    gateway.notification = _notification(
        'uuid-valid-after-invalid-flood',
        'SUBSCRIBED',
        subtype='INITIAL_BUY',
        transaction=_transaction('tx-valid-after-flood', app_account_token=token),
    )
    valid = _post(client, 'valid-apple-signed-payload')

    assert valid.status_code == 200, valid.text
    assert repository.remaining_readings('apple-client-001') == 15


def test_validation_failure_bucket_is_atomic_across_workers_and_retained_bounded(
    notification_api,
) -> None:
    _, repository, _, _ = notification_api

    def record(index: int) -> bool:
        return repository.enqueue_validation_failure(
            f'unique-junk-{index}',
            'signature verification failed',
            now=NOW - timedelta(minutes=1),
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        inserted = list(executor.map(record, range(32)))

    assert sum(inserted) == 1
    with closing(connect()) as conn:
        row = conn.execute(
            'SELECT COUNT(*) AS buckets, SUM(attempt_count) AS attempts FROM apple_validation_failure_buckets',
        ).fetchone()
    assert dict(row) == {'buckets': 1, 'attempts': 32}

    repository.enqueue_validation_failure(
        'new-window-junk',
        'signature verification failed',
        now=NOW + timedelta(days=2),
    )
    with closing(connect()) as conn:
        buckets = conn.execute(
            'SELECT COUNT(*) FROM apple_validation_failure_buckets',
        ).fetchone()[0]
        outbox_rows = conn.execute(
            "SELECT COUNT(*) FROM admin_outbox WHERE event_type = 'apple_validation_failure'",
        ).fetchone()[0]
    assert buckets == 1
    assert outbox_rows == 1


def test_oversized_notification_is_rejected_before_verification(notification_api) -> None:
    client, _, gateway, _ = notification_api

    oversized_signed_payload = 'x' * (
        apple_api_module.APPLE_SIGNED_PAYLOAD_MAX_CHARS + 1
    )
    signed_payload_response = _post(client, oversized_signed_payload)
    oversized_body_response = client.post(
        '/v1/billing/apple/notifications',
        content=b'x' * (apple_api_module.APPLE_NOTIFICATION_MAX_BODY_BYTES + 1),
        headers={'content-type': 'application/json'},
    )

    assert signed_payload_response.status_code == 413
    assert oversized_body_response.status_code == 413
    assert gateway.calls == []


def test_background_outbox_worker_retries_with_bounded_backoff_and_stops() -> None:
    class FlakyService:
        def __init__(self) -> None:
            self.calls = 0

        async def deliver_admin_events(self, notifier) -> int:
            self.calls += 1
            if self.calls < 3:
                raise RuntimeError('telegram unavailable')
            return 1

    service = FlakyService()
    stop_event = asyncio.Event()
    delays: list[float] = []

    async def fake_waiter(event: asyncio.Event, delay: float) -> bool:
        delays.append(delay)
        if len(delays) == 4:
            event.set()
        return event.is_set()

    asyncio.run(
        _app_store_outbox_loop(
            service,  # type: ignore[arg-type]
            object(),  # type: ignore[arg-type]
            SimpleNamespace(exception=lambda *args, **kwargs: None),
            stop_event=stop_event,
            base_delay=1.0,
            max_delay=2.0,
            wait_for_stop=fake_waiter,
        )
    )

    assert service.calls == 4
    assert delays == [1.0, 2.0, 1.0, 1.0]


def test_fastapi_lifespan_starts_and_stops_outbox_drain(monkeypatch) -> None:
    class BackgroundService:
        def __init__(self) -> None:
            self.called = asyncio.Event()

        async def deliver_admin_events(self, notifier) -> int:
            self.called.set()
            return 0

    class LegacyBilling:
        is_configured = False

    service = BackgroundService()
    monkeypatch.setattr(main_module, 'get_app_store_billing_service', lambda: service)
    monkeypatch.setattr(main_module, 'get_admin_notifier', lambda: object())
    monkeypatch.setattr(main_module, 'get_billing_service', lambda: LegacyBilling())
    app = main_module.create_app()

    with TestClient(app):
        for _ in range(100):
            if service.called.is_set():
                break
            import time

            time.sleep(0.01)
        assert service.called.is_set()


def test_fastapi_lifespan_stops_outbox_when_application_raises(monkeypatch) -> None:
    stop_states: list[bool] = []

    async def probe_worker(service, notifier, logger, *, stop_event, **kwargs) -> None:
        try:
            await stop_event.wait()
        finally:
            stop_states.append(stop_event.is_set())

    class LegacyBilling:
        is_configured = False

    monkeypatch.setattr(main_module, '_app_store_outbox_loop', probe_worker)
    monkeypatch.setattr(main_module, 'get_app_store_billing_service', lambda: object())
    monkeypatch.setattr(main_module, 'get_admin_notifier', lambda: object())
    monkeypatch.setattr(main_module, 'get_billing_service', lambda: LegacyBilling())
    app = main_module.create_app()

    async def run_lifespan() -> None:
        with pytest.raises(RuntimeError, match='application failed'):
            async with app.router.lifespan_context(app):
                raise RuntimeError('application failed')

    asyncio.run(run_lifespan())

    assert stop_states == [True]


def test_shutdown_and_lease_budgets_exceed_single_telegram_request() -> None:
    notifier = AdminNotifier(bot_token='token', admin_ids=['admin-1'])

    assert (
        main_module.APP_STORE_OUTBOX_SHUTDOWN_TIMEOUT_SECONDS
        > notifier.delivery_timeout_seconds
    )
    assert (
        app_store_repository_module.ADMIN_OUTBOX_LEASE_SECONDS
        > notifier.delivery_timeout_seconds
    )


def test_delivery_failure_releases_outbox_record_to_pending(notification_api) -> None:
    _, repository, gateway, _ = notification_api
    token = _register_account(repository)
    repository.apply_verified_transaction(
        AppStoreBillingService._stored_transaction(
            _transaction('tx-release-outbox', app_account_token=token),
            client_id='apple-client-001',
            app_account_token=token,
            readings=15,
            recurring=True,
        )
    )
    service = AppStoreBillingService(
        repository=repository,
        gateway=gateway,  # type: ignore[arg-type]
        billing_service=FakeBillingService(),  # type: ignore[arg-type]
    )

    class FailingNotifier:
        delivery_recipients = ('admin-1',)

        async def notify_app_store_event_to(self, recipient_id: str, **event) -> None:
            raise httpx.ConnectError('telegram offline')

    with pytest.raises(httpx.ConnectError):
        asyncio.run(service.deliver_admin_events(FailingNotifier()))  # type: ignore[arg-type]

    with closing(connect()) as conn:
        status_value = conn.execute(
            'SELECT status FROM admin_outbox WHERE dedupe_key = ?',
            ('apple-transaction:tx-release-outbox',),
        ).fetchone()['status']
    assert status_value == 'pending'


@pytest.mark.parametrize(
    ('bot_token', 'admin_ids'),
    [('', ['123']), ('token', []), ('', [])],
)
def test_missing_admin_notifier_configuration_keeps_outbox_pending(
    notification_api,
    bot_token: str,
    admin_ids: list[str],
) -> None:
    _, repository, gateway, _ = notification_api
    token = _register_account(repository)
    repository.apply_verified_transaction(
        AppStoreBillingService._stored_transaction(
            _transaction('tx-disabled-notifier', app_account_token=token),
            client_id='apple-client-001',
            app_account_token=token,
            readings=15,
            recurring=True,
        )
    )
    service = AppStoreBillingService(
        repository=repository,
        gateway=gateway,  # type: ignore[arg-type]
        billing_service=FakeBillingService(),  # type: ignore[arg-type]
    )

    with pytest.raises(RuntimeError, match='not configured'):
        asyncio.run(
            service.deliver_admin_events(
                AdminNotifier(bot_token=bot_token, admin_ids=admin_ids)
            )
        )

    with closing(connect()) as conn:
        status_value = conn.execute(
            'SELECT status FROM admin_outbox WHERE dedupe_key = ?',
            ('apple-transaction:tx-disabled-notifier',),
        ).fetchone()['status']
    assert status_value == 'pending'


def test_partial_multi_admin_retry_does_not_resend_successful_recipient(notification_api) -> None:
    _, repository, gateway, _ = notification_api
    token = _register_account(repository)
    repository.apply_verified_transaction(
        AppStoreBillingService._stored_transaction(
            _transaction('tx-partial-admins', app_account_token=token),
            client_id='apple-client-001',
            app_account_token=token,
            readings=15,
            recurring=True,
        )
    )
    service = AppStoreBillingService(
        repository=repository,
        gateway=gateway,  # type: ignore[arg-type]
        billing_service=FakeBillingService(),  # type: ignore[arg-type]
    )

    class PartialNotifier:
        delivery_recipients = ('admin-1', 'admin-2')

        def __init__(self) -> None:
            self.calls: list[str] = []
            self.fail_second = True

        async def notify_app_store_event_to(self, recipient_id: str, **event) -> None:
            self.calls.append(recipient_id)
            if recipient_id == 'admin-2' and self.fail_second:
                raise httpx.ConnectError('telegram offline')

        async def notify_app_store_event(self, **event) -> None:
            for recipient_id in self.delivery_recipients:
                await self.notify_app_store_event_to(recipient_id, **event)

    notifier = PartialNotifier()
    with pytest.raises(httpx.ConnectError):
        asyncio.run(service.deliver_admin_events(notifier))  # type: ignore[arg-type]
    notifier.fail_second = False

    assert asyncio.run(service.deliver_admin_events(notifier)) == 1  # type: ignore[arg-type]
    assert notifier.calls == ['admin-1', 'admin-2', 'admin-2']


def test_lease_heartbeat_prevents_reclaim_during_multi_admin_delivery(notification_api) -> None:
    _, repository, _, _ = notification_api
    token = _register_account(repository)
    repository.apply_verified_transaction(
        AppStoreBillingService._stored_transaction(
            _transaction('tx-heartbeat', app_account_token=token),
            client_id='apple-client-001',
            app_account_token=token,
            readings=15,
            recurring=True,
        )
    )
    event = repository.claim_admin_event(lease_seconds=60, now=NOW)
    assert event is not None

    assert repository.renew_admin_event_lease(
        event.id,
        event.lease_token,
        now=NOW + timedelta(seconds=50),
    )
    assert repository.claim_admin_event(
        lease_seconds=60,
        now=NOW + timedelta(seconds=100),
    ) is None
    reclaimed = repository.claim_admin_event(
        lease_seconds=60,
        now=NOW + timedelta(seconds=111),
    )

    assert reclaimed is not None
    assert reclaimed.id == event.id
    assert reclaimed.lease_token != event.lease_token


def test_cancellation_waits_for_recipient_checkpoint_then_releases_event(notification_api) -> None:
    _, repository, gateway, _ = notification_api
    token = _register_account(repository)
    repository.apply_verified_transaction(
        AppStoreBillingService._stored_transaction(
            _transaction('tx-cancel-checkpoint', app_account_token=token),
            client_id='apple-client-001',
            app_account_token=token,
            readings=15,
            recurring=True,
        )
    )
    service = AppStoreBillingService(
        repository=repository,
        gateway=gateway,  # type: ignore[arg-type]
        billing_service=FakeBillingService(),  # type: ignore[arg-type]
    )

    class BlockingNotifier:
        delivery_recipients = ('admin-1', 'admin-2')

        def __init__(self) -> None:
            self.started = asyncio.Event()
            self.allow_finish = asyncio.Event()

        async def notify_app_store_event_to(self, recipient_id: str, **event) -> None:
            assert recipient_id == 'admin-1'
            self.started.set()
            await self.allow_finish.wait()

    async def cancel_after_send_starts() -> None:
        notifier = BlockingNotifier()
        task = asyncio.create_task(service.deliver_admin_events(notifier))  # type: ignore[arg-type]
        await notifier.started.wait()
        task.cancel()
        notifier.allow_finish.set()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(cancel_after_send_starts())

    with closing(connect()) as conn:
        row = conn.execute(
            'SELECT status, payload FROM admin_outbox WHERE dedupe_key = ?',
            ('apple-transaction:tx-cancel-checkpoint',),
        ).fetchone()
    assert row['status'] == 'pending'
    assert json.loads(row['payload'])['_delivered_admin_ids'] == ['admin-1']

    class RetryNotifier:
        delivery_recipients = ('admin-1', 'admin-2')

        def __init__(self) -> None:
            self.calls: list[str] = []

        async def notify_app_store_event_to(self, recipient_id: str, **event) -> None:
            self.calls.append(recipient_id)

    retry_notifier = RetryNotifier()
    assert asyncio.run(service.deliver_admin_events(retry_notifier)) == 1  # type: ignore[arg-type]
    assert retry_notifier.calls == ['admin-2']


def test_first_seen_restore_enqueues_restore_event(notification_api) -> None:
    _, repository, _, _ = notification_api
    target_client = 'apple-restore-client'
    target_token = repository.get_or_create_app_account_token(target_client)
    transaction = AppStoreBillingService._stored_transaction(
        _transaction(
            'tx-first-seen-restore',
            app_account_token=target_token,
            expires_at=NOW + timedelta(days=5),
        ),
        client_id=target_client,
        app_account_token=target_token,
        readings=15,
        recurring=True,
    )

    result = repository.restore_subscription_chain(
        transaction=transaction,
        target_client_id=target_client,
        target_app_account_token=target_token,
        at=NOW,
    )
    event = repository.claim_admin_event(now=NOW)

    assert result.granted == 15
    assert event is not None
    assert event.payload['event_type'] == 'restore'


def test_unknown_verified_type_is_recorded_without_entitlement_change(notification_api) -> None:
    client, repository, gateway, notifier = notification_api
    _register_account(repository)
    gateway.notification = _notification('uuid-future', 'FUTURE_APPLE_EVENT')

    response = _post(client)

    assert response.status_code == 200
    assert repository.remaining_readings('apple-client-001') == 0
    assert notifier.events == []
    with closing(connect()) as conn:
        row = conn.execute(
            'SELECT notification_type FROM apple_notifications WHERE notification_uuid = ?',
            ('uuid-future',),
        ).fetchone()
    assert row['notification_type'] == 'FUTURE_APPLE_EVENT'


@pytest.mark.parametrize(
    ('error', 'status_code'),
    [
        (AppStoreValidationError('invalid signature'), 400),
        (AppStoreGatewayError('retryable verifier failure'), 503),
        (sqlite3.OperationalError('database is locked'), 503),
    ],
)
def test_notification_error_mapping(notification_api, error: Exception, status_code: int) -> None:
    client, _, gateway, notifier = notification_api
    gateway.notification = error

    response = _post(client)

    assert response.status_code == status_code
    assert len(notifier.events) == 1
    assert notifier.events[0]['event_type'] == 'validation_failure'
    assert 'signed-outer' not in str(notifier.events[0])


class FakeVerifier:
    def __init__(self, *, outer=None, transaction=None, renewal=None, error=None) -> None:
        self.outer = outer
        self.transaction = transaction
        self.renewal = renewal
        self.error = error
        self.calls: list[tuple[str, str]] = []

    def verify_and_decode_notification(self, signed_payload: str):
        self.calls.append(('outer', signed_payload))
        if self.error:
            raise self.error
        return self.outer

    def verify_and_decode_signed_transaction(self, signed_payload: str):
        self.calls.append(('transaction', signed_payload))
        return self.transaction

    def verify_and_decode_renewal_info(self, signed_payload: str):
        self.calls.append(('renewal', signed_payload))
        return self.renewal


class UnusedClient:
    def get_transaction_info(self, transaction_id: str):  # pragma: no cover
        raise AssertionError('notifications do not use transaction lookup')


@pytest.mark.parametrize(
    ('raw_auto_renew_status', 'expected'),
    [
        pytest.param(SimpleNamespace(value=0), False, id='enum-off'),
        pytest.param(1, True, id='int-on'),
        pytest.param(MISSING, None, id='missing'),
    ],
)
def test_gateway_decodes_auto_renew_status_from_nested_renewal_info(
    raw_auto_renew_status: object | None,
    expected: bool | None,
) -> None:
    transaction = SimpleNamespace(
        transactionId='tx-nested',
        originalTransactionId='original-weekly',
        bundleId='com.nexwit.tarot',
        productId='weekly_readings',
        environment=Environment.SANDBOX,
        appAccountToken='00000000-0000-4000-8000-000000000001',
        purchaseDate=int(NOW.timestamp() * 1000),
        expiresDate=int((NOW + timedelta(days=7)).timestamp() * 1000),
        revocationDate=None,
        type=None,
    )
    renewal_values = dict(
        originalTransactionId='original-weekly',
        productId='weekly_readings',
        environment=Environment.SANDBOX,
        appAccountToken='00000000-0000-4000-8000-000000000001',
        gracePeriodExpiresDate=None,
        isInBillingRetryPeriod=False,
        expirationIntent=None,
        signedDate=int((NOW + timedelta(seconds=7)).timestamp() * 1000),
    )
    if raw_auto_renew_status is not MISSING:
        renewal_values['autoRenewStatus'] = raw_auto_renew_status
    renewal = SimpleNamespace(**renewal_values)
    outer = SimpleNamespace(
        notificationUUID='uuid-nested',
        notificationType=SimpleNamespace(value='DID_RENEW'),
        rawNotificationType=None,
        subtype=SimpleNamespace(value='BILLING_RECOVERY'),
        rawSubtype=None,
        signedDate=int(NOW.timestamp() * 1000),
        data=SimpleNamespace(
            environment=Environment.SANDBOX,
            signedTransactionInfo='signed-transaction',
            signedRenewalInfo='signed-renewal',
        ),
    )
    production = FakeVerifier(error=AppStoreValidationError('wrong environment'))
    sandbox = FakeVerifier(outer=outer, transaction=transaction, renewal=renewal)
    gateway = AppStoreGateway.from_dependencies(
        bundle_id='com.nexwit.tarot',
        app_apple_id=123456,
        allowed_product_ids=APP_STORE_PRODUCT_IDS,
        production_client=UnusedClient(),
        sandbox_client=UnusedClient(),
        production_verifier=production,  # type: ignore[arg-type]
        sandbox_verifier=sandbox,  # type: ignore[arg-type]
    )

    verified = gateway.verify_notification('signed-outer')

    assert verified.notification_uuid == 'uuid-nested'
    assert verified.transaction is not None
    assert verified.transaction.transaction_id == 'tx-nested'
    assert verified.renewal_info is not None
    assert verified.renewal_info.auto_renew is expected
    assert verified.renewal_info.signed_date_ms == int(
        (NOW + timedelta(seconds=7)).timestamp() * 1000
    )
    assert sandbox.calls == [
        ('outer', 'signed-outer'),
        ('transaction', 'signed-transaction'),
        ('renewal', 'signed-renewal'),
    ]
