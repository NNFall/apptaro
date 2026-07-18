from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import closing
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import uuid4

from src.repositories.storage import connect


ProductType = Literal['subscription', 'consumable']

ADMIN_OUTBOX_LEASE_SECONDS = 60
APPLE_VALIDATION_FAILURE_WINDOW_SECONDS = 5 * 60
APPLE_VALIDATION_FAILURE_RETENTION_SECONDS = 24 * 60 * 60


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


@dataclass(frozen=True)
class ProcessNotificationResult:
    notification_uuid: str
    duplicate: bool


@dataclass(frozen=True)
class AdminOutboxRecord:
    id: int
    event_type: str
    payload: dict[str, object]
    lease_token: str


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
        *,
        admin_event_type: str = 'purchase',
    ) -> ApplyTransactionResult:
        with closing(connect()) as conn:
            try:
                conn.execute('BEGIN IMMEDIATE')
                result = _apply_verified_transaction(
                    conn,
                    transaction,
                    enqueue_admin=True,
                    admin_event_type=admin_event_type,
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return result

    def subscription_owner(self, original_transaction_id: str) -> str | None:
        normalized = original_transaction_id.strip()
        if not normalized:
            return None
        with closing(connect()) as conn:
            row = conn.execute(
                '''
                SELECT client_id
                FROM apple_subscription_chains
                WHERE original_transaction_id = ?
                ''',
                (normalized,),
            ).fetchone()
        return str(row['client_id']) if row is not None else None

    def process_notification(
        self,
        *,
        notification_uuid: str,
        notification_type: str,
        subtype: str | None,
        signed_payload: str,
        transaction: VerifiedAppStoreTransaction | None,
        lifecycle_action: str,
        original_transaction_id: str | None,
        transaction_id: str | None,
        grace_expires_at: datetime | str | int | None,
        lifecycle_cutoff_at: datetime | str | int | None,
        admin_event: dict[str, object] | None,
    ) -> ProcessNotificationResult:
        normalized_uuid = notification_uuid.strip()
        normalized_type = notification_type.strip()
        if not normalized_uuid or not normalized_type or not signed_payload.strip():
            raise ValueError('verified Apple notification fields are required')

        with closing(connect()) as conn:
            try:
                conn.execute('BEGIN IMMEDIATE')
                _ensure_terminal_event_table(conn)
                existing = conn.execute(
                    'SELECT 1 FROM apple_notifications WHERE notification_uuid = ?',
                    (normalized_uuid,),
                ).fetchone()
                if existing is not None:
                    conn.commit()
                    return ProcessNotificationResult(normalized_uuid, True)

                source_id = (transaction_id or '').strip()
                duplicate_event = False
                if source_id:
                    duplicate_event = conn.execute(
                        '''
                        SELECT 1
                        FROM apple_notifications
                        WHERE transaction_id = ?
                          AND notification_type = ?
                          AND COALESCE(subtype, '') = COALESCE(?, '')
                        LIMIT 1
                        ''',
                        (source_id, normalized_type, subtype),
                    ).fetchone() is not None

                transaction_result: ApplyTransactionResult | None = None
                if transaction is not None:
                    transaction_result = _apply_verified_transaction(
                        conn,
                        transaction,
                        enqueue_admin=False,
                        admin_event_type='purchase',
                    )

                chain_id = (original_transaction_id or '').strip()
                if lifecycle_action == 'grace':
                    if not chain_id or grace_expires_at is None:
                        raise ValueError('Apple grace period is missing subscription data')
                    grace_iso = _timestamp_to_iso(grace_expires_at)
                    if source_id:
                        conn.execute(
                            '''
                            UPDATE entitlement_lots
                            SET expires_at = ?
                            WHERE source_transaction_id = ?
                              AND original_transaction_id = ?
                              AND product_type = 'subscription'
                              AND remaining > 0
                            ''',
                            (grace_iso, source_id, chain_id),
                        )
                    else:
                        conn.execute(
                            '''
                            UPDATE entitlement_lots
                            SET expires_at = ?
                            WHERE id = (
                                SELECT id
                                FROM entitlement_lots
                                WHERE original_transaction_id = ?
                                  AND product_type = 'subscription'
                                  AND remaining > 0
                                ORDER BY expires_at DESC, id DESC
                                LIMIT 1
                            )
                            ''',
                            (grace_iso, chain_id),
                        )
                elif lifecycle_action in {'expire', 'billing_retry'}:
                    if not chain_id:
                        raise ValueError('Apple lifecycle event is missing subscription chain')
                    if source_id:
                        conn.execute(
                            '''
                            UPDATE entitlement_lots
                            SET remaining = 0
                            WHERE source_transaction_id = ?
                              AND original_transaction_id = ?
                              AND product_type = 'subscription'
                            ''',
                            (source_id, chain_id),
                        )
                    elif lifecycle_cutoff_at is not None:
                        cutoff_iso = _timestamp_to_iso(lifecycle_cutoff_at)
                        conn.execute(
                            '''
                            UPDATE entitlement_lots
                            SET remaining = 0
                            WHERE original_transaction_id = ?
                              AND product_type = 'subscription'
                              AND expires_at <= ?
                            ''',
                            (chain_id, cutoff_iso),
                        )
                    else:
                        raise ValueError('Apple lifecycle event is missing ordering data')
                elif lifecycle_action in {'refund', 'revoke'}:
                    if not source_id:
                        raise ValueError('Apple revocation event is missing transaction id')
                    terminal_cutoff = (
                        _timestamp_to_iso(lifecycle_cutoff_at)
                        if lifecycle_cutoff_at is not None
                        else None
                    )
                    conn.execute(
                        '''
                        INSERT OR IGNORE INTO apple_terminal_events (
                            notification_uuid, transaction_id,
                            original_transaction_id, terminal_type,
                            cutoff_at, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        ''',
                        (
                            normalized_uuid,
                            source_id,
                            chain_id or source_id,
                            normalized_type,
                            terminal_cutoff,
                            _now_iso(),
                        ),
                    )
                    conn.execute(
                        'UPDATE entitlement_lots SET remaining = 0 WHERE source_transaction_id = ?',
                        (source_id,),
                    )
                elif lifecycle_action not in {'none', 'grant'}:
                    raise ValueError(f'unsupported Apple notification action: {lifecycle_action}')

                created_at = _now_iso()
                conn.execute(
                    '''
                    INSERT INTO apple_notifications (
                        notification_uuid, notification_type, subtype,
                        transaction_id, signed_payload, processed_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    ''',
                    (
                        normalized_uuid,
                        normalized_type,
                        subtype,
                        source_id or None,
                        signed_payload,
                        created_at,
                    ),
                )
                should_enqueue_admin = (
                    admin_event is not None
                    and not duplicate_event
                    and not (
                        lifecycle_action == 'grant'
                        and transaction_result is not None
                        and (transaction_result.replayed or transaction_result.granted == 0)
                    )
                )
                if should_enqueue_admin:
                    conn.execute(
                        '''
                        INSERT INTO admin_outbox (
                            event_type, dedupe_key, payload, status, created_at
                        ) VALUES ('apple_notification', ?, ?, 'pending', ?)
                        ''',
                        (
                            f'apple-notification:{normalized_uuid}',
                            json.dumps(
                                admin_event,
                                ensure_ascii=False,
                                separators=(',', ':'),
                                sort_keys=True,
                            ),
                            created_at,
                        ),
                    )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
        return ProcessNotificationResult(normalized_uuid, False)

    def enqueue_validation_failure(
        self,
        signed_payload: str,
        detail: str,
        *,
        now: datetime | str | int | None = None,
    ) -> bool:
        fingerprint = hashlib.sha256(signed_payload.encode('utf-8')).hexdigest()
        created_at = _timestamp_to_iso(now) if now is not None else _now_iso()
        created_datetime = datetime.fromisoformat(created_at).astimezone(UTC)
        window_epoch = (
            int(created_datetime.timestamp())
            // APPLE_VALIDATION_FAILURE_WINDOW_SECONDS
            * APPLE_VALIDATION_FAILURE_WINDOW_SECONDS
        )
        window_start = datetime.fromtimestamp(window_epoch, tz=UTC).isoformat()
        retention_cutoff = (
            created_datetime - timedelta(seconds=APPLE_VALIDATION_FAILURE_RETENTION_SECONDS)
        ).isoformat()
        category = hashlib.sha256(detail.encode('utf-8')).hexdigest()[:16]
        bucket_key = f'{category}:{window_epoch}'
        payload = json.dumps(
            {
                'event_type': 'validation_failure',
                'client_id': '',
                'product_id': '',
                'transaction_id': '',
                'notification_uuid': '',
                'detail': detail,
            },
            ensure_ascii=False,
            separators=(',', ':'),
            sort_keys=True,
        )
        with closing(connect()) as conn:
            try:
                conn.execute('BEGIN IMMEDIATE')
                _ensure_validation_failure_table(conn)
                conn.execute(
                    '''
                    DELETE FROM admin_outbox
                    WHERE event_type = 'apple_validation_failure'
                      AND (
                            created_at < ?
                            OR dedupe_key NOT LIKE 'apple-validation-window:%'
                      )
                    ''',
                    (retention_cutoff,),
                )
                conn.execute(
                    'DELETE FROM apple_validation_failure_buckets WHERE window_start < ?',
                    (retention_cutoff,),
                )
                inserted = conn.execute(
                    '''
                    INSERT OR IGNORE INTO apple_validation_failure_buckets (
                        bucket_key, category, window_start, attempt_count,
                        first_fingerprint, first_seen_at, last_seen_at
                    ) VALUES (?, ?, ?, 1, ?, ?, ?)
                    ''',
                    (
                        bucket_key,
                        category,
                        window_start,
                        fingerprint,
                        created_at,
                        created_at,
                    ),
                ).rowcount == 1
                if not inserted:
                    conn.execute(
                        '''
                        UPDATE apple_validation_failure_buckets
                        SET attempt_count = attempt_count + 1,
                            last_seen_at = ?
                        WHERE bucket_key = ?
                        ''',
                        (created_at, bucket_key),
                    )
                else:
                    conn.execute(
                        '''
                        INSERT INTO admin_outbox (
                            event_type, dedupe_key, payload, status, created_at
                        ) VALUES ('apple_validation_failure', ?, ?, 'pending', ?)
                        ''',
                        (
                            f'apple-validation-window:{bucket_key}',
                            payload,
                            created_at,
                        ),
                    )
                conn.commit()
                return inserted
            except Exception:
                conn.rollback()
                raise

    def claim_admin_event(
        self,
        *,
        lease_seconds: int = ADMIN_OUTBOX_LEASE_SECONDS,
        now: datetime | str | int | None = None,
    ) -> AdminOutboxRecord | None:
        if lease_seconds <= 0:
            raise ValueError('outbox lease must be positive')
        claimed_at = _timestamp_to_iso(now) if now is not None else _now_iso()
        claimed_datetime = datetime.fromisoformat(claimed_at)
        stale_before = claimed_datetime - timedelta(seconds=lease_seconds)
        with closing(connect()) as conn:
            try:
                conn.execute('BEGIN IMMEDIATE')
                sending_rows = conn.execute(
                    "SELECT id, status FROM admin_outbox WHERE status = 'sending' OR status LIKE 'sending:%'",
                ).fetchall()
                for sending_row in sending_rows:
                    sending_status = str(sending_row['status'])
                    if _lease_is_expired(sending_status, stale_before):
                        conn.execute(
                            'UPDATE admin_outbox SET status = ? WHERE id = ? AND status = ?',
                            ('pending', int(sending_row['id']), sending_status),
                        )
                row = conn.execute(
                    '''
                    SELECT id, event_type, payload
                    FROM admin_outbox
                    WHERE status = 'pending'
                    ORDER BY id
                    LIMIT 1
                    ''',
                ).fetchone()
                if row is None:
                    conn.commit()
                    return None
                event_id = int(row['id'])
                lease_token = uuid4().hex
                lease_status = f'sending:{claimed_at}:{lease_token}'
                conn.execute(
                    "UPDATE admin_outbox SET status = ? WHERE id = ?",
                    (lease_status, event_id),
                )
                conn.commit()
                payload = json.loads(str(row['payload']))
                if not isinstance(payload, dict):
                    raise ValueError('invalid admin outbox payload')
                return AdminOutboxRecord(
                    event_id,
                    str(row['event_type']),
                    payload,
                    lease_token,
                )
            except Exception:
                conn.rollback()
                raise

    def renew_admin_event_lease(
        self,
        event_id: int,
        lease_token: str,
        *,
        now: datetime | str | int | None = None,
    ) -> bool:
        renewed_at = _timestamp_to_iso(now) if now is not None else _now_iso()
        with closing(connect()) as conn:
            try:
                conn.execute('BEGIN IMMEDIATE')
                row = conn.execute(
                    'SELECT status FROM admin_outbox WHERE id = ?',
                    (event_id,),
                ).fetchone()
                if row is None or not _status_owns_lease(str(row['status']), lease_token):
                    conn.commit()
                    return False
                renewed_status = f'sending:{renewed_at}:{lease_token}'
                result = conn.execute(
                    '''
                    UPDATE admin_outbox
                    SET status = ?
                    WHERE id = ? AND status = ?
                    ''',
                    (renewed_status, event_id, str(row['status'])),
                )
                conn.commit()
                return result.rowcount == 1
            except Exception:
                conn.rollback()
                raise

    def complete_admin_event(self, event_id: int, lease_token: str) -> bool:
        return self._transition_admin_event(
            event_id,
            lease_token,
            target_status='delivered',
            delivered_at=_now_iso(),
        )

    def release_admin_event(self, event_id: int, lease_token: str) -> bool:
        return self._transition_admin_event(
            event_id,
            lease_token,
            target_status='pending',
            delivered_at=None,
        )

    def _transition_admin_event(
        self,
        event_id: int,
        lease_token: str,
        *,
        target_status: str,
        delivered_at: str | None,
    ) -> bool:
        with closing(connect()) as conn:
            try:
                conn.execute('BEGIN IMMEDIATE')
                row = conn.execute(
                    'SELECT status FROM admin_outbox WHERE id = ?',
                    (event_id,),
                ).fetchone()
                if row is None or not _status_owns_lease(str(row['status']), lease_token):
                    conn.commit()
                    return False
                result = conn.execute(
                    '''
                    UPDATE admin_outbox
                    SET status = ?, delivered_at = ?
                    WHERE id = ? AND status = ?
                    ''',
                    (target_status, delivered_at, event_id, str(row['status'])),
                )
                conn.commit()
                return result.rowcount == 1
            except Exception:
                conn.rollback()
                raise

    def mark_admin_recipient_delivered(
        self,
        event_id: int,
        lease_token: str,
        recipient_id: str,
    ) -> bool:
        normalized_recipient = recipient_id.strip()
        if not normalized_recipient:
            raise ValueError('admin recipient is required')
        with closing(connect()) as conn:
            try:
                conn.execute('BEGIN IMMEDIATE')
                row = conn.execute(
                    'SELECT payload, status FROM admin_outbox WHERE id = ?',
                    (event_id,),
                ).fetchone()
                if row is None or not _status_owns_lease(str(row['status']), lease_token):
                    conn.commit()
                    return False
                payload = json.loads(str(row['payload']))
                if not isinstance(payload, dict):
                    raise ValueError('invalid admin outbox payload')
                delivered = payload.get('_delivered_admin_ids', [])
                if not isinstance(delivered, list):
                    raise ValueError('invalid admin delivery progress')
                delivered_ids = [str(value) for value in delivered]
                if normalized_recipient not in delivered_ids:
                    delivered_ids.append(normalized_recipient)
                    payload['_delivered_admin_ids'] = delivered_ids
                    result = conn.execute(
                        '''
                        UPDATE admin_outbox
                        SET payload = ?
                        WHERE id = ? AND status = ?
                        ''',
                        (
                            json.dumps(
                                payload,
                                ensure_ascii=False,
                                separators=(',', ':'),
                                sort_keys=True,
                            ),
                            event_id,
                            str(row['status']),
                        ),
                    )
                    if result.rowcount != 1:
                        conn.rollback()
                        return False
                conn.commit()
                return True
            except Exception:
                conn.rollback()
                raise

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
                ),
                admin_event_type='restore',
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


