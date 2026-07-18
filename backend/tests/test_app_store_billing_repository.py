from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from src.repositories.app_store_billing import (  # noqa: E402
    AppStoreBillingRepository,
    VerifiedAppStoreTransaction,
)
from src.repositories.storage import connect, init_storage  # noqa: E402


CLIENT_ID = 'client_apple_1'
ACCOUNT_TOKEN = 'c19c7770-7230-45ce-b799-4d8f889ac25c'
NOW = datetime(2026, 7, 18, 12, 0, tzinfo=UTC)


@pytest.fixture
def repo(tmp_path: Path) -> AppStoreBillingRepository:
    init_storage(tmp_path / 'app-store-billing.db')
    return AppStoreBillingRepository()


def subscription_transaction(
    transaction_id: str = 'tx-sub-1',
    *,
    original_transaction_id: str = 'original-sub-1',
    client_id: str = CLIENT_ID,
    account_token: str = ACCOUNT_TOKEN,
    expires_at: datetime | None = None,
) -> VerifiedAppStoreTransaction:
    return VerifiedAppStoreTransaction(
        transaction_id=transaction_id,
        original_transaction_id=original_transaction_id,
        client_id=client_id,
        app_account_token=account_token,
        product_id='weekly_readings',
        product_type='subscription',
        readings=15,
        purchased_at=NOW,
        expires_at=expires_at or NOW + timedelta(days=7),
        environment='Sandbox',
        signed_transaction=f'signed-{transaction_id}',
    )


def consumable_transaction(
    transaction_id: str,
    readings: int,
    *,
    client_id: str = CLIENT_ID,
    account_token: str = ACCOUNT_TOKEN,
) -> VerifiedAppStoreTransaction:
    return VerifiedAppStoreTransaction(
        transaction_id=transaction_id,
        original_transaction_id=transaction_id,
        client_id=client_id,
        app_account_token=account_token,
        product_id=f'one{readings}_readings',
        product_type='consumable',
        readings=readings,
        purchased_at=NOW,
        expires_at=None,
        environment='Sandbox',
        signed_transaction=f'signed-{transaction_id}',
    )


def test_apply_transaction_is_idempotent_and_grants_once(
    repo: AppStoreBillingRepository,
) -> None:
    transaction = subscription_transaction()

    first = repo.apply_verified_transaction(transaction)
    replay = repo.apply_verified_transaction(transaction)

    assert first.granted == 15
    assert first.replayed is False
    assert replay.granted == 0
    assert replay.replayed is True
    assert repo.remaining_readings(CLIENT_ID, at=NOW) == 15

    with connect() as conn:
        assert conn.execute('SELECT COUNT(*) FROM apple_transactions').fetchone()[0] == 1
        assert conn.execute('SELECT COUNT(*) FROM entitlement_lots').fetchone()[0] == 1
        assert conn.execute('SELECT COUNT(*) FROM admin_outbox').fetchone()[0] == 1


@pytest.mark.parametrize(
    ('changes', 'error_match'),
    [
        ({'client_id': 'client_apple_2'}, 'client'),
        (
            {'app_account_token': 'a4896aa5-7b84-4df2-9558-bbfde65bad25'},
            'app account token',
        ),
        ({'product_id': 'monthly_readings'}, 'product'),
        ({'original_transaction_id': 'original-sub-other'}, 'original transaction'),
    ],
)
def test_replay_rejects_conflicting_ownership_or_payload(
    repo: AppStoreBillingRepository,
    changes: dict[str, str],
    error_match: str,
) -> None:
    original = subscription_transaction()
    repo.apply_verified_transaction(original)
    conflicting = VerifiedAppStoreTransaction(
        **{**original.__dict__, **changes},
    )

    with pytest.raises(ValueError, match=error_match):
        repo.apply_verified_transaction(conflicting)

    assert repo.remaining_readings(CLIENT_ID, at=NOW) == 15
    if changes.get('client_id'):
        assert repo.remaining_readings(changes['client_id'], at=NOW) == 0
    with connect() as conn:
        assert conn.execute('SELECT COUNT(*) FROM apple_transactions').fetchone()[0] == 1
        assert conn.execute('SELECT COUNT(*) FROM entitlement_lots').fetchone()[0] == 1
        assert conn.execute('SELECT COUNT(*) FROM admin_outbox').fetchone()[0] == 1


