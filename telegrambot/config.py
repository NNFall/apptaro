from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import List, Dict, Any

from dotenv import load_dotenv

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(_BASE_DIR, '.env'))


def _split_ints(value: str) -> List[int]:
    if not value:
        return []
    return [int(x.strip()) for x in value.split(',') if x.strip()]


def _parse_json(value: str) -> Dict[str, Any]:
    if not value:
        return {}
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _split_strings(value: str) -> List[str]:
    if not value:
        return []
    return [x.strip() for x in value.split(',') if x.strip()]


@dataclass(frozen=True)
class Config:
    bot_token: str
    bot_username: str
    admin_ids: List[int]

    kie_api_key: str
    kie_base_url: str
    kie_api_url: str
    kie_text_model: str
    kie_text_endpoint: str
    kie_text_fallback_models: List[str]
    kie_image_model: str

    replicate_api_token: str
    replicate_base_url: str
    replicate_model: str
    replicate_wait_seconds: int
    replicate_poll_interval: float
    replicate_timeout_seconds: int
    replicate_default_input: Dict[str, Any]
    replicate_text_model: str
    replicate_text_prompt_field: str
    replicate_text_default_input: Dict[str, Any]
    image_concurrency: int

    libreoffice_path: str

    stars_provider_token: str
    yookassa_shop_id: str
    yookassa_secret: str
    yookassa_return_url: str
    yookassa_poll_interval: int
    yookassa_poll_timeout: int
    stars_week_amount: int
    stars_month_amount: int
    stars_one10_amount: int
    stars_one40_amount: int

    temp_dir: str
    templates_dir: str

    send_docx: bool
    log_file: str
    log_max_lines: int
    max_upload_mb: int
    download_timeout: int
    temp_ttl_seconds: int
    temp_clean_interval: int
    support_username: str
    offer_url: str
    auto_renew_interval: int
    font_fallback: str
    font_whitelist: List[str]
    fonts_dir: str
    mailer_enabled: bool
    mailer_template_index: int
    mailer_preview_minutes: int
    mailer_pause_hours: int
    mailer_tick_seconds: int
    mailer_rate_per_sec: int
    generation_timeout_seconds: int


