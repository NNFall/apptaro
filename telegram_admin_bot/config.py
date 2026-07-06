from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / 'backend'
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


load_dotenv(ROOT_DIR / 'telegram_admin_bot' / '.env')


def _split_ints(value: str) -> list[int]:
    if not value:
        return []
    result: list[int] = []
    for chunk in value.split(','):
        chunk = chunk.strip()
        if not chunk:
            continue
        result.append(int(chunk))
    return result


@dataclass(frozen=True)
class AdminBotConfig:
    bot_token: str
    admin_ids: list[int]
    database_path: Path
    bot_username: str
    app_share_url: str
    heartbeat_path: Path
    polling_timeout_seconds: int
    polling_retry_max_seconds: int


def load_config() -> AdminBotConfig:
    default_data_dir = ROOT_DIR / 'backend' / 'data'
    database_path = os.getenv('ADMIN_DATABASE_PATH', '').strip() or os.getenv(
        'DATABASE_PATH',
        str(default_data_dir / 'pmapptaro.db'),
    )
    heartbeat_path = os.getenv('ADMIN_BOT_HEARTBEAT_PATH', '/tmp/admin_bot.heartbeat').strip()
    return AdminBotConfig(
        bot_token=os.getenv('ADMIN_BOT_TOKEN', '').strip(),
        admin_ids=_split_ints(os.getenv('ADMIN_IDS', '')),
        database_path=Path(database_path).resolve(),
        bot_username=os.getenv('ADMIN_BOT_USERNAME', '').strip(),
        app_share_url=os.getenv('APP_SHARE_URL', '').strip(),
        heartbeat_path=Path(heartbeat_path),
        polling_timeout_seconds=int(os.getenv('ADMIN_BOT_POLLING_TIMEOUT_SECONDS', '50') or 50),
        polling_retry_max_seconds=int(os.getenv('ADMIN_BOT_POLLING_RETRY_MAX_SECONDS', '30') or 30),
    )
