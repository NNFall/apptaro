from __future__ import annotations

import json
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import RLock

from src.repositories import billing as billing_repo
from src.repositories.storage import connect


UTC = timezone.utc
_LOCK = RLock()


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class PromoCode:
    code: str
    tokens: int
    max_uses: int
    used: int
    is_active: int
    created_at: str


def add_admin(user_id: int) -> None:
    with _LOCK:
        with closing(connect()) as conn:
            conn.execute(
                'INSERT OR IGNORE INTO admins (user_id, created_at) VALUES (?, ?)',
                (user_id, _now()),
            )
            conn.commit()


def remove_admin(user_id: int) -> None:
    with _LOCK:
        with closing(connect()) as conn:
            conn.execute('DELETE FROM admins WHERE user_id = ?', (user_id,))
            conn.commit()


def list_admins() -> list[int]:
    with _LOCK:
        with closing(connect()) as conn:
            rows = conn.execute('SELECT user_id FROM admins ORDER BY user_id ASC').fetchall()
    return [int(row['user_id']) for row in rows]


def has_admin(user_id: int) -> bool:
    with _LOCK:
        with closing(connect()) as conn:
            row = conn.execute('SELECT 1 FROM admins WHERE user_id = ? LIMIT 1', (user_id,)).fetchone()
    return row is not None


def create_ad_tag(tag: str, source: str, campaign: str, content: str) -> None:
    with _LOCK:
        with closing(connect()) as conn:
            conn.execute(
                '''
                INSERT OR REPLACE INTO ad_tags (tag, source, campaign, content, created_at)
                VALUES (?, ?, ?, ?, ?)
                ''',
                (tag, source, campaign, content, _now()),
            )
            conn.commit()


def get_ad_tag(tag: str) -> dict[str, str] | None:
    with _LOCK:
        with closing(connect()) as conn:
            row = conn.execute('SELECT * FROM ad_tags WHERE tag = ?', (tag,)).fetchone()
    if row is None:
        return None
    return {key: str(row[key]) for key in row.keys()}


def record_client_tag(client_id: str, tag: str, raw: str) -> None:
    with _LOCK:
        with closing(connect()) as conn:
            conn.execute(
                '''
                INSERT OR IGNORE INTO client_tags (client_id, tag, raw, created_at)
                VALUES (?, ?, ?, ?)
                ''',
                (client_id, tag, raw, _now()),
            )
            conn.commit()


def add_tokens(client_id: str, tokens: int, days: int = 3650) -> None:
    now = datetime.now(UTC)
    current = billing_repo.get_subscription_for_use(client_id)
    if current:
        try:
            ends_at = datetime.fromisoformat(current.ends_at)
        except Exception:  # noqa: BLE001
            ends_at = now
        new_ends = max(ends_at, now + timedelta(days=days))
        remaining = current.remaining + tokens
        with _LOCK:
            with closing(connect()) as conn:
                conn.execute(
                    '''
                    UPDATE billing_subscriptions
                    SET remaining = ?, ends_at = ?, status = ?
                    WHERE id = ?
                    ''',
                    (remaining, new_ends.isoformat(), current.status or 'manual', current.id),
                )
                conn.commit()
        return

    ends = now + timedelta(days=days)
    with _LOCK:
        with closing(connect()) as conn:
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
                    'manual',
                    now.isoformat(),
                    ends.isoformat(),
                    tokens,
                    'manual',
                    0,
                    None,
                    'manual',
                    _now(),
                ),
            )
            conn.commit()


def set_subscription_status(client_id: str, status: str) -> bool:
    active = billing_repo.get_active_subscription(client_id)
    if active is None:
        return False
    with _LOCK:
        with closing(connect()) as conn:
            conn.execute(
                '''
                UPDATE billing_subscriptions
                SET status = ?, remaining = 0
                WHERE client_id = ? AND status = 'active'
                ''',
                (status, client_id),
            )
            conn.commit()
    return True


