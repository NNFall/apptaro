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


PLANS: dict[str, BillingPlan] = {
    'week': BillingPlan(
        key='week',
        title='Неделя раскладов',
        price_rub=199,
        limit=15,
        days=7,
        recurring=True,
    ),
    'month': BillingPlan(
        key='month',
        title='Месяц раскладов',
        price_rub=499,
        limit=100,
        days=30,
        recurring=True,
    ),
    'one10': BillingPlan(
        key='one10',
        title='Разово 10 раскладов',
        price_rub=199,
        limit=10,
        days=7,
        recurring=False,
    ),
    'one40': BillingPlan(
        key='one40',
        title='Разово 40 раскладов',
        price_rub=499,
        limit=50,
        days=7,
        recurring=False,
    ),
}


def get_plan(plan_key: str) -> BillingPlan:
    try:
        return PLANS[plan_key]
    except KeyError as exc:  # pragma: no cover - defensive
        raise ValueError(f'Unknown billing plan: {plan_key}') from exc


def list_plans() -> list[BillingPlan]:
    return list(PLANS.values())
