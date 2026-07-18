from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, status

from src.api.billing import _summary_response
from src.core.dependencies import (
    get_admin_notifier,
    get_app_store_billing_service,
    get_known_client_id,
)
from src.domain.app_store_billing_service import AppStoreBillingService
from src.integrations.admin_notifier import AdminNotifier
from src.integrations.app_store_gateway import AppStoreGatewayError, AppStoreValidationError
from src.schemas.billing import (
    AppleAccountTokenResponse,
    AppleVerifyRequest,
    BillingSummaryResponse,
)


router = APIRouter(prefix='/v1/billing/apple', tags=['billing'])

APPLE_NOTIFICATION_MAX_BODY_BYTES = 64 * 1024
APPLE_SIGNED_PAYLOAD_MAX_CHARS = 48 * 1024


class _NotificationBodyTooLarge(ValueError):
    pass


@router.post('/account-token', response_model=AppleAccountTokenResponse)
async def get_account_token(
    client_id: str = Depends(get_known_client_id),
    service: AppStoreBillingService = Depends(get_app_store_billing_service),
) -> AppleAccountTokenResponse:
    return AppleAccountTokenResponse(
        app_account_token=service.get_or_create_account_token(client_id),
    )


@router.post('/verify', response_model=BillingSummaryResponse)
async def verify_purchase(
    payload: AppleVerifyRequest,
    client_id: str = Depends(get_known_client_id),
    service: AppStoreBillingService = Depends(get_app_store_billing_service),
    notifier: AdminNotifier = Depends(get_admin_notifier),
) -> BillingSummaryResponse:
    try:
        summary = await service.verify_transaction(
            client_id=client_id,
            transaction_id=payload.transaction_id,
            product_id=payload.product_id,
            operation=payload.operation,
            client_signed_data=payload.client_signed_data,
        )
    except AppStoreValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Apple purchase could not be verified',
        ) from exc
    except AppStoreGatewayError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='App Store verification is temporarily unavailable',
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='App Store verification is temporarily unavailable',
        ) from exc
    try:
        await service.deliver_admin_events(notifier)
    except Exception:  # noqa: BLE001 - durable outbox remains pending for background retry
        pass
    return _summary_response(summary)


@router.post('/notifications')
async def receive_notification(
    request: Request,
    service: AppStoreBillingService = Depends(get_app_store_billing_service),
    notifier: AdminNotifier = Depends(get_admin_notifier),
) -> dict[str, str]:
    try:
        raw_body = await _read_bounded_notification_body(request)
    except _NotificationBodyTooLarge:
        await _persist_validation_failure(
            service,
            notifier,
            'apple-webhook:oversized-body',
            'notification request exceeded size limit',
        )
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail='Apple notification request is too large',
        )
    try:
        body = json.loads(raw_body)
    except (ValueError, UnicodeDecodeError):
        await _persist_validation_failure(
            service,
            notifier,
            'apple-webhook:malformed-json',
            'malformed notification request',
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Apple notification request is invalid',
        )
    signed_payload, malformed_fingerprint = _signed_payload_from_body(body)
    if signed_payload is None:
        await _persist_validation_failure(
            service,
            notifier,
            malformed_fingerprint,
            'malformed notification request',
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Apple notification request is invalid',
        )
    if len(signed_payload) > APPLE_SIGNED_PAYLOAD_MAX_CHARS:
        await _persist_validation_failure(
            service,
            notifier,
            'apple-webhook:oversized-signed-payload',
            'signed payload exceeded size limit',
        )
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail='Apple notification request is too large',
        )
    try:
        await service.process_notification(signed_payload)
    except AppStoreValidationError as exc:
        await _persist_validation_failure(
            service,
            notifier,
            signed_payload,
            'signature verification failed',
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Apple notification could not be verified',
        ) from exc
    except (AppStoreGatewayError, RuntimeError, sqlite3.Error) as exc:
        await _persist_validation_failure(
            service,
            notifier,
            signed_payload,
            'temporary verification or storage failure',
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail='App Store notification processing is temporarily unavailable',
        ) from exc
    except ValueError as exc:
        await _persist_validation_failure(
            service,
            notifier,
            signed_payload,
            'verified notification payload was rejected',
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Apple notification payload is invalid',
        ) from exc
    try:
        await service.deliver_admin_events(notifier)
    except Exception:  # noqa: BLE001 - notification is durable; worker retries the outbox
        pass
    return {'status': 'ok'}


async def _read_bounded_notification_body(request: Request) -> bytes:
    content_length = request.headers.get('content-length', '').strip()
    if content_length:
        try:
            if int(content_length) > APPLE_NOTIFICATION_MAX_BODY_BYTES:
                raise _NotificationBodyTooLarge
        except ValueError:
            pass
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > APPLE_NOTIFICATION_MAX_BODY_BYTES:
            raise _NotificationBodyTooLarge
    return bytes(body)


def _signed_payload_from_body(body: object) -> tuple[str | None, str]:
    if not isinstance(body, dict):
        return None, f'apple-webhook:body-type:{type(body).__name__}'
    if 'signedPayload' not in body:
        return None, 'apple-webhook:missing-signed-payload'
    value = body['signedPayload']
    if not isinstance(value, str):
        return None, f'apple-webhook:signed-payload-type:{type(value).__name__}'
    normalized = value.strip()
    if not normalized:
        return None, 'apple-webhook:empty-signed-payload'
    return normalized, ''


async def _persist_validation_failure(
    service: AppStoreBillingService,
    notifier: AdminNotifier,
    signed_payload: str,
    detail: str,
) -> None:
    try:
        created = await service.record_validation_failure(signed_payload, detail)
        if created:
            await service.deliver_admin_events(notifier)
    except Exception:  # noqa: BLE001 - never expose or log the untrusted signed payload
        pass
