from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

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


def test_replay_accepts_a_fresh_apple_signature_for_the_same_transaction(
    repo: AppStoreBillingRepository,
) -> None:
    original = subscription_transaction()
    repo.apply_verified_transaction(original)
    resigned = VerifiedAppStoreTransaction(
        **{**original.__dict__, 'signed_transaction': 'fresh-apple-jws'},
    )

    replay = repo.apply_verified_transaction(resigned)

    assert replay.replayed is True
    assert replay.granted == 0
    assert repo.remaining_readings(CLIENT_ID, at=NOW) == 15
    with connect() as conn:
        row = conn.execute(
            'SELECT signed_transaction FROM apple_transactions WHERE transaction_id = ?',
            (original.transaction_id,),
        ).fetchone()
        assert row['signed_transaction'] == original.signed_transaction


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


def test_account_token_is_stable_canonical_uuid(repo: AppStoreBillingRepository) -> None:
    first = repo.get_or_create_app_account_token(CLIENT_ID)
    second = repo.get_or_create_app_account_token(CLIENT_ID)

    assert first == second
    assert str(UUID(first)) == first


def test_consume_reading_uses_active_lots_atomically(repo: AppStoreBillingRepository) -> None:
    repo.apply_verified_transaction(consumable_transaction('tx-pack-10', 10))

    assert repo.consume_reading(CLIENT_ID, at=NOW) is True
    assert repo.remaining_readings(CLIENT_ID, at=NOW) == 9
    for _ in range(9):
        assert repo.consume_reading(CLIENT_ID, at=NOW) is True
    assert repo.consume_reading(CLIENT_ID, at=NOW) is False


def test_restore_transfers_only_active_subscription_chain(
    repo: AppStoreBillingRepository,
) -> None:
    old_client = 'client_apple_old'
    old_token = repo.get_or_create_app_account_token(old_client)
    new_client = 'client_apple_new'
    new_token = repo.get_or_create_app_account_token(new_client)
    transaction = subscription_transaction(
        client_id=old_client,
        account_token=old_token,
        expires_at=NOW + timedelta(days=3),
    )
    repo.apply_verified_transaction(transaction)

    result = repo.restore_subscription_chain(
        transaction=transaction,
        target_client_id=new_client,
        target_app_account_token=new_token,
        at=NOW,
    )

    assert result.replayed is True
    assert result.granted == 0
    assert repo.remaining_readings(old_client, at=NOW) == 0
    assert repo.remaining_readings(new_client, at=NOW) == 15


def test_restore_rejects_consumable_and_expired_subscription(
    repo: AppStoreBillingRepository,
) -> None:
    target_client = 'client_apple_restore'
    target_token = repo.get_or_create_app_account_token(target_client)

    with pytest.raises(ValueError, match='consumable'):
        repo.restore_subscription_chain(
            transaction=consumable_transaction('tx-pack-restore', 10),
            target_client_id=target_client,
            target_app_account_token=target_token,
            at=NOW,
        )

    expired = subscription_transaction(expires_at=NOW - timedelta(seconds=1))
    expired = VerifiedAppStoreTransaction(
        **{**expired.__dict__, 'purchased_at': NOW - timedelta(days=1)},
    )
    with pytest.raises(ValueError, match='active'):
        repo.restore_subscription_chain(
            transaction=expired,
            target_client_id=target_client,
            target_app_account_token=target_token,
            at=NOW,
        )
