from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from src.core.dependencies import get_billing_service, get_known_client_id
from src.domain.billing_service import BillingService
from src.schemas.billing import (
    BillingSummaryResponse,
    CreateBillingPaymentRequest,
    GooglePlayVerifyRequest,
    RedeemPromoCodeRequest,
    RedeemPromoCodeResponse,
)


router = APIRouter(prefix='/v1/billing', tags=['billing'])


def _summary_response(summary) -> BillingSummaryResponse:
    def _subscription(item):
        if item is None:
            return None
        return {
            'plan_key': item.plan_key,
            'status': item.status,
            'remaining': item.remaining,
            'starts_at': item.starts_at,
            'ends_at': item.ends_at,
            'auto_renew': bool(item.auto_renew),
            'provider': item.provider,
        }

    return BillingSummaryResponse(
        client_id=summary.client_id,
        support_username=summary.support_username,
        support_max_url=summary.support_max_url,
        offer_url=summary.offer_url,
        test_mode=summary.test_mode,
        plans=[
            {
                'key': plan.key,
                'title': plan.title,
                'price_rub': plan.price_rub,
                'limit': plan.limit,
                'days': plan.days,
                'recurring': plan.recurring,
                'google_product_id': plan.google_product_id,
            }
            for plan in summary.plans
        ],
        active_subscription=_subscription(summary.active_subscription),
        latest_valid_subscription=_subscription(summary.latest_valid_subscription),
    )


def _raise_redirect_billing_disabled() -> None:
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail='Redirect billing is disabled in the Google Play build. Use /v1/billing/google-play/verify.',
    )


@router.get('/summary', response_model=BillingSummaryResponse)
async def get_billing_summary(
    client_id: str = Depends(get_known_client_id),
    service: BillingService = Depends(get_billing_service),
) -> BillingSummaryResponse:
    summary = await service.get_summary(client_id)
    return _summary_response(summary)


@router.post('/payments', status_code=status.HTTP_410_GONE)
async def create_billing_payment(
    payload: CreateBillingPaymentRequest,
) -> None:
    _ = payload
    _raise_redirect_billing_disabled()


@router.post('/google-play/verify', response_model=BillingSummaryResponse)
async def verify_google_play_purchase(
    payload: GooglePlayVerifyRequest,
    client_id: str = Depends(get_known_client_id),
    service: BillingService = Depends(get_billing_service),
) -> BillingSummaryResponse:
    try:
        summary = await service.verify_google_play_purchase(
            client_id=client_id,
            product_id=payload.product_id,
            purchase_token=payload.purchase_token,
            package_name=payload.package_name,
            restored=payload.restored,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return _summary_response(summary)


@router.get('/payments/{payment_id}', status_code=status.HTTP_410_GONE)
async def get_billing_payment(
    payment_id: str,
) -> None:
    _ = payment_id
    _raise_redirect_billing_disabled()


@router.post('/subscription/cancel', response_model=BillingSummaryResponse)
async def cancel_billing_subscription(
    client_id: str = Depends(get_known_client_id),
    service: BillingService = Depends(get_billing_service),
) -> BillingSummaryResponse:
    summary = await service.cancel_subscription(client_id)
    return _summary_response(summary)


@router.post('/promo/redeem', response_model=RedeemPromoCodeResponse)
async def redeem_billing_promo_code(
    payload: RedeemPromoCodeRequest,
    client_id: str = Depends(get_known_client_id),
    service: BillingService = Depends(get_billing_service),
) -> RedeemPromoCodeResponse:
    try:
        summary, granted_tokens = await service.redeem_promo_code(
            client_id=client_id,
            code=payload.code,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return RedeemPromoCodeResponse(
        granted_tokens=granted_tokens,
        summary=_summary_response(summary),
    )
