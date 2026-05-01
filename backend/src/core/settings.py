from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_ROOT = Path(__file__).resolve().parents[3]
TELEGRAMBOT_DIR = PROJECT_ROOT / 'telegrambot'
ADMIN_BOT_DIR = PROJECT_ROOT / 'telegram_admin_bot'


def _load_env_files() -> None:
    for path in (
        BACKEND_DIR / '.env',
        PROJECT_ROOT / '.env',
        TELEGRAMBOT_DIR / '.env',
        ADMIN_BOT_DIR / '.env',
    ):
        if path.exists():
            load_dotenv(path, override=False)


_load_env_files()


def _split_strings(value: str) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(',') if item.strip()]


def _parse_json(value: str) -> dict[str, Any]:
    if not value:
        return {}
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _resolve_path(raw: str, fallback: Path) -> Path:
    if not raw:
        return fallback.resolve()

    path = Path(raw)
    if path.is_absolute():
        return path.resolve()

    candidates = (
        BACKEND_DIR / path,
        PROJECT_ROOT / path,
        TELEGRAMBOT_DIR / path,
    )
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    return (BACKEND_DIR / path).resolve()


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_env: str
    app_version: str
    app_host: str
    app_port: int
    log_level: str
    cors_allow_origins: list[str]

    kie_api_key: str
    kie_base_url: str
    kie_text_model: str
    kie_text_endpoint: str
    kie_text_fallback_models: list[str]
    kie_image_model: str
    kie_image_endpoint: str

    replicate_api_token: str
    replicate_base_url: str
    replicate_model: str
    replicate_default_input: dict[str, Any]
    replicate_text_model: str
    replicate_text_prompt_field: str
    replicate_wait_seconds: int
    replicate_poll_interval: float
    replicate_timeout_seconds: int
    replicate_text_default_input: dict[str, Any]
    image_concurrency: int
    image_generation_retries: int
    image_generation_retry_delay_seconds: float

    libreoffice_path: str
    font_fallback: str
    font_whitelist: list[str]
    fonts_dir: Path
    support_username: str
    offer_url: str

    data_dir: Path
    database_path: Path
    temp_dir: Path
    templates_dir: Path

    yookassa_shop_id: str
    yookassa_secret: str
    yookassa_return_url: str
    yookassa_poll_interval: int
    yookassa_poll_timeout: int
    yookassa_receipt_email: str
    yookassa_receipt_phone: str
    yookassa_tax_system_code: int
    yookassa_vat_code: int
    yookassa_item_name: str
    yookassa_payment_subject: str
    yookassa_payment_mode: str
    yookassa_test_mode: bool
    auto_renew_interval: int
    admin_bot_token: str
    admin_ids: list[str]


