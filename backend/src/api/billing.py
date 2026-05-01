from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from src.core.dependencies import get_billing_service, get_known_client_id
from src.domain.billing_service import BillingService
from src.schemas.billing import BillingPaymentResponse, BillingSummaryResponse, CreateBillingPaymentRequest


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
            }
            for plan in summary.plans
        ],
        active_subscription=_subscription(summary.active_subscription),
        latest_valid_subscription=_subscription(summary.latest_valid_subscription),
    )


def _payment_response(result) -> BillingPaymentResponse:
    return BillingPaymentResponse(
        payment_id=result.payment_id,
        status=result.status,
        confirmation_url=result.confirmation_url,
        test_mode=result.test_mode,
        summary=_summary_response(result.summary),
    )

@router.get('/summary', response_model=BillingSummaryResponse)
async def get_billing_summary(
    client_id: str = Depends(get_known_client_id),
    service: BillingService = Depends(get_billing_service),
) -> BillingSummaryResponse:
    summary = await service.get_summary(client_id)
    return _summary_response(summary)


@router.post('/payments', response_model=BillingPaymentResponse)
async def create_billing_payment(
    payload: CreateBillingPaymentRequest,
    client_id: str = Depends(get_known_client_id),
    service: BillingService = Depends(get_billing_service),
) -> BillingPaymentResponse:
    try:
        result = await service.create_payment(
            client_id=client_id,
            plan_key=payload.plan_key,
            context=payload.context,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _payment_response(result)


@router.get('/payments/{payment_id}', response_model=BillingPaymentResponse)
async def get_billing_payment(
    payment_id: str,
    client_id: str = Depends(get_known_client_id),
    service: BillingService = Depends(get_billing_service),
) -> BillingPaymentResponse:
    try:
        result = await service.sync_payment(client_id=client_id, payment_id=payment_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _payment_response(result)


@router.post('/subscription/cancel', response_model=BillingSummaryResponse)
async def cancel_billing_subscription(
    client_id: str = Depends(get_known_client_id),
    service: BillingService = Depends(get_billing_service),
) -> BillingSummaryResponse:
    summary = await service.cancel_subscription(client_id)
    return _summary_response(summary)