def get_bot_stats_full() -> dict[str, int | float]:
    with _LOCK:
        with closing(connect()) as conn:
            users = _first_int(conn, 'SELECT COUNT(*) AS c FROM billing_clients')
            generations = _first_int(
                conn,
                "SELECT COUNT(*) AS c FROM jobs WHERE job_type = 'presentation_render'",
            )
            success = _first_int(
                conn,
                "SELECT COUNT(*) AS c FROM jobs WHERE job_type = 'presentation_render' AND status = 'succeeded'",
            )
            paid_users = _first_int(
                conn,
                '''
                SELECT COUNT(DISTINCT client_id) AS c
                FROM billing_payments
                WHERE status = 'paid' AND currency = 'RUB'
                ''',
            )
            revenue_rub = _first_int(
                conn,
                '''
                SELECT COALESCE(SUM(amount), 0) AS s
                FROM billing_payments
                WHERE status = 'paid' AND currency = 'RUB'
                ''',
                key='s',
            )

            active_subs = 0
            week_subs = 0
            month_subs = 0
            active_clients: set[str] = set()
            sub_rows = conn.execute(
                '''
                SELECT * FROM billing_subscriptions
                WHERE status = 'active'
                ORDER BY id DESC
                '''
            ).fetchall()
            for row in sub_rows:
                item = billing_repo._row_to_subscription(row)  # type: ignore[attr-defined]
                if item is None or item.client_id in active_clients:
                    continue
                if not _is_subscription_valid(item.ends_at, item.remaining):
                    continue
                active_clients.add(item.client_id)
                if item.plan_key in {'week', 'month'}:
                    active_subs += 1
                    if item.plan_key == 'week':
                        week_subs += 1
                    if item.plan_key == 'month':
                        month_subs += 1

            free_users = len(_free_generation_clients(conn))

    return {
        'users': users,
        'generations': generations,
        'success': success,
        'free_users': free_users,
        'paid_users': paid_users,
        'active_subs': active_subs,
        'week_subs': week_subs,
        'month_subs': month_subs,
        'revenue_rub': revenue_rub,
    }


def get_tag_stats(tag: str) -> dict[str, int]:
    with _LOCK:
        with closing(connect()) as conn:
            client_ids = _tag_clients(conn, tag)
            users = len(client_ids)
            buyers = 0
            revenue = 0
            if client_ids:
                placeholders = ','.join('?' for _ in client_ids)
                buyers = _first_int(
                    conn,
                    f'''
                    SELECT COUNT(DISTINCT client_id) AS c
                    FROM billing_payments
                    WHERE client_id IN ({placeholders})
                      AND status = 'paid'
                      AND currency = 'RUB'
                    ''',
                    tuple(client_ids),
                )
                revenue = _first_int(
                    conn,
                    f'''
                    SELECT COALESCE(SUM(amount), 0) AS s
                    FROM billing_payments
                    WHERE client_id IN ({placeholders})
                      AND status = 'paid'
                      AND currency = 'RUB'
                    ''',
                    tuple(client_ids),
                    key='s',
                )
    return {'users': users, 'payments': buyers, 'revenue': revenue}


