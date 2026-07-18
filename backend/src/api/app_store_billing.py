from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.billing import _summary_response
from src.core.dependencies import get_app_store_billing_service, get_known_client_id
from src.domain.app_store_billing_service import AppStoreBillingService
from src.integrations.app_store_gateway import AppStoreGatewayError, AppStoreValidationError
from src.schemas.billing import (
    AppleAccountTokenResponse,
    AppleVerifyRequest,
    BillingSummaryResponse,
)


router = APIRouter(prefix='/v1/billing/apple', tags=['billing'])


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
    return _summary_response(summary)
