from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, Header, HTTPException, status

from src.core.settings import get_settings
from src.domain.billing_service import BillingService
from src.domain.conversion_service import ConversionService
from src.domain.presentation_outline_service import PresentationOutlineService
from src.domain.presentation_render_service import PresentationRenderService
from src.integrations.admin_notifier import AdminNotifier
from src.integrations.yookassa_gateway import YooKassaGateway
from src.integrations.text_generation import PresentationGenerationClient
from src.repositories import billing as billing_repo


@lru_cache(maxsize=1)
def get_generation_client() -> PresentationGenerationClient:
    settings = get_settings()
    return PresentationGenerationClient(
        api_key=settings.kie_api_key,
        base_url=settings.kie_base_url,
        text_model=settings.kie_text_model,
        image_model=settings.kie_image_model,
        text_endpoint=settings.kie_text_endpoint,
        image_endpoint=settings.kie_image_endpoint,
        text_fallback_models=settings.kie_text_fallback_models,
        replicate_api_token=settings.replicate_api_token,
        replicate_base_url=settings.replicate_base_url,
        replicate_model=settings.replicate_model,
        replicate_default_input=settings.replicate_default_input,
        replicate_text_model=settings.replicate_text_model,
        replicate_text_prompt_field=settings.replicate_text_prompt_field,
        replicate_wait_seconds=settings.replicate_wait_seconds,
        replicate_poll_interval=settings.replicate_poll_interval,
        replicate_timeout_seconds=settings.replicate_timeout_seconds,
        replicate_text_default_input=settings.replicate_text_default_input,
        image_generation_retries=settings.image_generation_retries,
        image_generation_retry_delay_seconds=settings.image_generation_retry_delay_seconds,
    )


@lru_cache(maxsize=1)
def get_outline_service() -> PresentationOutlineService:
    settings = get_settings()
    return PresentationOutlineService(
        get_generation_client(),
        cards_dir=settings.tarot_cards_dir,
    )


@lru_cache(maxsize=1)
def get_render_service() -> PresentationRenderService:
    settings = get_settings()
    return PresentationRenderService(
        generation_client=get_generation_client(),
        temp_dir=settings.temp_dir,
        templates_dir=settings.templates_dir,
        tarot_cards_dir=settings.tarot_cards_dir,
        tarot_background_path=settings.tarot_background_path,
        tarot_layout_path=settings.tarot_layout_path,
        libreoffice_path=settings.libreoffice_path,
        image_concurrency=settings.image_concurrency,
    )


@lru_cache(maxsize=1)
def get_conversion_service() -> ConversionService:
    settings = get_settings()
    return ConversionService(
        temp_dir=settings.temp_dir,
        libreoffice_path=settings.libreoffice_path,
    )


@lru_cache(maxsize=1)
def get_yookassa_gateway() -> YooKassaGateway:
    settings = get_settings()
    return YooKassaGateway(
        shop_id=settings.yookassa_shop_id,
        secret_key=settings.yookassa_secret,
        return_url=settings.yookassa_return_url,
        receipt_email=settings.yookassa_receipt_email,
        receipt_phone=settings.yookassa_receipt_phone,
        tax_system_code=settings.yookassa_tax_system_code,
        vat_code=settings.yookassa_vat_code,
        item_name=settings.yookassa_item_name,
        payment_subject=settings.yookassa_payment_subject,
        payment_mode=settings.yookassa_payment_mode,
    )


@lru_cache(maxsize=1)
def get_billing_service() -> BillingService:
    settings = get_settings()
    return BillingService(
        gateway=get_yookassa_gateway(),
        offer_url=settings.offer_url,
        support_username=settings.support_username,
        return_url=settings.yookassa_return_url or settings.offer_url,
        test_mode=settings.yookassa_test_mode,
        notifier=get_admin_notifier(),
    )


@lru_cache(maxsize=1)
def get_admin_notifier() -> AdminNotifier:
    settings = get_settings()
    return AdminNotifier(
        bot_token=settings.admin_bot_token,
        admin_ids=settings.admin_ids,
    )


def get_client_id(
    x_apptaro_client_id: str | None = Header(default=None, alias='X-Apptaro-Client-Id'),
    x_appslides_client_id: str | None = Header(default=None, alias='X-AppSlides-Client-Id'),
) -> str:
    client_id = (x_apptaro_client_id or x_appslides_client_id or '').strip()
    if len(client_id) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Missing or invalid X-Apptaro-Client-Id header',
        )
    return client_id


async def get_known_client_id(
    client_id: str = Depends(get_client_id),
    notifier: AdminNotifier = Depends(get_admin_notifier),
) -> str:
    is_new = billing_repo.touch_client(client_id)
    if is_new:
        await notifier.notify_new_client(client_id)
    return client_id
