from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from src.repositories.storage import connect


ProductType = Literal['subscription', 'consumable']


@dataclass(frozen=True)
class VerifiedAppStoreTransaction:
    transaction_id: str
    original_transaction_id: str
    client_id: str
    app_account_token: str
    product_id: str
    product_type: ProductType
    readings: int
    purchased_at: datetime | str | int
    expires_at: datetime | str | int | None
    environment: str
    signed_transaction: str


@dataclass(frozen=True)
class ApplyTransactionResult:
    transaction_id: str
    granted: int
    replayed: bool
    remaining: int


@dataclass(frozen=True)
class AppleEntitlementSnapshot:
    remaining: int
    product_id: str
    product_type: ProductType
    starts_at: str
    expires_at: str | None


class AppStoreBillingRepository:
    def get_or_create_app_account_token(self, client_id: str) -> str:
        normalized_client_id = client_id.strip()
        if not normalized_client_id:
            raise ValueError('client ID is required')
        with closing(connect()) as conn:
            try:
                conn.execute('BEGIN IMMEDIATE')
                row = conn.execute(
                    'SELECT app_account_token FROM apple_app_accounts WHERE client_id = ?',
                    (normalized_client_id,),
                ).fetchone()
                if row is None:
                    token = str(uuid4())
                    conn.execute(
                        '''
                        INSERT INTO apple_app_accounts (client_id, app_account_token, created_at)
                        VALUES (?, ?, ?)
                        ''',
                        (normalized_client_id, token, _now_iso()),
                    )
                else:
                    token = str(row['app_account_token'])
                conn.commit()
                return token
            except Exception:
                conn.rollback()
                raise

    def client_id_for_app_account_token(self, app_account_token: str) -> str | None:
        normalized = app_account_token.strip()
        if not normalized:
            return None
        with closing(connect()) as conn:
            row = conn.execute(
                'SELECT client_id FROM apple_app_accounts WHERE app_account_token = ?',
                (normalized,),
            ).fetchone()
        return str(row['client_id']) if row is not None else None

    def apply_verified_transaction(
        self,
        transaction: VerifiedAppStoreTransaction,
    ) -> ApplyTransactionResult:
        values = _validated_values(transaction)
        with closing(connect()) as conn:
            try:
                conn.execute('BEGIN IMMEDIATE')
                existing = conn.execute(
                    '''
                    SELECT
                        original_transaction_id,
                        client_id,
                        app_account_token,
                        product_id,
                        product_type,
                        readings,
                        purchased_at,
                        expires_at,
                        environment,
                        signed_transaction
                    FROM apple_transactions
                    WHERE transaction_id = ?
                    ''',
                    (transaction.transaction_id,),
                ).fetchone()
                if existing is not None:
                    _validate_replay(existing, transaction, values)
                    remaining = _remaining_readings(conn, str(existing['client_id']), _now_iso())
                    conn.commit()
                    return ApplyTransactionResult(
                        transaction_id=transaction.transaction_id,
                        granted=0,
                        replayed=True,
                        remaining=remaining,
                    )

                created_at = _now_iso()
                _ensure_app_account(conn, transaction, created_at)
                if transaction.product_type == 'subscription':
                    _ensure_subscription_chain(conn, transaction, created_at)

                conn.execute(
                    '''
                    INSERT INTO apple_transactions (
                        transaction_id,
                        original_transaction_id,
                        client_id,
                        app_account_token,
                        product_id,
                        product_type,
                        readings,
                        purchased_at,
                        expires_at,
                        environment,
                        signed_transaction,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (
                        transaction.transaction_id,
                        transaction.original_transaction_id,
                        transaction.client_id,
                        transaction.app_account_token,
                        transaction.product_id,
                        transaction.product_type,
                        transaction.readings,
                        values.purchased_at,
                        values.expires_at,
                        transaction.environment,
                        transaction.signed_transaction,
                        created_at,
                    ),
                )
                conn.execute(
                    '''
                    INSERT INTO entitlement_lots (
                        client_id,
                        source_transaction_id,
                        original_transaction_id,
                        product_id,
                        product_type,
                        granted,
                        remaining,
                        expires_at,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''',
                    (
                        transaction.client_id,
                        transaction.transaction_id,
                        transaction.original_transaction_id,
                        transaction.product_id,
                        transaction.product_type,
                        transaction.readings,
                        transaction.readings,
                        values.expires_at,
                        created_at,
                    ),
                )
                conn.execute(
                    '''
                    INSERT INTO admin_outbox (
                        event_type,
                        dedupe_key,
                        payload,
                        status,
                        created_at
                    ) VALUES (?, ?, ?, 'pending', ?)
                    ''',
                    (
                        'apple_transaction_applied',
                        f'apple-transaction:{transaction.transaction_id}',
                        json.dumps(
                            {
                                'client_id': transaction.client_id,
                                'transaction_id': transaction.transaction_id,
                                'original_transaction_id': transaction.original_transaction_id,
                                'product_id': transaction.product_id,
                                'product_type': transaction.product_type,
                                'readings': transaction.readings,
                                'expires_at': values.expires_at,
                                'environment': transaction.environment,
                            },
                            ensure_ascii=False,
                            separators=(',', ':'),
                            sort_keys=True,
                        ),
                        created_at,
                    ),
                )
                remaining = _remaining_readings(conn, transaction.client_id, _now_iso())
                conn.commit()
            except Exception:
                conn.rollback()
                raise

        return ApplyTransactionResult(
            transaction_id=transaction.transaction_id,
            granted=transaction.readings,
            replayed=False,
            remaining=remaining,
        )

    def remaining_readings(
        self,
        client_id: str,
        *,
        at: datetime | str | int | None = None,
    ) -> int:
        at_iso = _timestamp_to_iso(at) if at is not None else _now_iso()
        with closing(connect()) as conn:
            return _remaining_readings(conn, client_id, at_iso)

    def entitlement_snapshot(
        self,
        client_id: str,
        *,
        at: datetime | str | int | None = None,
    ) -> AppleEntitlementSnapshot | None:
        at_iso = _timestamp_to_iso(at) if at is not None else _now_iso()
        with closing(connect()) as conn:
            remaining = _remaining_readings(conn, client_id, at_iso)
            if remaining <= 0:
                return None
            row = conn.execute(
                '''
                SELECT product_id, product_type, created_at, expires_at
                FROM entitlement_lots
                WHERE client_id = ?
                  AND remaining > 0
                  AND (expires_at IS NULL OR expires_at > ?)
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                ''',
                (client_id, at_iso),
            ).fetchone()
        if row is None:  # pragma: no cover - same-transaction defensive case
            return None
        return AppleEntitlementSnapshot(
            remaining=remaining,
            product_id=str(row['product_id']),
            product_type=str(row['product_type']),  # type: ignore[arg-type]
            starts_at=str(row['created_at']),
            expires_at=str(row['expires_at']) if row['expires_at'] is not None else None,
        )

    def consume_reading(
        self,
        client_id: str,
        *,
        at: datetime | str | int | None = None,
    ) -> bool:
        at_iso = _timestamp_to_iso(at) if at is not None else _now_iso()
        with closing(connect()) as conn:
            try:
                conn.execute('BEGIN IMMEDIATE')
                row = conn.execute(
                    '''
                    SELECT id
                    FROM entitlement_lots
                    WHERE client_id = ?
                      AND remaining > 0
                      AND (expires_at IS NULL OR expires_at > ?)
                    ORDER BY
                      CASE WHEN expires_at IS NULL THEN 1 ELSE 0 END,
                      expires_at ASC,
                      id ASC
                    LIMIT 1
                    ''',
                    (client_id, at_iso),
                ).fetchone()
                if row is None:
                    conn.commit()
                    return False
                updated = conn.execute(
                    '''
                    UPDATE entitlement_lots
                    SET remaining = remaining - 1
                    WHERE id = ? AND remaining > 0
                    ''',
                    (int(row['id']),),
                ).rowcount
                conn.commit()
                return updated == 1
            except Exception:
                conn.rollback()
                raise

    def restore_subscription_chain(
        self,
        *,
        transaction: VerifiedAppStoreTransaction,
        target_client_id: str,
        target_app_account_token: str,
        at: datetime | str | int | None = None,
    ) -> ApplyTransactionResult:
        if transaction.product_type != 'subscription':
            raise ValueError('consumable purchases cannot be restored')
        values = _validated_values(transaction)
        at_iso = _timestamp_to_iso(at) if at is not None else _now_iso()
        if values.expires_at is None or values.expires_at <= at_iso:
            raise ValueError('subscription must be active to restore')

        normalized_client_id = target_client_id.strip()
        normalized_token = target_app_account_token.strip()
        if not normalized_client_id or not normalized_token:
            raise ValueError('restore target account is required')

        with closing(connect()) as lookup_conn:
            existing = lookup_conn.execute(
                'SELECT 1 FROM apple_transactions WHERE transaction_id = ?',
                (transaction.transaction_id,),
            ).fetchone()
        if existing is None:
            return self.apply_verified_transaction(
                replace(
                    transaction,
                    client_id=normalized_client_id,
                    app_account_token=normalized_token,
                )
            )

        with closing(connect()) as conn:
            try:
                conn.execute('BEGIN IMMEDIATE')
                stored = conn.execute(
                    '''
                    SELECT
                        original_transaction_id, client_id, app_account_token,
                        product_id, product_type, readings, purchased_at,
                        expires_at, environment, signed_transaction
                    FROM apple_transactions
                    WHERE transaction_id = ?
                    ''',
                    (transaction.transaction_id,),
                ).fetchone()
                if stored is None:  # pragma: no cover - concurrent defensive case
                    raise RuntimeError('Apple transaction disappeared during restore')
                _validate_replay(stored, transaction, values)
                _ensure_account_pair(
                    conn,
                    normalized_client_id,
                    normalized_token,
                    _now_iso(),
                )
                chain = conn.execute(
                    '''
                    SELECT product_id, environment
                    FROM apple_subscription_chains
                    WHERE original_transaction_id = ?
                    ''',
                    (transaction.original_transaction_id,),
                ).fetchone()
                if chain is None:
                    raise ValueError('subscription chain was not found')
                if (
                    str(chain['product_id']) != transaction.product_id
                    or str(chain['environment']) != transaction.environment
                ):
                    raise ValueError('subscription chain payload does not match')

                conn.execute(
                    '''
                    UPDATE apple_subscription_chains
                    SET client_id = ?, app_account_token = ?
                    WHERE original_transaction_id = ?
                    ''',
                    (
                        normalized_client_id,
                        normalized_token,
                        transaction.original_transaction_id,
                    ),
                )
                conn.execute(
                    '''
                    UPDATE entitlement_lots
                    SET client_id = ?
                    WHERE original_transaction_id = ?
                      AND product_type = 'subscription'
                      AND expires_at > ?
                    ''',
                    (normalized_client_id, transaction.original_transaction_id, at_iso),
                )
                conn.execute(
                    '''
                    INSERT OR IGNORE INTO admin_outbox (
                        event_type, dedupe_key, payload, status, created_at
                    ) VALUES ('apple_subscription_restored', ?, ?, 'pending', ?)
                    ''',
                    (
                        f'apple-restore:{transaction.original_transaction_id}:{normalized_client_id}',
                        json.dumps(
                            {
                                'client_id': normalized_client_id,
                                'original_transaction_id': transaction.original_transaction_id,
                                'product_id': transaction.product_id,
                            },
                            ensure_ascii=False,
                            separators=(',', ':'),
                            sort_keys=True,
                        ),
                        _now_iso(),
                    ),
                )
                remaining = _remaining_readings(conn, normalized_client_id, at_iso)
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return ApplyTransactionResult(
            transaction_id=transaction.transaction_id,
            granted=0,
            replayed=True,
            remaining=remaining,
        )


@dataclass(frozen=True)
class _ValidatedValues:
    purchased_at: str
    expires_at: str | None


def _validated_values(transaction: VerifiedAppStoreTransaction) -> _ValidatedValues:
    required_text = {
        'transaction ID': transaction.transaction_id,
        'original transaction ID': transaction.original_transaction_id,
        'client ID': transaction.client_id,
        'app account token': transaction.app_account_token,
        'product ID': transaction.product_id,
        'environment': transaction.environment,
        'signed transaction': transaction.signed_transaction,
    }
    for field_name, value in required_text.items():
        if not value.strip():
            raise ValueError(f'{field_name} is required')
    if transaction.product_type not in ('subscription', 'consumable'):
        raise ValueError('unsupported Apple product type')
    if transaction.readings <= 0:
        raise ValueError('readings must be positive')

    purchased_at = _timestamp_to_iso(transaction.purchased_at)
    if transaction.product_type == 'subscription':
        if transaction.expires_at is None:
            raise ValueError('subscription expiry is required')
        expires_at = _timestamp_to_iso(transaction.expires_at)
        if expires_at <= purchased_at:
            raise ValueError('subscription expiry must be after purchase')
    else:
        if transaction.expires_at is not None:
            raise ValueError('consumable expiry must be empty')
        expires_at = None
    return _ValidatedValues(purchased_at=purchased_at, expires_at=expires_at)


def _ensure_app_account(
    conn: sqlite3.Connection,
    transaction: VerifiedAppStoreTransaction,
    created_at: str,
) -> None:
    _ensure_account_pair(
        conn,
        transaction.client_id,
        transaction.app_account_token,
        created_at,
    )


def _ensure_account_pair(
    conn: sqlite3.Connection,
    client_id: str,
    app_account_token: str,
    created_at: str,
) -> None:
    conn.execute(
        '''
        INSERT OR IGNORE INTO apple_app_accounts (
            client_id,
            app_account_token,
            created_at
        ) VALUES (?, ?, ?)
        ''',
        (client_id, app_account_token, created_at),
    )
    row = conn.execute(
        '''
        SELECT client_id, app_account_token
        FROM apple_app_accounts
        WHERE client_id = ? OR app_account_token = ?
        ''',
        (client_id, app_account_token),
    ).fetchall()
    if len(row) != 1:
        raise ValueError('app account token is already assigned to another client')
    account = row[0]
    if (
        str(account['client_id']) != client_id
        or str(account['app_account_token']) != app_account_token
    ):
        raise ValueError('app account token is already assigned to another client')


def _validate_replay(
    existing: sqlite3.Row,
    transaction: VerifiedAppStoreTransaction,
    values: _ValidatedValues,
) -> None:
    expected = (
        ('client', str(existing['client_id']), transaction.client_id),
        (
            'app account token',
            str(existing['app_account_token']),
            transaction.app_account_token,
        ),
        ('product', str(existing['product_id']), transaction.product_id),
        (
            'original transaction',
            str(existing['original_transaction_id']),
            transaction.original_transaction_id,
        ),
        ('product type', str(existing['product_type']), transaction.product_type),
        ('readings', int(existing['readings']), transaction.readings),
        ('purchase timestamp', str(existing['purchased_at']), values.purchased_at),
        ('expiry', existing['expires_at'], values.expires_at),
        ('environment', str(existing['environment']), transaction.environment),
    )
    for field_name, stored_value, replayed_value in expected:
        if stored_value != replayed_value:
            raise ValueError(f'Apple transaction replay has conflicting {field_name}')


def _ensure_subscription_chain(
    conn: sqlite3.Connection,
    transaction: VerifiedAppStoreTransaction,
    created_at: str,
) -> None:
    conn.execute(
        '''
        INSERT OR IGNORE INTO apple_subscription_chains (
            original_transaction_id,
            client_id,
            app_account_token,
            product_id,
            environment,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        ''',
        (
            transaction.original_transaction_id,
            transaction.client_id,
            transaction.app_account_token,
            transaction.product_id,
            transaction.environment,
            created_at,
        ),
    )
    row = conn.execute(
        '''
        SELECT client_id, app_account_token, environment
        FROM apple_subscription_chains
        WHERE original_transaction_id = ?
        ''',
        (transaction.original_transaction_id,),
    ).fetchone()
    if row is None:  # pragma: no cover - defensive
        raise RuntimeError('failed to persist Apple subscription chain')
    if (
        str(row['client_id']) != transaction.client_id
        or str(row['app_account_token']) != transaction.app_account_token
        or str(row['environment']) != transaction.environment
    ):
        raise ValueError('subscription chain belongs to another app account')


def _remaining_readings(
    conn: sqlite3.Connection,
    client_id: str,
    at_iso: str,
) -> int:
    row = conn.execute(
        '''
        SELECT COALESCE(SUM(remaining), 0) AS remaining
        FROM entitlement_lots
        WHERE client_id = ?
          AND remaining > 0
          AND (expires_at IS NULL OR expires_at > ?)
        ''',
        (client_id, at_iso),
    ).fetchone()
    return int(row['remaining']) if row is not None else 0


def _timestamp_to_iso(value: datetime | str | int) -> str:
    if isinstance(value, datetime):
        timestamp = value
    elif isinstance(value, int):
        timestamp = datetime.fromtimestamp(value / 1000, tz=UTC)
    else:
        normalized = value.strip().replace('Z', '+00:00')
        if not normalized:
            raise ValueError('timestamp is required')
        try:
            timestamp = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError('invalid timestamp') from exc
    if timestamp.tzinfo is None:
        raise ValueError('timestamp must include a timezone')
    return timestamp.astimezone(UTC).isoformat()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
