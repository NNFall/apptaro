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
    templates_dir: Path
    temp_dir: Path
    bot_username: str
    app_share_url: str
    mailer_template_index: int


def load_config() -> AdminBotConfig:
    default_data_dir = ROOT_DIR / 'backend' / 'data'
    default_templates_dir = ROOT_DIR / 'backend' / 'runtime' / 'templates'
    default_temp_dir = ROOT_DIR / 'backend' / 'runtime' / 'temp'
    database_path = os.getenv('ADMIN_DATABASE_PATH', '').strip() or os.getenv(
        'DATABASE_PATH',
        str(default_data_dir / 'appslides.db'),
    )
    templates_dir = os.getenv('ADMIN_TEMPLATES_DIR', '').strip() or os.getenv(
        'TEMPLATES_DIR',
        str(default_templates_dir),
    )
    temp_dir = os.getenv('ADMIN_TEMP_DIR', '').strip() or os.getenv(
        'TEMP_DIR',
        str(default_temp_dir),
    )
    return AdminBotConfig(
        bot_token=os.getenv('ADMIN_BOT_TOKEN', '').strip(),
        admin_ids=_split_ints(os.getenv('ADMIN_IDS', '')),
        database_path=Path(database_path).resolve(),
        templates_dir=Path(templates_dir).resolve(),
        temp_dir=Path(temp_dir).resolve(),
        bot_username=os.getenv('ADMIN_BOT_USERNAME', '').strip(),
        app_share_url=os.getenv('APP_SHARE_URL', '').strip(),
        mailer_template_index=int(os.getenv('MAILER_TEMPLATE_INDEX', '5') or 5),
    )