def load_config() -> Config:
    return Config(
        bot_token=os.getenv('BOT_TOKEN', ''),
        bot_username=os.getenv('BOT_USERNAME', ''),
        admin_ids=_split_ints(os.getenv('ADMIN_IDS', '')),
        kie_api_key=os.getenv('KIE_API_KEY', ''),
        kie_base_url=os.getenv('KIE_BASE_URL', 'https://api.kie.ai'),
        kie_api_url=os.getenv('KIE_API_URL', ''),
        kie_text_model=os.getenv('KIE_TEXT_MODEL', 'gemini-flash'),
        kie_text_endpoint=os.getenv('KIE_TEXT_ENDPOINT', ''),
        kie_text_fallback_models=_split_strings(
            os.getenv('KIE_TEXT_FALLBACK_MODELS', 'gemini-2.5-flash,gemini-3-pro')
        ),
        kie_image_model=os.getenv('KIE_IMAGE_MODEL', 'flux-nano-banana'),
        replicate_api_token=os.getenv('REPLICATE_API_TOKEN', ''),
        replicate_base_url=os.getenv('REPLICATE_BASE_URL', 'https://api.replicate.com'),
        replicate_model=os.getenv('REPLICATE_MODEL', 'black-forest-labs/flux-schnell'),
        replicate_wait_seconds=int(os.getenv('REPLICATE_WAIT_SECONDS', '60')),
        replicate_poll_interval=float(os.getenv('REPLICATE_POLL_INTERVAL', '1.5')),
        replicate_timeout_seconds=int(os.getenv('REPLICATE_TIMEOUT_SECONDS', '120')),
        replicate_default_input=_parse_json(os.getenv('REPLICATE_DEFAULT_INPUT', '')),
        replicate_text_model=os.getenv('REPLICATE_TEXT_MODEL', 'google/gemini-3-flash'),
        replicate_text_prompt_field=os.getenv('REPLICATE_TEXT_PROMPT_FIELD', 'prompt'),
        replicate_text_default_input=_parse_json(os.getenv('REPLICATE_TEXT_DEFAULT_INPUT', '')),
        image_concurrency=int(os.getenv('IMAGE_CONCURRENCY', '5')),
        libreoffice_path=os.getenv('LIBREOFFICE_PATH', 'soffice'),
        stars_provider_token=os.getenv('STARS_PROVIDER_TOKEN', ''),
        yookassa_shop_id=os.getenv('YOOKASSA_SHOP_ID', ''),
        yookassa_secret=os.getenv('YOOKASSA_SECRET', os.getenv('YOOKASSA_SECRET_KEY', '')),
        yookassa_return_url=os.getenv('YOOKASSA_RETURN_URL', ''),
        yookassa_poll_interval=int(os.getenv('YOOKASSA_POLL_INTERVAL', '10')),
        yookassa_poll_timeout=int(os.getenv('YOOKASSA_POLL_TIMEOUT', '600')),
        stars_week_amount=int(os.getenv('STARS_WEEK_AMOUNT', '199')),
        stars_month_amount=int(os.getenv('STARS_MONTH_AMOUNT', '799')),
        stars_one10_amount=int(os.getenv('STARS_ONE10_AMOUNT', '199')),
        stars_one40_amount=int(os.getenv('STARS_ONE40_AMOUNT', '799')),
        temp_dir=os.getenv('TEMP_DIR', 'media/temp'),
        templates_dir=os.getenv('TEMPLATES_DIR', 'media/templates'),
        send_docx=os.getenv('SEND_DOCX', '0') == '1',
        log_file=os.getenv('LOG_FILE', os.path.join('logs', 'bot.log')),
        log_max_lines=int(os.getenv('LOG_MAX_LINES', '1000')),
        max_upload_mb=int(os.getenv('MAX_UPLOAD_MB', '40')),
        download_timeout=int(os.getenv('DOWNLOAD_TIMEOUT', '300')),
        temp_ttl_seconds=int(os.getenv('TEMP_TTL_SECONDS', '3600')),
        temp_clean_interval=int(os.getenv('TEMP_CLEAN_INTERVAL', '600')),
        support_username=os.getenv('SUPPORT_USERNAME', '@your_tracksupport'),
        offer_url=os.getenv('OFFER_URL', 'https://dimonk95.github.io/videofxai/'),
        auto_renew_interval=int(os.getenv('AUTO_RENEW_INTERVAL', '60')),
        font_fallback=os.getenv('FONT_FALLBACK', 'Cambria'),
        font_whitelist=_split_strings(os.getenv('FONT_WHITELIST', 'Cambria,Calibri,Arial,Times New Roman')),
        fonts_dir=os.getenv('FONTS_DIR', ''),
        mailer_enabled=os.getenv('MAILER_ENABLED', '1') == '1',
        mailer_template_index=int(os.getenv('MAILER_TEMPLATE_INDEX', '5')),
        mailer_preview_minutes=int(os.getenv('MAILER_PREVIEW_MINUTES', '30')),
        mailer_pause_hours=int(os.getenv('MAILER_PAUSE_HOURS', '12')),
        mailer_tick_seconds=int(os.getenv('MAILER_TICK_SECONDS', '30')),
        mailer_rate_per_sec=int(os.getenv('MAILER_RATE_PER_SEC', '25')),
        generation_timeout_seconds=int(os.getenv('GENERATION_TIMEOUT_SECONDS', '900')),
    )


PLANS = {
    'week': {'title': 'Неделя', 'price_rub': 199, 'limit': 10, 'days': 7},
    'month': {'title': 'Месяц', 'price_rub': 499, 'limit': 50, 'days': 30},
    'one10': {'title': 'Разово 10', 'price_rub': 199, 'limit': 10, 'days': 7},
    'one40': {'title': 'Разово 40', 'price_rub': 499, 'limit': 50, 'days': 7},
}
