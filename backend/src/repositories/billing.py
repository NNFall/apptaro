from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock

from src.repositories.storage import connect


UTC = timezone.utc
_LOCK = RLock()


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class StoredSubscription:
    id: int
    client_id: str
    plan_key: str
    starts_at: str
    ends_at: str
    remaining: int
    status: str
    auto_renew: int
    payment_method_id: str | None
    provider: str
    created_at: str


@dataclass(frozen=True)
class StoredPayment:
    id: int
    client_id: str
    provider: str
    amount: int
    currency: str
    plan_key: str
    external_payment_id: str
    status: str
    payment_method_id: str | None
    confirmation_url: str | None
    created_at: str
    updated_at: str


def touch_client(client_id: str) -> bool:
    now = _now()
    with _LOCK:
        with closing(connect()) as conn:
            existing = conn.execute(
                'SELECT 1 FROM billing_clients WHERE client_id = ? LIMIT 1',
                (client_id,),
            ).fetchone()
            conn.execute(
                '''
                INSERT INTO billing_clients (client_id, created_at, last_seen_at)
                VALUES (?, ?, ?)
                ON CONFLICT(client_id) DO UPDATE SET last_seen_at = excluded.last_seen_at
                ''',
                (client_id, now, now),
            )
            conn.commit()
    return existing is None


