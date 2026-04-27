from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, List

from .db import get_db


UTC = timezone.utc


def _now() -> str:
    return datetime.now(UTC).isoformat()


async def upsert_user(user_id: int, username: str, first_name: str, last_name: str) -> None:
    async with get_db() as db:
        await db.execute(
            'INSERT OR IGNORE INTO users (id, username, first_name, last_name, created_at, last_active) '
            'VALUES (?, ?, ?, ?, ?, ?)',
            (user_id, username, first_name, last_name, _now(), _now()),
        )
        await db.execute(
            'UPDATE users SET username = ?, first_name = ?, last_name = ?, last_active = ? WHERE id = ?',
            (username, first_name, last_name, _now(), user_id),
        )
        await db.commit()


async def get_user(user_id: int) -> Optional[dict]:
    async with get_db() as db:
        cur = await db.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def create_subscription(
    user_id: int,
    plan: str,
    limit: int,
    days: int,
    provider: str = 'manual',
    auto_renew: int = 0,
    payment_method_id: str | None = None,
) -> None:
    now = datetime.now(UTC)
    ends = now + timedelta(days=days)
    async with get_db() as db:
        await db.execute(
            "UPDATE subscriptions SET status = 'expired', remaining = 0 WHERE user_id = ? AND status = 'active'",
            (user_id,),
        )
        await db.execute(
            '''
            INSERT INTO subscriptions (
                user_id, plan, starts_at, ends_at, remaining, status, auto_renew, payment_method_id, provider, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                user_id,
                plan,
                now.isoformat(),
                ends.isoformat(),
                limit,
                'active',
                auto_renew,
                payment_method_id,
                provider,
                _now(),
            ),
        )
        await db.commit()


async def get_active_subscription(user_id: int) -> Optional[dict]:
    async with get_db() as db:
        cur = await db.execute(
            '''
            SELECT * FROM subscriptions
            WHERE user_id = ? AND status = 'active'
            ORDER BY id DESC
            ''',
            (user_id,),
        )
        rows = await cur.fetchall()
        if not rows:
            return None
        for row in rows:
            data = dict(row)
            ends_at = datetime.fromisoformat(data['ends_at'])
            if ends_at < datetime.now(UTC) or data['remaining'] <= 0:
                await db.execute(
                    'UPDATE subscriptions SET status = ? WHERE id = ?',
                    ('expired', data['id']),
                )
                continue
            await db.commit()
            return data
        await db.commit()
        return None


async def get_subscription_for_use(user_id: int) -> Optional[dict]:
    async with get_db() as db:
        cur = await db.execute(
            '''
            SELECT * FROM subscriptions
            WHERE user_id = ? AND status IN ('active', 'canceled', 'manual')
            ORDER BY id DESC
            ''',
            (user_id,),
        )
        rows = await cur.fetchall()
        if not rows:
            return None
        for row in rows:
            data = dict(row)
            ends_at = datetime.fromisoformat(data['ends_at'])
            if ends_at < datetime.now(UTC) or data['remaining'] <= 0:
                await db.execute(
                    'UPDATE subscriptions SET status = ? WHERE id = ?',
                    ('expired', data['id']),
                )
                continue
            await db.commit()
            return data
        await db.commit()
        return None


async def get_latest_subscription(user_id: int) -> Optional[dict]:
    async with get_db() as db:
        cur = await db.execute(
            '''
            SELECT * FROM subscriptions
            WHERE user_id = ?
            ORDER BY id DESC LIMIT 1
            ''',
            (user_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def get_latest_valid_subscription(user_id: int) -> Optional[dict]:
    async with get_db() as db:
        cur = await db.execute(
            '''
            SELECT * FROM subscriptions
            WHERE user_id = ? AND remaining > 0
            ORDER BY id DESC
            ''',
            (user_id,),
        )
        rows = await cur.fetchall()
        if not rows:
            return None
        for row in rows:
            data = dict(row)
            try:
                ends_at = datetime.fromisoformat(data['ends_at'])
            except Exception:  # noqa: BLE001
                ends_at = None
            if ends_at and ends_at >= datetime.now(UTC):
                return data
        return None


async def add_tokens(user_id: int, tokens: int, days: int = 3650) -> None:
    now = datetime.now(UTC)
    async with get_db() as db:
        cur = await db.execute(
            '''
            SELECT * FROM subscriptions
            WHERE user_id = ? AND status IN ('active', 'canceled', 'manual')
            ORDER BY id DESC LIMIT 1
            ''',
            (user_id,),
        )
        row = await cur.fetchone()
        if row:
            remaining = row['remaining'] + tokens
            ends_at = datetime.fromisoformat(row['ends_at'])
            new_ends = max(ends_at, now + timedelta(days=days))
            await db.execute(
                'UPDATE subscriptions SET remaining = ?, ends_at = ? WHERE id = ?',
                (remaining, new_ends.isoformat(), row['id']),
            )
        else:
            ends = now + timedelta(days=days)
            await db.execute(
                '''
                INSERT INTO subscriptions (
                    user_id, plan, starts_at, ends_at, remaining, status, auto_renew, provider, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''',
                (user_id, 'manual', now.isoformat(), ends.isoformat(), tokens, 'manual', 0, 'manual', _now()),
            )
        await db.commit()


async def set_subscription_status(user_id: int, status: str) -> bool:
    async with get_db() as db:
        cur = await db.execute(
            '''
            SELECT * FROM subscriptions
            WHERE user_id = ? AND status = 'active'
            ORDER BY id DESC LIMIT 1
            ''',
            (user_id,),
        )
        row = await cur.fetchone()
        if not row:
            return False
        await db.execute(
            'UPDATE subscriptions SET status = ?, remaining = 0 WHERE user_id = ? AND status = ?',
            (status, user_id, 'active'),
        )
        await db.commit()
        return True


async def cancel_subscription(user_id: int) -> bool:
    async with get_db() as db:
        cur = await db.execute(
            '''
            SELECT * FROM subscriptions
            WHERE user_id = ? AND status = 'active'
            ORDER BY id DESC LIMIT 1
            ''',
            (user_id,),
        )
        row = await cur.fetchone()
        if not row:
            return False
        await db.execute(
            'UPDATE subscriptions SET status = ?, auto_renew = 0 WHERE user_id = ? AND status = ?',
            ('canceled', user_id, 'active'),
        )
        await db.commit()
        return True


async def decrement_subscription(user_id: int) -> bool:
    async with get_db() as db:
        cur = await db.execute(
            '''
            SELECT * FROM subscriptions
            WHERE user_id = ? AND status IN ('active', 'canceled', 'manual')
            ORDER BY id DESC LIMIT 1
            ''',
            (user_id,),
        )
        row = await cur.fetchone()
        if not row:
            return False
        remaining = row['remaining'] - 1
        status = row['status'] if remaining > 0 else 'expired'
        await db.execute(
            'UPDATE subscriptions SET remaining = ?, status = ? WHERE id = ?',
            (remaining, status, row['id']),
        )
        await db.commit()
        return remaining >= 0


async def log_generation(user_id: int, topic: str, slides: int, success: bool) -> None:
    async with get_db() as db:
        await db.execute(
            'INSERT INTO generations (user_id, topic, slides, success, created_at) VALUES (?, ?, ?, ?, ?)',
            (user_id, topic, slides, 1 if success else 0, _now()),
        )
        await db.commit()


async def add_payment(user_id: int, provider: str, amount: int, currency: str, payload: str, status: str) -> None:
    async with get_db() as db:
        await db.execute(
            '''
            INSERT INTO payments (user_id, provider, amount, currency, payload, status, payment_method_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (user_id, provider, amount, currency, payload, status, None, _now()),
        )
        await db.commit()


async def add_payment_with_method(
    user_id: int,
    provider: str,
    amount: int,
    currency: str,
    payload: str,
    status: str,
    payment_method_id: str | None,
) -> None:
    async with get_db() as db:
        await db.execute(
            '''
            INSERT INTO payments (user_id, provider, amount, currency, payload, status, payment_method_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (user_id, provider, amount, currency, payload, status, payment_method_id, _now()),
        )
        await db.commit()


async def set_autorenew(user_id: int, enabled: bool) -> None:
    async with get_db() as db:
        await db.execute(
            'UPDATE subscriptions SET auto_renew = ? WHERE user_id = ? AND status = ?',
            (1 if enabled else 0, user_id, 'active'),
        )
        await db.commit()


async def renew_subscription(sub_id: int, plan: str, limit: int, days: int) -> None:
    now = datetime.now(UTC)
    ends = now + timedelta(days=days)
    async with get_db() as db:
        await db.execute(
            '''
            UPDATE subscriptions
            SET starts_at = ?, ends_at = ?, remaining = ?, status = 'active'
            WHERE id = ?
            ''',
            (now.isoformat(), ends.isoformat(), limit, sub_id),
        )
        await db.commit()


async def get_autorenew_due_subscriptions() -> List[dict]:
    now = datetime.now(UTC).isoformat()
    async with get_db() as db:
        cur = await db.execute(
            '''
            SELECT * FROM subscriptions
            WHERE status = 'active'
              AND auto_renew = 1
              AND ends_at <= ?
            ''',
            (now,),
        )
        rows = await cur.fetchall()
        return [dict(row) for row in rows]


async def expire_subscription(sub_id: int) -> None:
    async with get_db() as db:
        await db.execute(
            'UPDATE subscriptions SET status = ?, remaining = 0, auto_renew = 0 WHERE id = ?',
            ('expired', sub_id),
        )
        await db.commit()


async def postpone_autorenew_attempt(sub_id: int, days: int = 1) -> str:
    now = datetime.now(UTC)
    async with get_db() as db:
        cur = await db.execute('SELECT ends_at FROM subscriptions WHERE id = ?', (sub_id,))
        row = await cur.fetchone()
        if not row:
            value = (now + timedelta(days=days)).isoformat()
            return value
        try:
            current_end = datetime.fromisoformat(row['ends_at'])
        except Exception:  # noqa: BLE001
            current_end = now
        next_try = max(current_end, now) + timedelta(days=days)
        await db.execute(
            'UPDATE subscriptions SET ends_at = ? WHERE id = ?',
            (next_try.isoformat(), sub_id),
        )
        await db.commit()
        return next_try.isoformat()


async def update_payment_status(
    provider: str,
    payload: str,
    status: str,
    payment_method_id: str | None = None,
) -> None:
    async with get_db() as db:
        if payment_method_id is None:
            await db.execute(
                'UPDATE payments SET status = ? WHERE provider = ? AND payload = ?',
                (status, provider, payload),
            )
        else:
            await db.execute(
                'UPDATE payments SET status = ?, payment_method_id = ? WHERE provider = ? AND payload = ?',
                (status, payment_method_id, provider, payload),
            )
        await db.commit()


async def get_bot_stats() -> dict:
    async with get_db() as db:
        cur = await db.execute('SELECT COUNT(*) as c FROM users')
        users = await cur.fetchone()
        cur = await db.execute('SELECT COUNT(*) as c FROM generations')
        gens = await cur.fetchone()
        cur = await db.execute('SELECT COUNT(*) as c FROM generations WHERE success = 1')
        ok = await cur.fetchone()
        return {
            'users': users['c'],
            'generations': gens['c'],
            'success': ok['c'],
        }


async def get_ad_stats() -> dict:
    async with get_db() as db:
        cur = await db.execute('SELECT COUNT(*) as c FROM payments WHERE status = ?', ('paid',))
        paid = await cur.fetchone()
        return {'payments': paid['c']}


async def get_bot_stats_full() -> dict:
    async with get_db() as db:
        cur = await db.execute('SELECT COUNT(*) as c FROM users')
        users = await cur.fetchone()
        cur = await db.execute('SELECT COUNT(*) as c FROM generations')
        gens = await cur.fetchone()
        cur = await db.execute('SELECT COUNT(*) as c FROM generations WHERE success = 1')
        ok = await cur.fetchone()

        cur = await db.execute(
            '''
            SELECT COUNT(DISTINCT g.user_id) as c
            FROM generations g
            LEFT JOIN (SELECT DISTINCT user_id FROM payments WHERE status = 'paid') p
            ON p.user_id = g.user_id
            WHERE p.user_id IS NULL
            '''
        )
        free_users = await cur.fetchone()

        cur = await db.execute('SELECT COUNT(DISTINCT user_id) as c FROM payments WHERE status = ?', ('paid',))
        paid_users = await cur.fetchone()

        cur = await db.execute(
            "SELECT COUNT(*) as c FROM subscriptions WHERE status = 'active' AND plan IN ('week', 'month')"
        )
        active_subs = await cur.fetchone()
        cur = await db.execute(
            "SELECT COUNT(*) as c FROM subscriptions WHERE status = 'active' AND plan = 'week'"
        )
        week_subs = await cur.fetchone()
        cur = await db.execute(
            "SELECT COUNT(*) as c FROM subscriptions WHERE status = 'active' AND plan = 'month'"
        )
        month_subs = await cur.fetchone()

        cur = await db.execute(
            "SELECT COUNT(*) as c FROM payments WHERE status = 'paid' AND provider = 'stars'"
        )
        stars_payments = await cur.fetchone()
        cur = await db.execute(
            "SELECT COUNT(DISTINCT user_id) as c FROM payments WHERE status = 'paid' AND provider = 'stars'"
        )
        stars_buyers = await cur.fetchone()
        cur = await db.execute(
            "SELECT COALESCE(SUM(amount), 0) as s FROM payments WHERE status = 'paid' AND provider = 'stars'"
        )
        stars_sum = await cur.fetchone()

        cur = await db.execute(
            "SELECT COALESCE(SUM(amount), 0) as s FROM payments WHERE status = 'paid' AND currency = 'RUB'"
        )
        revenue_rub = await cur.fetchone()

        return {
            'users': users['c'],
            'generations': gens['c'],
            'success': ok['c'],
            'free_users': free_users['c'],
            'paid_users': paid_users['c'],
            'active_subs': active_subs['c'],
            'week_subs': week_subs['c'],
            'month_subs': month_subs['c'],
            'stars_payments': stars_payments['c'],
            'stars_buyers': stars_buyers['c'],
            'stars_sum': stars_sum['s'],
            'revenue_rub': revenue_rub['s'],
        }


async def create_ad_tag(tag: str, source: str, campaign: str, content: str) -> None:
    async with get_db() as db:
        await db.execute(
            'INSERT OR REPLACE INTO ad_tags (tag, source, campaign, content, created_at) VALUES (?, ?, ?, ?, ?)',
            (tag, source, campaign, content, _now()),
        )
        await db.commit()


async def get_ad_tag(tag: str) -> Optional[dict]:
    async with get_db() as db:
        cur = await db.execute('SELECT * FROM ad_tags WHERE tag = ?', (tag,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def record_user_tag(user_id: int, tag: str, raw: str) -> None:
    async with get_db() as db:
        await db.execute(
            'INSERT OR IGNORE INTO user_tags (user_id, tag, raw, created_at) VALUES (?, ?, ?, ?)',
            (user_id, tag, raw, _now()),
        )
        await db.commit()


async def get_tag_stats(tag: str) -> dict:
    async with get_db() as db:
        cur = await db.execute('SELECT COUNT(*) as c FROM user_tags WHERE tag = ?', (tag,))
        users = await cur.fetchone()
        cur = await db.execute(
            '''
            SELECT COUNT(*) as c
            FROM payments p
            JOIN user_tags ut ON ut.user_id = p.user_id
            WHERE ut.tag = ? AND p.status = 'paid' AND p.currency = 'RUB'
            ''',
            (tag,),
        )
        payments = await cur.fetchone()
        cur = await db.execute(
            '''
            SELECT COALESCE(SUM(p.amount), 0) as s
            FROM payments p
            JOIN user_tags ut ON ut.user_id = p.user_id
            WHERE ut.tag = ? AND p.status = 'paid' AND p.currency = 'RUB'
            ''',
            (tag,),
        )
        revenue = await cur.fetchone()
        return {'users': users['c'], 'payments': payments['c'], 'revenue': revenue['s']}


async def get_all_tag_stats_full() -> List[dict]:
    async with get_db() as db:
        cur = await db.execute('SELECT DISTINCT tag FROM user_tags WHERE tag != ""')
        rows = await cur.fetchall()
        tags = {row['tag'] for row in rows}
        cur = await db.execute('SELECT tag FROM ad_tags')
        rows = await cur.fetchall()
        tags.update(row['tag'] for row in rows)

        stats = []
        for tag in sorted(tags):
            cur = await db.execute('SELECT COUNT(DISTINCT user_id) as c FROM user_tags WHERE tag = ?', (tag,))
            users = await cur.fetchone()
            cur = await db.execute(
                '''
                SELECT COUNT(DISTINCT p.user_id) as c
                FROM payments p
                JOIN user_tags ut ON ut.user_id = p.user_id
                WHERE ut.tag = ? AND p.status = 'paid' AND p.currency = 'RUB'
                ''',
                (tag,),
            )
            buyers = await cur.fetchone()
            cur = await db.execute(
                '''
                SELECT COALESCE(SUM(p.amount), 0) as s
                FROM payments p
                JOIN user_tags ut ON ut.user_id = p.user_id
                WHERE ut.tag = ? AND p.status = 'paid' AND p.currency = 'RUB'
                ''',
                (tag,),
            )
            revenue = await cur.fetchone()
            stats.append(
                {
                    'tag': tag,
                    'users': users['c'],
                    'buyers': buyers['c'],
                    'revenue': revenue['s'],
                }
            )

        # без метки
        cur = await db.execute('SELECT COUNT(*) as c FROM users WHERE id NOT IN (SELECT user_id FROM user_tags)')
        no_users = await cur.fetchone()
        cur = await db.execute(
            '''
            SELECT COUNT(DISTINCT user_id) as c
            FROM payments
            WHERE status = 'paid' AND currency = 'RUB'
            AND user_id NOT IN (SELECT user_id FROM user_tags)
            '''
        )
        no_buyers = await cur.fetchone()
        cur = await db.execute(
            '''
            SELECT COALESCE(SUM(amount), 0) as s
            FROM payments
            WHERE status = 'paid' AND currency = 'RUB'
            AND user_id NOT IN (SELECT user_id FROM user_tags)
            '''
        )
        no_revenue = await cur.fetchone()
        stats.append(
            {
                'tag': 'без метки',
                'users': no_users['c'],
                'buyers': no_buyers['c'],
                'revenue': no_revenue['s'],
            }
        )
        return stats


async def add_admin(user_id: int) -> None:
    async with get_db() as db:
        await db.execute('INSERT OR IGNORE INTO admins (user_id, created_at) VALUES (?, ?)', (user_id, _now()))
        await db.commit()


async def remove_admin(user_id: int) -> None:
    async with get_db() as db:
        await db.execute('DELETE FROM admins WHERE user_id = ?', (user_id,))
        await db.commit()


async def list_admins() -> List[int]:
    async with get_db() as db:
        cur = await db.execute('SELECT user_id FROM admins')
        rows = await cur.fetchall()
        return [row['user_id'] for row in rows]


async def has_admin(user_id: int) -> bool:
    async with get_db() as db:
        cur = await db.execute('SELECT 1 FROM admins WHERE user_id = ? LIMIT 1', (user_id,))
        row = await cur.fetchone()
        return row is not None


async def create_promo_code(code: str, tokens: int, max_uses: int) -> None:
    async with get_db() as db:
        await db.execute(
            'INSERT INTO promo_codes (code, tokens, max_uses, used, created_at) VALUES (?, ?, ?, ?, ?)',
            (code, tokens, max_uses, 0, _now()),
        )
        await db.commit()


async def use_promo_code(user_id: int, code: str) -> tuple[bool, str, int]:
    async with get_db() as db:
        await db.execute('BEGIN')
        cur = await db.execute('SELECT * FROM promo_codes WHERE code = ?', (code,))
        row = await cur.fetchone()
        if not row:
            await db.execute('ROLLBACK')
            return False, 'Промокод не найден.', 0
        cur = await db.execute(
            'SELECT 1 FROM promo_uses WHERE code = ? AND user_id = ? LIMIT 1',
            (code, user_id),
        )
        used_row = await cur.fetchone()
        if used_row:
            await db.execute('ROLLBACK')
            return False, 'Промокод уже использован вами.', 0
        if row['used'] >= row['max_uses']:
            await db.execute('ROLLBACK')
            return False, 'Промокод уже исчерпан.', 0
        await db.execute(
            'UPDATE promo_codes SET used = used + 1 WHERE code = ?',
            (code,),
        )
        await db.execute(
            'INSERT INTO promo_uses (code, user_id, used_at) VALUES (?, ?, ?)',
            (code, user_id, _now()),
        )
        await db.commit()
        tokens = row['tokens']
    await add_tokens(user_id, tokens)
    return True, f'Промокод активирован! Добавлено {tokens} генераций.', tokens


async def get_mailer_state() -> Optional[dict]:
    async with get_db() as db:
        cur = await db.execute('SELECT * FROM mailer_state WHERE id = 1')
        row = await cur.fetchone()
        return dict(row) if row else None


async def upsert_mailer_state(
    current_index: int,
    next_run_at: str,
    preview_at: str,
    preview_sent: int,
) -> None:
    async with get_db() as db:
        await db.execute(
            '''
            INSERT INTO mailer_state (id, current_index, next_run_at, preview_at, preview_sent, updated_at)
            VALUES (1, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                current_index = excluded.current_index,
                next_run_at = excluded.next_run_at,
                preview_at = excluded.preview_at,
                preview_sent = excluded.preview_sent,
                updated_at = excluded.updated_at
            ''',
            (current_index, next_run_at, preview_at, preview_sent, _now()),
        )
        await db.commit()


async def set_mailer_preview_sent(sent: int) -> None:
    async with get_db() as db:
        await db.execute(
            'UPDATE mailer_state SET preview_sent = ?, updated_at = ? WHERE id = 1',
            (sent, _now()),
        )
        await db.commit()


async def get_users_without_active_subscription() -> List[dict]:
    now = datetime.now(UTC).isoformat()
    async with get_db() as db:
        cur = await db.execute(
            '''
            SELECT u.id, u.username
            FROM users u
            WHERE u.id NOT IN (
                SELECT user_id FROM subscriptions
                WHERE status = 'active' AND ends_at > ? AND remaining > 0
            )
            ORDER BY u.id
            ''',
            (now,),
        )
        rows = await cur.fetchall()
        return [dict(row) for row in rows]
