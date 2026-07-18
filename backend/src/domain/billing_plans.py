from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BillingPlan:
    key: str
    title: str
    price_rub: int
    limit: int
    days: int
    recurring: bool
    google_product_id: str


PLANS: dict[str, BillingPlan] = {
    'week': BillingPlan(
        key='week',
        title='Weekly tarot readings',
        price_rub=199,
        limit=15,
        days=7,
        recurring=True,
        google_product_id='weekly_readings',
    ),
    'month': BillingPlan(
        key='month',
        title='Monthly tarot readings',
        price_rub=499,
        limit=100,
        days=30,
        recurring=True,
        google_product_id='monthly_readings',
    ),
    'one10': BillingPlan(
        key='one10',
        title='10 tarot readings',
        price_rub=199,
        limit=10,
        days=7,
        recurring=False,
        google_product_id='one10_readings',
    ),
    'one40': BillingPlan(
        key='one40',
        title='40 tarot readings',
        price_rub=499,
        limit=40,
        days=7,
        recurring=False,
        google_product_id='one40_readings',
    ),
}


def get_plan(plan_key: str) -> BillingPlan:
    try:
        return PLANS[plan_key]
    except KeyError as exc:  # pragma: no cover - defensive
        raise ValueError(f'Unknown billing plan: {plan_key}') from exc


def list_plans() -> list[BillingPlan]:
    return list(PLANS.values())


def get_plan_by_google_product_id(product_id: str) -> BillingPlan:
    normalized = product_id.strip()
    for plan in PLANS.values():
        if plan.google_product_id == normalized:
            return plan
    raise ValueError(f'Unknown Google Play product: {product_id}')


def get_plan_by_store_product_id(product_id: str) -> BillingPlan:
    normalized = product_id.strip()
    for plan in PLANS.values():
        if plan.google_product_id == normalized:
            return plan
    raise ValueError(f'Unknown store product: {product_id}')