def get_all_tag_stats_full() -> list[dict[str, int | str]]:
    with _LOCK:
        with closing(connect()) as conn:
            tags = {
                str(row['tag'])
                for row in conn.execute('SELECT DISTINCT tag FROM client_tags WHERE tag != ""').fetchall()
            }
            tags.update(str(row['tag']) for row in conn.execute('SELECT tag FROM ad_tags').fetchall())

            stats: list[dict[str, int | str]] = []
            tagged_clients: set[str] = set()
            for tag in sorted(tags):
                client_ids = _tag_clients(conn, tag)
                tagged_clients.update(client_ids)
                users = len(client_ids)
                buyers = 0
                revenue = 0
                if client_ids:
                    placeholders = ','.join('?' for _ in client_ids)
                    buyers = _first_int(
                        conn,
                        f'''
                        SELECT COUNT(DISTINCT client_id) AS c
                        FROM billing_payments
                        WHERE client_id IN ({placeholders})
                          AND status = 'paid'
                          AND currency = 'RUB'
                        ''',
                        tuple(client_ids),
                    )
                    revenue = _first_int(
                        conn,
                        f'''
                        SELECT COALESCE(SUM(amount), 0) AS s
                        FROM billing_payments
                        WHERE client_id IN ({placeholders})
                          AND status = 'paid'
                          AND currency = 'RUB'
                        ''',
                        tuple(client_ids),
                        key='s',
                    )
                stats.append(
                    {
                        'tag': tag,
                        'users': users,
                        'buyers': buyers,
                        'revenue': revenue,
                    }
                )

            all_clients = {
                str(row['client_id'])
                for row in conn.execute('SELECT client_id FROM billing_clients').fetchall()
            }
            without_tag = sorted(all_clients - tagged_clients)
            no_users = len(without_tag)
            no_buyers = 0
            no_revenue = 0
            if without_tag:
                placeholders = ','.join('?' for _ in without_tag)
                no_buyers = _first_int(
                    conn,
                    f'''
                    SELECT COUNT(DISTINCT client_id) AS c
                    FROM billing_payments
                    WHERE client_id IN ({placeholders})
                      AND status = 'paid'
                      AND currency = 'RUB'
                    ''',
                    tuple(without_tag),
                )
                no_revenue = _first_int(
                    conn,
                    f'''
                    SELECT COALESCE(SUM(amount), 0) AS s
                    FROM billing_payments
                    WHERE client_id IN ({placeholders})
                      AND status = 'paid'
                      AND currency = 'RUB'
                    ''',
                    tuple(without_tag),
                    key='s',
                )
            stats.append(
                {
                    'tag': 'без метки',
                    'users': no_users,
                    'buyers': no_buyers,
                    'revenue': no_revenue,
                }
            )
            return stats


def create_promo_code(code: str, tokens: int, max_uses: int) -> None:
    normalized = (code or '').strip().upper()
    with _LOCK:
        with closing(connect()) as conn:
            conn.execute(
                '''
                INSERT INTO promo_codes (code, tokens, max_uses, used, is_active, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ''',
                (normalized, tokens, max_uses, 0, 1, _now()),
            )
            conn.commit()


def get_latest_subscription(client_id: str):
    return billing_repo.get_latest_subscription(client_id)


def get_active_subscription(client_id: str):
    return billing_repo.get_active_subscription(client_id)


def cancel_subscription(client_id: str) -> bool:
    return billing_repo.cancel_subscription(client_id)


def _free_generation_clients(conn) -> set[str]:
    paid_clients = {
        str(row['client_id'])
        for row in conn.execute(
            '''
            SELECT DISTINCT client_id
            FROM billing_payments
            WHERE status = 'paid'
            '''
        ).fetchall()
    }
    free_clients: set[str] = set()
    rows = conn.execute(
        '''
        SELECT input_data
        FROM jobs
        WHERE job_type = 'presentation_render'
        '''
    ).fetchall()
    for row in rows:
        client_id = _extract_client_id(row['input_data'])
        if client_id and client_id not in paid_clients:
            free_clients.add(client_id)
    return free_clients


def _extract_client_id(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    value = str(data.get('client_id', '')).strip()
    return value or None


def _is_subscription_valid(ends_at_raw: str, remaining: int) -> bool:
    if remaining <= 0:
        return False
    try:
        ends_at = datetime.fromisoformat(ends_at_raw)
    except Exception:  # noqa: BLE001
        return False
    return ends_at >= datetime.now(UTC)


def _tag_clients(conn, tag: str) -> list[str]:
    rows = conn.execute(
        'SELECT DISTINCT client_id FROM client_tags WHERE tag = ? ORDER BY client_id ASC',
        (tag,),
    ).fetchall()
    return [str(row['client_id']) for row in rows]


def _first_int(conn, query: str, params: tuple = (), key: str = 'c') -> int:
    row = conn.execute(query, params).fetchone()
    if row is None:
        return 0
    value = row[key]
    try:
        return int(value or 0)
    except Exception:  # noqa: BLE001
        return 0