def _apply_verified_transaction(
    conn: sqlite3.Connection,
    transaction: VerifiedAppStoreTransaction,
    *,
    enqueue_admin: bool,
    admin_event_type: str,
) -> ApplyTransactionResult:
    values = _validated_values(transaction)
    _ensure_terminal_event_table(conn)
    existing = conn.execute(
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
    if existing is not None:
        _validate_replay(existing, transaction, values)
        remaining = _remaining_readings(conn, str(existing['client_id']), _now_iso())
        return ApplyTransactionResult(transaction.transaction_id, 0, True, remaining)

    created_at = _now_iso()
    terminal_notification = conn.execute(
        '''
        SELECT 1
        FROM apple_terminal_events
        WHERE transaction_id = ?
           OR (
                original_transaction_id = ?
                AND cutoff_at IS NOT NULL
                AND ? IS NOT NULL
                AND ? <= cutoff_at
           )
        LIMIT 1
        ''',
        (
            transaction.transaction_id,
            transaction.original_transaction_id,
            values.expires_at,
            values.expires_at,
        ),
    ).fetchone()
    terminal_before_grant = terminal_notification is not None
    _ensure_app_account(conn, transaction, created_at)
    if transaction.product_type == 'subscription':
        _ensure_subscription_chain(conn, transaction, created_at)
    conn.execute(
        '''
        INSERT INTO apple_transactions (
            transaction_id, original_transaction_id, client_id,
            app_account_token, product_id, product_type, readings,
            purchased_at, expires_at, environment, signed_transaction,
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
            client_id, source_transaction_id, original_transaction_id,
            product_id, product_type, granted, remaining, expires_at,
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
            0 if terminal_before_grant else transaction.readings,
            values.expires_at,
            created_at,
        ),
    )
    if enqueue_admin and not terminal_before_grant:
        conn.execute(
            '''
            INSERT INTO admin_outbox (
                event_type, dedupe_key, payload, status, created_at
            ) VALUES (?, ?, ?, 'pending', ?)
            ''',
            (
                'apple_transaction_applied',
                f'apple-transaction:{transaction.transaction_id}',
                json.dumps(
                    {
                        'event_type': admin_event_type,
                        'client_id': transaction.client_id,
                        'transaction_id': transaction.transaction_id,
                        'original_transaction_id': transaction.original_transaction_id,
                        'product_id': transaction.product_id,
                        'product_type': transaction.product_type,
                        'readings': transaction.readings,
                        'expires_at': values.expires_at,
                        'environment': transaction.environment,
                        'detail': (
                            'client restore'
                            if admin_event_type == 'restore'
                            else 'client verification'
                        ),
                    },
                    ensure_ascii=False,
                    separators=(',', ':'),
                    sort_keys=True,
                ),
                created_at,
            ),
        )
    remaining = _remaining_readings(conn, transaction.client_id, _now_iso())
    return ApplyTransactionResult(
        transaction.transaction_id,
        0 if terminal_before_grant else transaction.readings,
        False,
        remaining,
    )


def _status_owns_lease(status: str, lease_token: str) -> bool:
    normalized_token = lease_token.strip()
    return bool(
        normalized_token
        and status.startswith('sending:')
        and status.endswith(f':{normalized_token}')
    )


def _lease_is_expired(status: str, stale_before: datetime) -> bool:
    if status == 'sending':
        return True
    if not status.startswith('sending:'):
        return False
    encoded = status[len('sending:'):]
    timestamp = encoded
    possible_timestamp, separator, possible_token = encoded.rpartition(':')
    if (
        separator
        and len(possible_token) == 32
        and all(character in '0123456789abcdef' for character in possible_token.lower())
    ):
        timestamp = possible_timestamp
    try:
        claimed_at = datetime.fromisoformat(timestamp)
    except ValueError:
        return True
    if claimed_at.tzinfo is None:
        claimed_at = claimed_at.replace(tzinfo=UTC)
    return claimed_at.astimezone(UTC) <= stale_before.astimezone(UTC)


def _ensure_terminal_event_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS apple_terminal_events (
            notification_uuid TEXT PRIMARY KEY,
            transaction_id TEXT NOT NULL,
            original_transaction_id TEXT NOT NULL,
            terminal_type TEXT NOT NULL,
            cutoff_at TEXT,
            created_at TEXT NOT NULL
        )
        ''',
    )
    conn.execute(
        '''
        CREATE INDEX IF NOT EXISTS idx_apple_terminal_events_chain
        ON apple_terminal_events(original_transaction_id, cutoff_at)
        ''',
    )


def _ensure_validation_failure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS apple_validation_failure_buckets (
            bucket_key TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            window_start TEXT NOT NULL,
            attempt_count INTEGER NOT NULL CHECK(attempt_count > 0),
            first_fingerprint TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL
        )
        ''',
    )
    conn.execute(
        '''
        CREATE INDEX IF NOT EXISTS idx_apple_validation_failure_window
        ON apple_validation_failure_buckets(window_start)
        ''',
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
