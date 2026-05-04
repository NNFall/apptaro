from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path
from threading import RLock

from src.core.settings import get_settings


_LOCK = RLock()
_DATABASE_PATH: Path | None = None
_INITIALIZED = False


def configure_database_path(path: str | Path) -> Path:
    global _DATABASE_PATH, _INITIALIZED
    with _LOCK:
        _DATABASE_PATH = Path(path).resolve()
        _INITIALIZED = False
        return _DATABASE_PATH


def get_database_path() -> Path:
    global _DATABASE_PATH
    with _LOCK:
        if _DATABASE_PATH is None:
            _DATABASE_PATH = get_settings().database_path.resolve()
        return _DATABASE_PATH


def init_storage(path: str | Path | None = None) -> Path:
    global _INITIALIZED
    db_path = configure_database_path(path) if path is not None else get_database_path()
    with _LOCK:
        if _INITIALIZED:
            return db_path

        db_path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(str(db_path), timeout=30, check_same_thread=False)) as conn:
            conn.execute('PRAGMA journal_mode=WAL;')
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    job_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    input_data TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    error TEXT,
                    result TEXT,
                    meta TEXT NOT NULL DEFAULT '{}'
                )
                '''
            )
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    filename TEXT NOT NULL,
                    media_type TEXT NOT NULL,
                    path TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                '''
            )
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS billing_clients (
                    client_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    free_trial_used INTEGER NOT NULL DEFAULT 0
                )
                '''
            )
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS billing_subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id TEXT NOT NULL,
                    plan_key TEXT NOT NULL,
                    starts_at TEXT NOT NULL,
                    ends_at TEXT NOT NULL,
                    remaining INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    auto_renew INTEGER NOT NULL DEFAULT 0,
                    payment_method_id TEXT,
                    provider TEXT NOT NULL DEFAULT 'manual',
                    created_at TEXT NOT NULL
                )
                '''
            )
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS billing_payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    amount INTEGER NOT NULL,
                    currency TEXT NOT NULL,
                    plan_key TEXT NOT NULL,
                    external_payment_id TEXT NOT NULL UNIQUE,
                    status TEXT NOT NULL,
                    payment_method_id TEXT,
                    confirmation_url TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                '''
            )
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS admins (
                    user_id INTEGER PRIMARY KEY,
                    created_at TEXT NOT NULL
                )
                '''
            )
            conn.execute(
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
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS client_tags (
                    client_id TEXT NOT NULL,
                    tag TEXT NOT NULL,
                    raw TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(client_id, tag)
                )
                '''
            )
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS promo_codes (
                    code TEXT PRIMARY KEY,
                    tokens INTEGER NOT NULL,
                    max_uses INTEGER NOT NULL,
                    used INTEGER NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                )
                '''
            )
            conn.execute(
                '''
                CREATE TABLE IF NOT EXISTS promo_uses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(code, client_id)
                )
                '''
            )
            conn.execute(
                'CREATE INDEX IF NOT EXISTS idx_jobs_type_status ON jobs(job_type, status)'
            )
            conn.execute(
                'CREATE INDEX IF NOT EXISTS idx_artifacts_kind ON artifacts(kind)'
            )
            conn.execute(
                '''
                CREATE INDEX IF NOT EXISTS idx_billing_subscriptions_client_status
                ON billing_subscriptions(client_id, status)
                '''
            )
            conn.execute(
                '''
                CREATE INDEX IF NOT EXISTS idx_billing_subscriptions_due
                ON billing_subscriptions(status, auto_renew, ends_at)
                '''
            )
            conn.execute(
                '''
                CREATE INDEX IF NOT EXISTS idx_billing_payments_client_status
                ON billing_payments(client_id, status)
                '''
            )
            conn.execute(
                'CREATE INDEX IF NOT EXISTS idx_client_tags_tag ON client_tags(tag)'
            )
            conn.execute(
                'CREATE INDEX IF NOT EXISTS idx_promo_uses_code ON promo_uses(code)'
            )
            _ensure_column(
                conn,
                table='billing_clients',
                column='free_trial_used',
                definition='INTEGER NOT NULL DEFAULT 0',
            )
            conn.commit()

        _INITIALIZED = True
        return db_path


def connect() -> sqlite3.Connection:
    if not _INITIALIZED:
        init_storage()
    conn = sqlite3.connect(str(get_database_path()), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_column(
    conn: sqlite3.Connection,
    *,
    table: str,
    column: str,
    definition: str,
) -> None:
    try:
        conn.execute(f'ALTER TABLE {table} ADD COLUMN {column} {definition}')
    except sqlite3.OperationalError as exc:
        if 'duplicate column name' not in str(exc).lower():
            raise
