from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime, timedelta


DEFAULT_DB_PATH = 'database/data.db'


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description='Fix wrong subscription period length for selected plans in subscriptions table.',
    )
    parser.add_argument('--db', default=DEFAULT_DB_PATH, help='Path to SQLite database')
    parser.add_argument(
        '--plans',
        default='week',
        help='Comma-separated plan list to fix (example: week or week,one10)',
    )
    parser.add_argument('--apply', action='store_true', help='Write changes to DB (default: dry-run)')
    return parser.parse_args()


def _expected_days(plan: str) -> int | None:
    if plan == 'week':
        return 7
    if plan == 'month':
        return 30
    if plan == 'one10':
        return 7
    if plan == 'one40':
        return 7
    return None


def _must_fix(days: float, expected: int) -> bool:
    # Accept tiny float drift, but fix obvious mistakes (30/3650 etc.).
    return abs(days - expected) > 1.0


def main() -> None:
    args = _parse_args()
    plans = [p.strip() for p in args.plans.split(',') if p.strip()]
    if not plans:
        raise SystemExit('No plans passed in --plans')

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    placeholders = ','.join('?' for _ in plans)
    rows = conn.execute(
        f'''
        SELECT id, user_id, plan, status, starts_at, ends_at, remaining, auto_renew
        FROM subscriptions
        WHERE plan IN ({placeholders})
        ORDER BY id
        ''',
        plans,
    ).fetchall()

    to_fix: list[tuple[int, str, str, int, str, str, float]] = []
    for row in rows:
        expected = _expected_days(str(row['plan']))
        if expected is None:
            continue
        try:
            start = datetime.fromisoformat(row['starts_at'])
            end = datetime.fromisoformat(row['ends_at'])
        except Exception:
            continue
        days = (end - start).total_seconds() / 86400
        if not _must_fix(days, expected):
            continue
        new_end = (start + timedelta(days=expected)).isoformat()
        to_fix.append(
            (
                int(row['id']),
                str(row['plan']),
                str(row['status']),
                int(row['user_id']),
                str(row['ends_at']),
                new_end,
                days,
            )
        )

    print(f'DB: {args.db}')
    print(f'Plans: {", ".join(plans)}')
    print(f'Rows scanned: {len(rows)}')
    print(f'Rows to fix: {len(to_fix)}')
    for sub_id, plan, status, user_id, old_end, new_end, days in to_fix[:50]:
        print(
            f'id={sub_id} user_id={user_id} plan={plan} status={status} '
            f'days={days:.3f} old_end={old_end} -> new_end={new_end}'
        )

    if not args.apply:
        print('Dry-run mode. Use --apply to write changes.')
        conn.close()
        return

    for sub_id, *_rest, new_end, _days in to_fix:
        conn.execute('UPDATE subscriptions SET ends_at = ? WHERE id = ?', (new_end, sub_id))
    conn.commit()
    conn.close()
    print(f'Applied: {len(to_fix)} rows updated.')


if __name__ == '__main__':
    main()
