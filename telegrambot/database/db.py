import os
from contextlib import asynccontextmanager

import aiosqlite

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_DB_PATH = os.path.join(_BASE_DIR, 'data.db')
DB_PATH = os.path.abspath(os.getenv('DB_PATH', _DEFAULT_DB_PATH))


async def init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('PRAGMA journal_mode=WAL;')
        await db.execute(
            '''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                created_at TEXT NOT NULL,
                last_active TEXT NOT NULL
            )
            '''
        )
        await db.execute(
            '''
            CREATE TABLE IF NOT EXISTS subscriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                plan TEXT NOT NULL,
                starts_at TEXT NOT NULL,
                ends_at TEXT NOT NULL,
                remaining INTEGER NOT NULL,
                status TEXT NOT NULL,
                auto_renew INTEGER NOT NULL DEFAULT 0,
                payment_method_id TEXT,
                provider TEXT DEFAULT 'manual',
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            '''
        )
        await db.execute(
            '''
            CREATE TABLE IF NOT EXISTS generations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                topic TEXT NOT NULL,
                slides INTEGER NOT NULL,
                success INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            '''
        )
        await db.execute(
            '''
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                provider TEXT NOT NULL,
                amount INTEGER NOT NULL,
                currency TEXT NOT NULL,
                payload TEXT,
                status TEXT NOT NULL,
                payment_method_id TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            '''
        )
        await db.execute(
            '''
            CREATE TABLE IF NOT EXISTS ad_tags (
                tag TEXT PRIMARY KEY,
                source TEXT NOT NULL,
                campaign TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            '''
        )
        await db.execute(
            '''
            CREATE TABLE IF NOT EXISTS user_tags (
                user_id INTEGER PRIMARY KEY,
                tag TEXT,
                raw TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            '''
        )
        await db.execute(
            '''
            CREATE TABLE IF NOT EXISTS admins (
                user_id INTEGER PRIMARY KEY,
                created_at TEXT NOT NULL
            )
            '''
        )
        await db.execute(
            '''
            CREATE TABLE IF NOT EXISTS promo_codes (
                code TEXT PRIMARY KEY,
                tokens INTEGER NOT NULL,
                max_uses INTEGER NOT NULL,
                used INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            '''
        )
        await db.execute(
            '''
            CREATE TABLE IF NOT EXISTS promo_uses (
                code TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                used_at TEXT NOT NULL,
                PRIMARY KEY (code, user_id),
                FOREIGN KEY(code) REFERENCES promo_codes(code),
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            '''
        )
        await db.execute(
            '''
            CREATE TABLE IF NOT EXISTS mailer_state (
                id INTEGER PRIMARY KEY,
                current_index INTEGER NOT NULL DEFAULT 0,
                next_run_at TEXT NOT NULL,
                preview_at TEXT NOT NULL,
                preview_sent INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            )
            '''
        )
        await _ensure_column(db, 'subscriptions', 'auto_renew', 'INTEGER NOT NULL DEFAULT 0')
        await _ensure_column(db, 'subscriptions', 'payment_method_id', 'TEXT')
        await _ensure_column(db, 'subscriptions', 'provider', "TEXT DEFAULT 'manual'")
        await _ensure_column(db, 'payments', 'payment_method_id', 'TEXT')
        await db.commit()


async def _ensure_column(db: aiosqlite.Connection, table: str, column: str, definition: str) -> None:
    cur = await db.execute(f'PRAGMA table_info({table})')
    rows = await cur.fetchall()
    existing = {row[1] if isinstance(row, tuple) else row['name'] for row in rows}
    if column in existing:
        return
    await db.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')


@asynccontextmanager
async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()
