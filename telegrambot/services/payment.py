from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Tuple, Optional, Any, Dict
import os

from yookassa import Configuration, Payment

from config import PLANS
from services.logger import get_logger


logger = get_logger()


@dataclass(frozen=True)
class PaymentConfig:
    stars_provider_token: str
    yookassa_shop_id: str
    yookassa_secret: str
    yookassa_return_url: str


def build_payload(plan_key: str, user_id: int) -> str:
    return f'plan={plan_key};user={user_id};ts={int(time.time())}'


def parse_payload(payload: str) -> Tuple[str, int]:
    parts = dict(item.split('=') for item in payload.split(';') if '=' in item)
    return parts.get('plan', ''), int(parts.get('user', '0') or 0)


def get_plan(plan_key: str) -> dict:
    return PLANS[plan_key]


def init_yookassa(shop_id: str, secret: str) -> None:
    Configuration.account_id = shop_id
    Configuration.secret_key = secret


def create_yookassa_payment(
    plan_key: str,
    user_id: int,
    amount_rub: int,
    return_url: str,
    save_payment_method: bool = True,
) -> Tuple[str, str]:
    plan_title = PLANS.get(plan_key, {}).get('title', plan_key)
    payload = {
        'amount': {'value': f'{amount_rub:.2f}', 'currency': 'RUB'},
        'confirmation': {'type': 'redirect', 'return_url': return_url},
        'capture': True,
        'description': f'Подписка {plan_title}',
        'metadata': {'user_id': str(user_id), 'plan_key': plan_key},
    }
    receipt = _build_receipt(amount_rub, f'Подписка {plan_title}')
    if receipt:
        payload['receipt'] = receipt
    if save_payment_method:
        payload['save_payment_method'] = True
    idempotence_key = str(uuid.uuid4())
    logger.info('YooKassa create payment: plan=%s user=%s amount=%s', plan_key, user_id, amount_rub)
    payment = Payment.create(payload, idempotence_key)
    confirmation_url = payment.confirmation.confirmation_url
    return payment.id, confirmation_url


def create_yookassa_recurring_payment(
    plan_key: str,
    user_id: int,
    amount_rub: int,
    payment_method_id: str,
) -> Payment:
    plan_title = PLANS.get(plan_key, {}).get('title', plan_key)
    description = f'Подписка {plan_title} - продление (автосписание)'
    payload = {
        'amount': {'value': f'{amount_rub:.2f}', 'currency': 'RUB'},
        'capture': True,
        'description': description,
        'metadata': {'user_id': str(user_id), 'plan_key': plan_key, 'type': 'auto_renew'},
        'payment_method_id': payment_method_id,
    }
    receipt = _build_receipt(amount_rub, description)
    if receipt:
        payload['receipt'] = receipt
    idempotence_key = str(uuid.uuid4())
    logger.info('YooKassa auto-charge: plan=%s user=%s amount=%s', plan_key, user_id, amount_rub)
    return Payment.create(payload, idempotence_key)


def get_yookassa_payment(payment_id: str) -> Optional[Payment]:
    logger.info('YooKassa check payment: id=%s', payment_id)
    return Payment.find_one(payment_id)


def _build_receipt(amount_rub: int, description: str) -> Optional[Dict[str, Any]]:
    email = os.getenv('YOOKASSA_RECEIPT_EMAIL', '').strip()
    if not email:
        return None
    try:
        tax_system_code = int(os.getenv('YOOKASSA_TAX_SYSTEM_CODE', '1') or 1)
    except ValueError:
        tax_system_code = 1
    try:
        vat_code = int(os.getenv('YOOKASSA_VAT_CODE', '1') or 1)
    except ValueError:
        vat_code = 1
    payment_subject = os.getenv('YOOKASSA_PAYMENT_SUBJECT', 'service') or 'service'
    payment_mode = os.getenv('YOOKASSA_PAYMENT_MODE', 'full_prepayment') or 'full_prepayment'
    return {
        'customer': {'email': email},
        'tax_system_code': tax_system_code,
        'items': [
            {
                'description': description[:128],
                'quantity': '1.00',
                'amount': {'value': f'{amount_rub:.2f}', 'currency': 'RUB'},
                'vat_code': vat_code,
                'payment_subject': payment_subject,
                'payment_mode': payment_mode,
            }
        ],
    }