def test_subscription_lot_uses_signed_expiry(repo: AppStoreBillingRepository) -> None:
    signed_expiry = NOW + timedelta(hours=3, minutes=17)

    repo.apply_verified_transaction(
        subscription_transaction(expires_at=signed_expiry),
    )

    with connect() as conn:
        row = conn.execute(
            'SELECT expires_at FROM entitlement_lots WHERE source_transaction_id = ?',
            ('tx-sub-1',),
        ).fetchone()

    assert row is not None
    assert row['expires_at'] == signed_expiry.isoformat()
    assert repo.remaining_readings(CLIENT_ID, at=signed_expiry - timedelta(seconds=1)) == 15
    assert repo.remaining_readings(CLIENT_ID, at=signed_expiry) == 0


def test_renewal_transaction_grants_exactly_once(
    repo: AppStoreBillingRepository,
) -> None:
    repo.apply_verified_transaction(subscription_transaction())
    renewal = subscription_transaction(
        'tx-sub-renewal',
        expires_at=NOW + timedelta(days=14),
    )

    first_renewal = repo.apply_verified_transaction(renewal)
    replayed_renewal = repo.apply_verified_transaction(renewal)

    assert first_renewal.granted == 15
    assert replayed_renewal.granted == 0
    assert repo.remaining_readings(CLIENT_ID, at=NOW) == 30
    with connect() as conn:
        chain_count = conn.execute(
            'SELECT COUNT(*) FROM apple_subscription_chains',
        ).fetchone()[0]
    assert chain_count == 1


def test_consumable_lots_stack_without_expiry(
    repo: AppStoreBillingRepository,
) -> None:
    repo.apply_verified_transaction(consumable_transaction('tx-pack-10', 10))
    repo.apply_verified_transaction(consumable_transaction('tx-pack-40', 40))

    assert repo.remaining_readings(CLIENT_ID, at=NOW + timedelta(days=3650)) == 50
    with connect() as conn:
        rows = conn.execute(
            '''
            SELECT granted, remaining, expires_at
            FROM entitlement_lots
            ORDER BY id
            ''',
        ).fetchall()

    assert [(row['granted'], row['remaining'], row['expires_at']) for row in rows] == [
        (10, 10, None),
        (40, 40, None),
    ]


def test_account_conflict_rolls_back_entire_apply(
    repo: AppStoreBillingRepository,
) -> None:
    repo.apply_verified_transaction(consumable_transaction('tx-owner', 10))

    conflicting = consumable_transaction(
        'tx-conflict',
        40,
        client_id='client_apple_2',
        account_token=ACCOUNT_TOKEN,
    )
    with pytest.raises(ValueError, match='app account token'):
        repo.apply_verified_transaction(conflicting)

    with connect() as conn:
        assert conn.execute(
            'SELECT COUNT(*) FROM apple_transactions WHERE transaction_id = ?',
            ('tx-conflict',),
        ).fetchone()[0] == 0
        assert conn.execute(
            'SELECT COUNT(*) FROM entitlement_lots WHERE source_transaction_id = ?',
            ('tx-conflict',),
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM admin_outbox WHERE dedupe_key = 'apple-transaction:tx-conflict'",
        ).fetchone()[0] == 0


def test_rejects_subscription_without_signed_expiry(
    repo: AppStoreBillingRepository,
) -> None:
    transaction = subscription_transaction()
    transaction = VerifiedAppStoreTransaction(
        **{**transaction.__dict__, 'expires_at': None},
    )

    with pytest.raises(ValueError, match='expiry'):
        repo.apply_verified_transaction(transaction)

    with connect() as conn:
        assert conn.execute('SELECT COUNT(*) FROM apple_transactions').fetchone()[0] == 0
