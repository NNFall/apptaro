from __future__ import annotations

import sys
import sqlite3
from datetime import datetime

from config import load_config


def _print_rows(rows: list[sqlite3.Row]) -> None:
    if not rows:
        print("  (нет)")
        return
    for row in rows:
        print(" ", dict(row))


def main() -> int:
    cfg = load_config()
    db_path = cfg.database_path
    now_iso = datetime.utcnow().isoformat(timespec="seconds")

    print(f"DB: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM subscriptions")
    total_subs = cur.fetchone()[0]
    cur.execute(
        "SELECT COUNT(*) FROM subscriptions WHERE status='active' AND current_period_end >= ?",
        (now_iso,),
    )
    active_subs = cur.fetchone()[0]

    print(f"Всего подписок: {total_subs}")
    print(f"Активных подписок: {active_subs}")

    print("\nДубликаты payment_method_id (одна карта на несколько аккаунтов):")
    cur.execute(
        """
        SELECT payment_method_id, COUNT(*) AS cnt, GROUP_CONCAT(user_id) AS users
        FROM subscriptions
        WHERE payment_method_id IS NOT NULL AND payment_method_id != ''
        GROUP BY payment_method_id
        HAVING cnt > 1
        ORDER BY cnt DESC
        """
    )
    _print_rows(cur.fetchall())

    print("\nАктивные подписки (user_id, plan_id, period_end, auto_renew):")
    cur.execute(
        """
        SELECT user_id, plan_id, current_period_end, auto_renew
        FROM subscriptions
        WHERE status='active' AND current_period_end >= ?
        ORDER BY current_period_end DESC
        """,
        (now_iso,),
    )
    _print_rows(cur.fetchall())

    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        user_id = int(sys.argv[1])
        print(f"\nПодписка для user_id={user_id}:")
        cur.execute("SELECT * FROM subscriptions WHERE user_id = ?", (user_id,))
        row = cur.fetchone()
        _print_rows([row] if row else [])

        print(f"\nПоследние платежи для user_id={user_id}:")
        cur.execute(
            """
            SELECT id, amount, currency, provider, status, created_at, payload
            FROM transactions
            WHERE user_id = ?
            ORDER BY created_at DESC
            LIMIT 10
            """,
            (user_id,),
        )
        _print_rows(cur.fetchall())

    conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
