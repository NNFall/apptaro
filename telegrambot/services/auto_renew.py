from __future__ import annotations

import asyncio
from datetime import datetime

from config import PLANS
from database.models import (
    add_payment_with_method,
    expire_subscription,
    get_autorenew_due_subscriptions,
    postpone_autorenew_attempt,
    renew_subscription,
)
from services.admin_notify import notify_admins
from services.logger import get_logger
from services.payment import create_yookassa_recurring_payment, init_yookassa


logger = get_logger()


def _dt_short(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime('%Y-%m-%d %H:%M')
    except Exception:  # noqa: BLE001
        return value


def _is_missing_payment_method_error(error_text: str) -> bool:
    text = (error_text or '').lower()
    return "payment_method_id doesn't exist" in text or 'payment_method_id' in text and 'doesn' in text


async def _username(bot, user_id: int) -> str:
    try:
        chat = await bot.get_chat(user_id)
        return chat.username or '-'
    except Exception:  # noqa: BLE001
        return '-'


async def auto_renew_loop(bot, config) -> None:
    if not config.yookassa_shop_id or not config.yookassa_secret:
        logger.info('Auto-renew disabled: YOOKASSA credentials not set')
        await notify_admins(bot, '❌ YooKassa config error: отсутствуют YOOKASSA_*')
        return

    init_yookassa(config.yookassa_shop_id, config.yookassa_secret)
    logger.info('Auto-renew worker started')

    while True:
        try:
            subs = await get_autorenew_due_subscriptions()
            for sub in subs:
                await _process_subscription(bot, sub)
        except Exception:  # noqa: BLE001
            logger.exception('Auto-renew loop failed')
        await asyncio.sleep(config.auto_renew_interval)


async def _process_subscription(bot, sub: dict) -> None:
    user_id = sub['user_id']
    sub_id = sub['id']
    plan_id = sub['plan']
    period_end = sub.get('ends_at', '')
    plan = PLANS.get(plan_id)
    if not plan:
        logger.error(
            'Auto-renew skip unknown plan: user_id=%s sub_id=%s plan_id=%s current_period_end=%s',
            user_id,
            sub_id,
            plan_id,
            period_end,
        )
        next_try = await postpone_autorenew_attempt(sub_id, days=1)
        await _notify_error(
            bot=bot,
            user_id=user_id,
            plan_id=plan_id,
            plan_title='unknown',
            tokens=sub.get('remaining', 0),
            amount=0,
            status='error',
            payment_id='-',
            reason=f'Неизвестный тариф: {plan_id}',
            next_try=next_try,
        )
        return

    amount = int(plan['price_rub'])
    tokens = int(plan['limit'])
    plan_title = str(plan.get('title', plan_id))
    payment_method_id = sub.get('payment_method_id') or ''

    logger.info(
        'Auto-renew start: user_id=%s sub_id=%s plan_id=%s current_period_end=%s',
        user_id,
        sub_id,
        plan_id,
        period_end,
    )

    if not payment_method_id:
        logger.error(
            'Auto-renew critical: missing payment_method_id user_id=%s sub_id=%s',
            user_id,
            sub_id,
        )
        await expire_subscription(sub_id)
        await _notify_critical_missing_pm(
            bot=bot,
            user_id=user_id,
            plan_id=plan_id,
            plan_title=plan_title,
            tokens=tokens,
            amount=amount,
            reason='payment_method_id отсутствует',
        )
        return

    try:
        payment = await asyncio.to_thread(
            create_yookassa_recurring_payment,
            plan_id,
            user_id,
            amount,
            payment_method_id,
        )
    except Exception as exc:  # noqa: BLE001
        error_text = str(exc)
        logger.error(
            'Auto-renew response: user_id=%s sub_id=%s status=error payment_id=- error=%s',
            user_id,
            sub_id,
            error_text,
        )
        if _is_missing_payment_method_error(error_text):
            logger.error(
                'Auto-renew critical: payment_method_id invalid user_id=%s sub_id=%s',
                user_id,
                sub_id,
            )
            await expire_subscription(sub_id)
            await _notify_critical_missing_pm(
                bot=bot,
                user_id=user_id,
                plan_id=plan_id,
                plan_title=plan_title,
                tokens=tokens,
                amount=amount,
                reason=error_text,
            )
            return

        next_try = await postpone_autorenew_attempt(sub_id, days=1)
        logger.info(
            'Auto-renew postponed: user_id=%s sub_id=%s next_try=%s',
            user_id,
            sub_id,
            next_try,
        )
        await _notify_error(
            bot=bot,
            user_id=user_id,
            plan_id=plan_id,
            plan_title=plan_title,
            tokens=tokens,
            amount=amount,
            status='error',
            payment_id='-',
            reason=error_text,
            next_try=next_try,
        )
        return

    status = getattr(payment, 'status', '') or 'unknown'
    payment_id = getattr(payment, 'id', '') or '-'
    logger.info(
        'Auto-renew response: user_id=%s sub_id=%s status=%s payment_id=%s error=-',
        user_id,
        sub_id,
        status,
        payment_id,
    )

    if status == 'succeeded':
        await renew_subscription(sub_id, plan_id, tokens, int(plan['days']))
        await add_payment_with_method(
            user_id=user_id,
            provider='yookassa',
            amount=amount,
            currency='RUB',
            payload=payment_id,
            status='paid',
            payment_method_id=payment_method_id,
        )
        logger.info(
            'Auto-renew period updated: user_id=%s sub_id=%s plan_id=%s',
            user_id,
            sub_id,
            plan_id,
        )
        await _notify_success(
            bot=bot,
            user_id=user_id,
            plan_id=plan_id,
            plan_title=plan_title,
            tokens=tokens,
            amount=amount,
            payment_id=payment_id,
        )
        return

    next_try = await postpone_autorenew_attempt(sub_id, days=1)
    logger.info(
        'Auto-renew postponed: user_id=%s sub_id=%s next_try=%s',
        user_id,
        sub_id,
        next_try,
    )
    await _notify_error(
        bot=bot,
        user_id=user_id,
        plan_id=plan_id,
        plan_title=plan_title,
        tokens=tokens,
        amount=amount,
        status=status,
        payment_id=payment_id,
        reason=f'Платеж не прошел, status={status}',
        next_try=next_try,
    )


async def _notify_success(
    bot,
    user_id: int,
    plan_id: str,
    plan_title: str,
    tokens: int,
    amount: int,
    payment_id: str,
) -> None:
    username = await _username(bot, user_id)
    text = (
        '🔄 Автосписание - УСПЕХ\n'
        f'User ID: {user_id} (@{username})\n'
        f'Тариф: {plan_id} ({plan_title} - {tokens} токенов)\n'
        f'Сумма: {amount} RUB\n'
        'Status: succeeded\n'
        f'Payment ID: {payment_id}'
    )
    await notify_admins(bot, text)


async def _notify_error(
    bot,
    user_id: int,
    plan_id: str,
    plan_title: str,
    tokens: int,
    amount: int,
    status: str,
    payment_id: str,
    reason: str,
    next_try: str,
) -> None:
    username = await _username(bot, user_id)
    text = (
        '🔄 Автосписание - ОШИБКА\n'
        f'User ID: {user_id} (@{username})\n'
        f'Тариф: {plan_id} ({plan_title} - {tokens} токенов)\n'
        f'Сумма: {amount} RUB\n'
        f'Status: {status}\n'
        f'Payment ID: {payment_id or "-"}\n'
        f'Причина: {reason}\n'
        f'Следующая попытка: {_dt_short(next_try)}'
    )
    await notify_admins(bot, text)


async def _notify_critical_missing_pm(
    bot,
    user_id: int,
    plan_id: str,
    plan_title: str,
    tokens: int,
    amount: int,
    reason: str,
) -> None:
    username = await _username(bot, user_id)
    text = (
        '🔄 Автосписание - ОШИБКА\n'
        f'User ID: {user_id} (@{username})\n'
        f'Тариф: {plan_id} ({plan_title} - {tokens} токенов)\n'
        f'Сумма: {amount} RUB\n'
        'Status: error\n'
        'Payment ID: -\n'
        f'Причина: {reason}\n'
        'Следующая попытка: не будет (подписка переведена в expired)'
    )
    await notify_admins(bot, text)