def load_settings() -> Settings:
    default_data_dir = BACKEND_DIR / 'data'
    default_database_path = default_data_dir / 'appslides.db'
    default_temp_dir = BACKEND_DIR / 'runtime' / 'temp'
    default_templates_dir = BACKEND_DIR / 'runtime' / 'templates'
    default_fonts_dir = BACKEND_DIR / 'runtime' / 'fonts'
    return Settings(
        app_name=os.getenv('APP_NAME', 'AppSlides Backend'),
        app_env=os.getenv('APP_ENV', 'development'),
        app_version=os.getenv('APP_VERSION', '0.1.0'),
        app_host=os.getenv('APP_HOST', '0.0.0.0'),
        app_port=int(os.getenv('APP_PORT', '8000')),
        log_level=os.getenv('LOG_LEVEL', 'INFO').upper(),
        cors_allow_origins=_split_strings(os.getenv('CORS_ALLOW_ORIGINS', '*')) or ['*'],
        kie_api_key=os.getenv('KIE_API_KEY', ''),
        kie_base_url=os.getenv('KIE_BASE_URL', 'https://api.kie.ai'),
        kie_text_model=os.getenv('KIE_TEXT_MODEL', 'gemini-flash'),
        kie_text_endpoint=os.getenv('KIE_TEXT_ENDPOINT', ''),
        kie_text_fallback_models=_split_strings(
            os.getenv('KIE_TEXT_FALLBACK_MODELS', 'gemini-2.5-flash,gemini-3-pro')
        ),
        kie_image_model=os.getenv('KIE_IMAGE_MODEL', 'flux-nano-banana'),
        kie_image_endpoint=os.getenv('KIE_IMAGE_ENDPOINT', ''),
        replicate_api_token=os.getenv('REPLICATE_API_TOKEN', ''),
        replicate_base_url=os.getenv('REPLICATE_BASE_URL', 'https://api.replicate.com'),
        replicate_model=os.getenv('REPLICATE_MODEL', 'black-forest-labs/flux-schnell'),
        replicate_default_input=_parse_json(os.getenv('REPLICATE_DEFAULT_INPUT', '')),
        replicate_text_model=os.getenv('REPLICATE_TEXT_MODEL', 'google/gemini-3-flash'),
        replicate_text_prompt_field=os.getenv('REPLICATE_TEXT_PROMPT_FIELD', 'prompt'),
        replicate_wait_seconds=int(os.getenv('REPLICATE_WAIT_SECONDS', '60')),
        replicate_poll_interval=float(os.getenv('REPLICATE_POLL_INTERVAL', '1.5')),
        replicate_timeout_seconds=int(os.getenv('REPLICATE_TIMEOUT_SECONDS', '120')),
        replicate_text_default_input=_parse_json(os.getenv('REPLICATE_TEXT_DEFAULT_INPUT', '')),
        image_concurrency=int(os.getenv('IMAGE_CONCURRENCY', '5')),
        image_generation_retries=int(os.getenv('IMAGE_GENERATION_RETRIES', '2')),
        image_generation_retry_delay_seconds=float(os.getenv('IMAGE_GENERATION_RETRY_DELAY_SECONDS', '2.0')),
        libreoffice_path=os.getenv('LIBREOFFICE_PATH', 'soffice'),
        font_fallback=os.getenv('FONT_FALLBACK', 'Cambria'),
        font_whitelist=_split_strings(os.getenv('FONT_WHITELIST', 'Cambria,Calibri,Arial,Times New Roman')),
        fonts_dir=_resolve_path(os.getenv('FONTS_DIR', ''), default_fonts_dir),
        support_username=os.getenv('SUPPORT_USERNAME', '@your_tracksupport'),
        offer_url=os.getenv('OFFER_URL', 'https://dimonk95.github.io/slide_ai/'),
        data_dir=_resolve_path(os.getenv('DATA_DIR', ''), default_data_dir),
        database_path=_resolve_path(os.getenv('DATABASE_PATH', ''), default_database_path),
        temp_dir=_resolve_path(os.getenv('TEMP_DIR', ''), default_temp_dir),
        templates_dir=_resolve_path(os.getenv('TEMPLATES_DIR', ''), default_templates_dir),
        yookassa_shop_id=os.getenv('YOOKASSA_SHOP_ID', ''),
        yookassa_secret=os.getenv('YOOKASSA_SECRET', os.getenv('YOOKASSA_SECRET_KEY', '')),
        yookassa_return_url=os.getenv('YOOKASSA_RETURN_URL', ''),
        yookassa_poll_interval=int(os.getenv('YOOKASSA_POLL_INTERVAL', '10')),
        yookassa_poll_timeout=int(os.getenv('YOOKASSA_POLL_TIMEOUT', '600')),
        yookassa_receipt_email=os.getenv('YOOKASSA_RECEIPT_EMAIL', '').strip(),
        yookassa_receipt_phone=os.getenv('YOOKASSA_RECEIPT_PHONE', '').strip(),
        yookassa_tax_system_code=int(os.getenv('YOOKASSA_TAX_SYSTEM_CODE', '1') or 1),
        yookassa_vat_code=int(os.getenv('YOOKASSA_VAT_CODE', '1') or 1),
        yookassa_item_name=os.getenv('YOOKASSA_ITEM_NAME', 'Подписка на генерации AppSlides'),
        yookassa_payment_subject=os.getenv('YOOKASSA_PAYMENT_SUBJECT', 'service') or 'service',
        yookassa_payment_mode=os.getenv('YOOKASSA_PAYMENT_MODE', 'full_prepayment') or 'full_prepayment',
        yookassa_test_mode=os.getenv('YOOKASSA_TEST_MODE', '1') == '1',
        auto_renew_interval=int(os.getenv('AUTO_RENEW_INTERVAL', '60')),
        admin_bot_token=os.getenv('ADMIN_BOT_TOKEN', '').strip(),
        admin_ids=_split_strings(os.getenv('ADMIN_IDS', '')),
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()