def create_payment(
    client_id: str,
    provider: str,
    amount: int,
    currency: str,
    plan_key: str,
    external_payment_id: str,
    status: str,
    payment_method_id: str | None = None,
    confirmation_url: str | None = None,
) -> StoredPayment:
    now = _now()
    with _LOCK:
        with closing(connect()) as conn:
            conn.execute(
                '''
                INSERT INTO billing_payments (
                    client_id,
                    provider,
                    amount,
                    currency,
                    plan_key,
                    external_payment_id,
                    status,
                    payment_method_id,
                    confirmation_url,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    client_id,
                    provider,
                    amount,
                    currency,
                    plan_key,
                    external_payment_id,
                    status,
                    payment_method_id,
                    confirmation_url,
                    now,
                    now,
                ),
            )
            conn.commit()
    payment = get_payment(external_payment_id)
    if payment is None:  # pragma: no cover - defensive
        raise RuntimeError('Failed to persist payment')
    return payment


def get_payment(external_payment_id: str) -> StoredPayment | None:
    with _LOCK:
        with closing(connect()) as conn:
            row = conn.execute(
                'SELECT * FROM billing_payments WHERE external_payment_id = ?',
                (external_payment_id,),
            ).fetchone()
    return _row_to_payment(row)


def list_open_payments(client_id: str, limit: int = 5) -> list[StoredPayment]:
    safe_limit = max(1, limit)
    with _LOCK:
        with closing(connect()) as conn:
            rows = conn.execute(
                '''
                SELECT * FROM billing_payments
                WHERE client_id = ?
                  AND status IN ('pending', 'waiting_for_capture')
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                ''',
                (client_id, safe_limit),
            ).fetchall()
    return [item for row in rows if (item := _row_to_payment(row)) is not None]


def update_payment_status(
    external_payment_id: str,
    status: str,
    payment_method_id: str | None = None,
    confirmation_url: str | None = None,
) -> StoredPayment | None:
    with _LOCK:
        with closing(connect()) as conn:
            conn.execute(
                '''
                UPDATE billing_payments
                SET status = ?,
                    payment_method_id = COALESCE(?, payment_method_id),
                    confirmation_url = COALESCE(?, confirmation_url),
                    updated_at = ?
                WHERE external_payment_id = ?
                ''',
                (status, payment_method_id, confirmation_url, _now(), external_payment_id),
            )
            conn.commit()
    return get_payment(external_payment_id)


def create_subscription(
    client_id: str,
    plan_key: str,
    limit: int,
    days: int,
    provider: str = 'manual',
    auto_renew: int = 0,
    payment_method_id: str | None = None,
) -> StoredSubscription:
    now_dt = datetime.now(UTC)
    ends = now_dt + timedelta(days=days)
    with _LOCK:
        with closing(connect()) as conn:
            conn.execute(
                '''
                UPDATE billing_subscriptions
                SET status = 'expired', remaining = 0
                WHERE client_id = ? AND status = 'active'
                ''',
                (client_id,),
            )
            conn.execute(
                '''
                INSERT INTO billing_subscriptions (
                    client_id,
                    plan_key,
                    starts_at,
                    ends_at,
                    remaining,
                    status,
                    auto_renew,
                    payment_method_id,
                    provider,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (
                    client_id,
                    plan_key,
                    now_dt.isoformat(),
                    ends.isoformat(),
                    limit,
                    'active',
                    auto_renew,
                    payment_method_id,
                    provider,
                    _now(),
                ),
            )
            conn.commit()
            row = conn.execute('SELECT * FROM billing_subscriptions WHERE id = last_insert_rowid()').fetchone()
    if row is None:  # pragma: no cover - defensive
        raise RuntimeError('Failed to persist subscription')
    return _row_to_subscription(row)


def renew_subscription(
    subscription_id: int,
    plan_key: str,
    limit: int,
    days: int,
) -> StoredSubscription | None:
    now_dt = datetime.now(UTC)
    ends = now_dt + timedelta(days=days)
    with _LOCK:
        with closing(connect()) as conn:
            conn.execute(
                '''
                UPDATE billing_subscriptions
                SET plan_key = ?,
                    starts_at = ?,
                    ends_at = ?,
                    remaining = ?,
                    status = 'active'
                WHERE id = ?
                ''',
                (plan_key, now_dt.isoformat(), ends.isoformat(), limit, subscription_id),
            )
            conn.commit()
    return get_subscription_by_id(subscription_id)


def get_subscription_by_id(subscription_id: int) -> StoredSubscription | None:
    with _LOCK:
        with closing(connect()) as conn:
            row = conn.execute(
                'SELECT * FROM billing_subscriptions WHERE id = ?',
                (subscription_id,),
            ).fetchone()
    return _row_to_subscription(row)


def get_active_subscription(client_id: str) -> StoredSubscription | None:
    with _LOCK:
        with closing(connect()) as conn:
            rows = conn.execute(
                '''
                SELECT * FROM billing_subscriptions
                WHERE client_id = ? AND status = 'active'
                ORDER BY id DESC
                ''',
                (client_id,),
            ).fetchall()
    if not rows:
        return None
    for row in rows:
        item = _row_to_subscription(row)
        if item is None:
            continue
        if _is_subscription_valid(item):
            return item
        expire_subscription(item.id)
    return None


def get_latest_valid_subscription(client_id: str) -> StoredSubscription | None:
    with _LOCK:
        with closing(connect()) as conn:
            rows = conn.execute(
                '''
                SELECT * FROM billing_subscriptions
                WHERE client_id = ? AND remaining > 0
                ORDER BY id DESC
                ''',
                (client_id,),
            ).fetchall()
    for row in rows:
        item = _row_to_subscription(row)
        if item and _subscription_not_expired(item):
            return item
    return None


def get_latest_subscription(client_id: str) -> StoredSubscription | None:
    with _LOCK:
        with closing(connect()) as conn:
            row = conn.execute(
                '''
                SELECT * FROM billing_subscriptions
                WHERE client_id = ?
                ORDER BY id DESC
                LIMIT 1
                ''',
                (client_id,),
            ).fetchone()
    return _row_to_subscription(row)


def get_subscription_for_use(client_id: str) -> StoredSubscription | None:
    with _LOCK:
        with closing(connect()) as conn:
            rows = conn.execute(
                '''
                SELECT * FROM billing_subscriptions
                WHERE client_id = ? AND status IN ('active', 'canceled', 'manual')
                ORDER BY id DESC
                ''',
                (client_id,),
            ).fetchall()
    if not rows:
        return None
    for row in rows:
        item = _row_to_subscription(row)
        if item is None:
            continue
        if _is_subscription_valid(item):
            return item
        expire_subscription(item.id)
    return None


def decrement_subscription(client_id: str) -> bool:
    item = get_subscription_for_use(client_id)
    if item is None:
        return False
    remaining = item.remaining - 1
    status = item.status if remaining > 0 else 'expired'
    with _LOCK:
        with closing(connect()) as conn:
            conn.execute(
                '''
                UPDATE billing_subscriptions
                SET remaining = ?, status = ?
                WHERE id = ?
                ''',
                (remaining, status, item.id),
            )
            conn.commit()
    return remaining >= 0


def cancel_subscription(client_id: str) -> bool:
    item = get_active_subscription(client_id)
    if item is None:
        return False
    with _LOCK:
        with closing(connect()) as conn:
            conn.execute(
                '''
                UPDATE billing_subscriptions
                SET status = 'canceled', auto_renew = 0
                WHERE client_id = ? AND status = 'active'
                ''',
                (client_id,),
            )
            conn.commit()
    return True


def get_due_auto_renew_subscriptions() -> list[StoredSubscription]:
    now = datetime.now(UTC).isoformat()
    with _LOCK:
        with closing(connect()) as conn:
            rows = conn.execute(
                '''
                SELECT * FROM billing_subscriptions
                WHERE status = 'active'
                  AND auto_renew = 1
                  AND ends_at <= ?
                ORDER BY id ASC
                ''',
                (now,),
            ).fetchall()
    return [item for row in rows if (item := _row_to_subscription(row)) is not None]


def expire_subscription(subscription_id: int) -> None:
    with _LOCK:
        with closing(connect()) as conn:
            conn.execute(
                '''
                UPDATE billing_subscriptions
                SET status = 'expired', remaining = 0, auto_renew = 0
                WHERE id = ?
                ''',
                (subscription_id,),
            )
            conn.commit()


def postpone_autorenew_attempt(subscription_id: int, days: int = 1) -> str:
    with _LOCK:
        with closing(connect()) as conn:
            row = conn.execute(
                'SELECT ends_at FROM billing_subscriptions WHERE id = ?',
                (subscription_id,),
            ).fetchone()
            now_dt = datetime.now(UTC)
            if row is None:
                value = (now_dt + timedelta(days=days)).isoformat()
                return value
            try:
                current_end = datetime.fromisoformat(str(row['ends_at']))
            except Exception:  # noqa: BLE001
                current_end = now_dt
            next_try = max(current_end, now_dt) + timedelta(days=days)
            conn.execute(
                'UPDATE billing_subscriptions SET ends_at = ? WHERE id = ?',
                (next_try.isoformat(), subscription_id),
            )
            conn.commit()
            return next_try.isoformat()


def _subscription_not_expired(item: StoredSubscription) -> bool:
    try:
        ends_at = datetime.fromisoformat(item.ends_at)
    except Exception:  # noqa: BLE001
        return False
    return ends_at >= datetime.now(UTC)


def _is_subscription_valid(item: StoredSubscription) -> bool:
    return item.remaining > 0 and _subscription_not_expired(item)


def _row_to_subscription(row) -> StoredSubscription | None:
    if row is None:
        return None
    return StoredSubscription(
        id=int(row['id']),
        client_id=str(row['client_id']),
        plan_key=str(row['plan_key']),
        starts_at=str(row['starts_at']),
        ends_at=str(row['ends_at']),
        remaining=int(row['remaining']),
        status=str(row['status']),
        auto_renew=int(row['auto_renew']),
        payment_method_id=row['payment_method_id'],
        provider=str(row['provider']),
        created_at=str(row['created_at']),
    )


def _row_to_payment(row) -> StoredPayment | None:
    if row is None:
        return None
    return StoredPayment(
        id=int(row['id']),
        client_id=str(row['client_id']),
        provider=str(row['provider']),
        amount=int(row['amount']),
        currency=str(row['currency']),
        plan_key=str(row['plan_key']),
        external_payment_id=str(row['external_payment_id']),
        status=str(row['status']),
        payment_method_id=row['payment_method_id'],
        confirmation_url=row['confirmation_url'],
        created_at=str(row['created_at']),
        updated_at=str(row['updated_at']),
    )
