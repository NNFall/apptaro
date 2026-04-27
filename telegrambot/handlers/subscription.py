import asyncio
import time

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, PreCheckoutQuery, LabeledPrice
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey

from config import load_config, PLANS
from datetime import datetime, timezone

from database.models import (
    get_active_subscription,
    get_latest_valid_subscription,
    create_subscription,
    add_payment,
    add_payment_with_method,
    update_payment_status,
    cancel_subscription,
    renew_subscription,
)
from keyboards.inline import (
    payment_kb,
    payment_options_kb,
    pay_url_kb,
    main_menu_button_kb,
    subscription_actions_kb,
)
from services.logger import get_logger
from services.admin_notify import notify_admins
from services.payment import (
    build_payload,
    parse_payload,
    init_yookassa,
    create_yookassa_payment,
    create_yookassa_recurring_payment,
    get_yookassa_payment,
)
from services.runtime import get_storage

router = Router()
config = load_config()
logger = get_logger()


@router.callback_query(F.data == 'menu:plan')
async def my_plan_cb(callback: CallbackQuery) -> None:
    logger.info('Menu click: plan user=%s', callback.from_user.id)
    await _send_plan(callback.message, callback.from_user.id)
    await callback.answer()


@router.message(F.text == 'Мой тариф')
async def my_plan(message: Message) -> None:
    logger.info('Command: plan user=%s', message.from_user.id)
    await _send_plan(message)


@router.message(F.text == 'Баланс / Подписка')
async def my_plan_alias(message: Message) -> None:
    logger.info('Command: plan alias user=%s', message.from_user.id)
    await _send_plan(message)


@router.message(Command('balance'))
async def my_plan_balance(message: Message) -> None:
    logger.info('Command: balance user=%s', message.from_user.id)
    await _send_plan(message)


async def _send_plan(message: Message, user_id: int | None = None) -> None:
    target_user_id = user_id or message.from_user.id
    sub = await get_active_subscription(target_user_id)
    if not sub:
        latest = await get_latest_valid_subscription(target_user_id)
        tokens = latest.get('remaining', 0) if latest else 0
        lines = []
        if latest and latest.get('status') == 'canceled':
            ends_at = _format_date(latest.get('ends_at', ''))
            lines += [
                '<b>❌ Подписка отключена</b>',
                f'<b>🎬 Генерации: {tokens}</b>',
                f'Генерации доступны до {ends_at}.',
            ]
        else:
            lines += [
                '<b>❌ Подписка не активна</b>',
                f'<b>🎬 Генерации: {tokens}</b>',
            ]
        lines += [
            '',
            '<b>Подписка с автосписанием</b>',
            f"🔥 {PLANS['week']['price_rub']} ₽ / неделя — {PLANS['week']['limit']} генераций",
            f"⭐ {PLANS['month']['price_rub']} ₽ / месяц — {PLANS['month']['limit']} генераций",
            '',
            f"⭐ {config.stars_one10_amount} ⭐ — {PLANS['week']['limit']} генераций (разово)",
            f"⭐ {config.stars_one40_amount} ⭐ — {PLANS['month']['limit']} генераций (разово)",
            '',
            'Отключить можно в любой момент в /balance.',
            '',
            f'Переходя к оплате, вы соглашаетесь с <a href="{config.offer_url}">офертой</a>.',
            config.offer_url,
        ]
        await message.answer('\n'.join(lines), reply_markup=payment_kb(), parse_mode='HTML')
        return

    plan_title = PLANS.get(sub['plan'], {}).get('title', sub['plan'])
    provider = sub.get('provider') or 'manual'
    tokens = sub['remaining']
    ends_at = _format_date(sub.get('ends_at', ''))
    plan = PLANS.get(sub['plan'], {})
    price = plan.get('price_rub')
    limit = plan.get('limit')
    tariff_line = f'{price} ₽ / {plan_title} — {limit} генераций' if price and limit else plan_title
    lines = [
        '✅ Подписка активна',
        f'<b>Тариф: {tariff_line}</b>',
        f'Остаток генераций: {tokens}',
        f'Обновление генераций: {ends_at or sub.get("ends_at", "")}',
    ]
    show_renew_now = provider == 'yookassa'
    await message.answer(
        '\n'.join(lines),
        reply_markup=subscription_actions_kb(
            show_renew_now=show_renew_now,
            show_cancel=True,
        ),
        parse_mode='HTML',
    )


@router.callback_query(F.data == 'plan:choose')
async def choose_plan(callback: CallbackQuery) -> None:
    logger.info('Plan choose: user=%s', callback.from_user.id)
    await callback.answer()
    options = _build_payment_options()
    await callback.message.answer('Выбери подписку 👇', reply_markup=payment_options_kb(options, back_data='plan:back'))


@router.callback_query(F.data == 'plan:back')
async def plan_back(callback: CallbackQuery) -> None:
    logger.info('Plan back: user=%s', callback.from_user.id)
    await callback.answer()
    await _send_plan(callback.message, callback.from_user.id)


@router.callback_query(F.data == 'renew:back')
async def renew_back(callback: CallbackQuery) -> None:
    await callback.answer()
    await _send_plan(callback.message, callback.from_user.id)


def _build_payment_options() -> list[tuple[str, str]]:
    options: list[tuple[str, str]] = [
        (f"🔥 {PLANS['week']['price_rub']} ₽ / неделя — {PLANS['week']['limit']} генераций", 'pay:week:yoo'),
        (f"⭐ {PLANS['month']['price_rub']} ₽ / месяц — {PLANS['month']['limit']} генераций", 'pay:month:yoo'),
        (f"⭐ Купить {PLANS['week']['limit']} генераций ({config.stars_one10_amount} ⭐)", 'pay:one10:stars'),
        (f"⭐ Купить {PLANS['month']['limit']} генераций ({config.stars_one40_amount} ⭐)", 'pay:one40:stars'),
    ]
    return options


def _stars_amount_for_plan(plan_key: str) -> int:
    if plan_key == 'week':
        return config.stars_week_amount
    if plan_key == 'month':
        return config.stars_month_amount
    if plan_key == 'one10':
        return config.stars_one10_amount
    if plan_key == 'one40':
        return config.stars_one40_amount
    return config.stars_week_amount


@router.callback_query(F.data.startswith('pay:'))
async def pay(callback: CallbackQuery) -> None:
    await callback.answer()
    parts = callback.data.split(':')
    plan_key = parts[1] if len(parts) > 1 else ''
    provider = parts[2] if len(parts) > 2 else 'auto'
    context = parts[3] if len(parts) > 3 else ''
    if provider == 'auto':
        provider = 'stars' if config.stars_provider_token else 'yoo'
    if provider not in {'stars', 'yoo'}:
        provider = 'yoo'
    plan = PLANS[plan_key]
    payload = build_payload(plan_key, callback.from_user.id)
    logger.info('Pay start: provider=%s plan=%s user=%s', provider, plan_key, callback.from_user.id)

    if provider == 'stars':
        amount = _stars_amount_for_plan(plan_key)
        prices = [LabeledPrice(label=plan['title'], amount=amount)]
        await callback.message.bot.send_invoice(
            chat_id=callback.from_user.id,
            title=f"Подписка: {plan['title']}",
            description=f"{plan['limit']} генераций на {plan['days']} дней",
            payload=payload,
            provider_token=config.stars_provider_token,
            currency='XTR',
            prices=prices,
        )
        return

    if provider == 'yoo' and config.yookassa_shop_id and config.yookassa_secret:
        init_yookassa(config.yookassa_shop_id, config.yookassa_secret)
        if context == 'renew':
            sub = await get_active_subscription(callback.from_user.id)
            if sub and sub.get('provider') == 'yookassa' and sub.get('payment_method_id'):
                payment_method_id = sub.get('payment_method_id')
                try:
                    payment = await asyncio.to_thread(
                        create_yookassa_recurring_payment,
                        plan_key,
                        callback.from_user.id,
                        plan['price_rub'],
                        payment_method_id,
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.exception('YooKassa auto-charge failed: user=%s', callback.from_user.id)
                    await callback.message.answer(f'Не удалось списать автоматически 😢\n{exc}')
                    await notify_admins(
                        callback.message.bot,
                        f'❌ Продление не удалось (ошибка списания): {exc}',
                    )
                    return
                status = getattr(payment, 'status', '')
                if status == 'succeeded':
                    await renew_subscription(sub['id'], plan_key, plan['limit'], plan['days'])
                    await add_payment_with_method(
                        callback.from_user.id,
                        'yookassa',
                        plan['price_rub'],
                        'RUB',
                        getattr(payment, 'id', ''),
                        'paid',
                        payment_method_id,
                    )
                    await callback.message.answer('Подписка продлена ✅', reply_markup=main_menu_button_kb())
                    plan_title = PLANS.get(plan_key, {}).get('title', plan_key)
                    await notify_admins(
                        callback.message.bot,
                        f'✅ Продление подписки (ЮKassa). Пользователь {callback.from_user.id} (@{callback.from_user.username or "-"}) , тариф {plan_title}',
                    )
                    return
                await callback.message.answer('Автосписание не прошло 😢 Попробуйте позже.')
                await notify_admins(
                    callback.message.bot,
                    f'❌ Продление не удалось (ошибка списания): статус {status}',
                )
                return
        await callback.message.answer('Создаю счёт на оплату... 💳')
        try:
            return_url = config.yookassa_return_url or (
                f'https://t.me/{config.bot_username}' if config.bot_username else 'https://t.me'
            )
            payment_id, confirmation_url = await asyncio.to_thread(
                create_yookassa_payment,
                plan_key,
                callback.from_user.id,
                plan['price_rub'],
                return_url,
                True,
            )
            await add_payment(callback.from_user.id, 'yookassa', plan['price_rub'], 'RUB', payment_id, 'pending')
            await callback.message.answer(
                'Оплата через ЮKassa. Нажмите кнопку ниже и завершите оплату.',
                reply_markup=pay_url_kb(confirmation_url),
            )
            asyncio.create_task(_poll_yookassa_payment(callback.message.bot, payment_id, plan_key, callback.from_user.id))
        except Exception:  # noqa: BLE001
            logger.exception('YooKassa create failed: user=%s plan=%s', callback.from_user.id, plan_key)
            await callback.message.answer(
                'Не удалось создать счёт в ЮKassa 😢\nПроверьте интернет/SSL и попробуйте снова.',
                reply_markup=main_menu_button_kb(),
            )
        return

    await callback.message.answer(
        'Оплата не настроена ⚠️\nЗаполните STARS_PROVIDER_TOKEN или YOOKASSA_* в .env.',
        reply_markup=main_menu_button_kb(),
    )
    await notify_admins(
        callback.message.bot,
        '❌ YooKassa config error: отсутствуют YOOKASSA_* или STARS_PROVIDER_TOKEN',
    )


async def _poll_yookassa_payment(bot, payment_id: str, plan_key: str, user_id: int) -> None:
    plan = PLANS[plan_key]
    deadline = time.time() + config.yookassa_poll_timeout
    while time.time() < deadline:
        try:
            payment = await asyncio.to_thread(get_yookassa_payment, payment_id)
        except Exception:  # noqa: BLE001
            logger.exception('YooKassa poll failed: id=%s user=%s', payment_id, user_id)
            await asyncio.sleep(config.yookassa_poll_interval)
            continue
        if not payment:
            await asyncio.sleep(config.yookassa_poll_interval)
            continue
        status = getattr(payment, 'status', '')
        if status == 'succeeded':
            payment_method_id = _extract_payment_method_id(payment)
            auto_renew = 1 if payment_method_id else 0
            await create_subscription(
                user_id,
                plan_key,
                plan['limit'],
                plan['days'],
                provider='yookassa',
                auto_renew=auto_renew,
                payment_method_id=payment_method_id,
            )
            await update_payment_status('yookassa', payment_id, 'paid', payment_method_id)
            await bot.send_message(
                user_id,
                'Оплата прошла ✅ Подписка активирована!',
                reply_markup=main_menu_button_kb(),
            )
            try:
                chat = await bot.get_chat(user_id)
                username = chat.username or '-'
            except Exception:  # noqa: BLE001
                username = '-'
            plan_title = PLANS.get(plan_key, {}).get('title', plan_key)
            await notify_admins(
                bot,
                f'💰 Успешная покупка (ЮKassa). Пользователь {user_id} (@{username}) , тариф {plan_title}',
            )
            logger.info('YooKassa success: id=%s user=%s', payment_id, user_id)
            await _resume_generation_if_pending(bot, user_id)
            return
        if status == 'canceled':
            await update_payment_status('yookassa', payment_id, 'canceled')
            await bot.send_message(
                user_id,
                'Оплата отменена ❌ Если нужно, попробуйте ещё раз.',
                reply_markup=main_menu_button_kb(),
            )
            logger.info('YooKassa canceled: id=%s user=%s', payment_id, user_id)
            return
        logger.info('YooKassa pending: id=%s status=%s user=%s', payment_id, status, user_id)
        await asyncio.sleep(config.yookassa_poll_interval)
    await bot.send_message(
        user_id,
        'Не удалось подтвердить оплату 🕒\nПопробуйте позже.',
        reply_markup=main_menu_button_kb(),
    )


async def _resume_generation_if_pending(bot, user_id: int) -> None:
    storage = get_storage()
    if not storage:
        return
    key = StorageKey(bot_id=bot.id, chat_id=user_id, user_id=user_id)
    state = FSMContext(storage=storage, key=key)
    data = await state.get_data()
    if data.get('topic') and data.get('design'):
        from handlers.presentation_gen import _run_generation

        await bot.send_message(user_id, 'Оплата получена ✅\nЗапускаю генерацию... 🚀')
        await _run_generation(bot, user_id, user_id, state)


@router.pre_checkout_query()
async def pre_checkout(pre_checkout_query: PreCheckoutQuery) -> None:
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def successful_payment(message: Message, state: FSMContext) -> None:
    payload = message.successful_payment.invoice_payload
    plan_key, user_id = parse_payload(payload)
    if plan_key not in PLANS:
        await message.answer('Не удалось определить тариф 🤷‍♂️', reply_markup=main_menu_button_kb())
        return
    plan = PLANS[plan_key]
    await create_subscription(user_id, plan_key, plan['limit'], plan['days'], provider='stars', auto_renew=0)
    amount = message.successful_payment.total_amount
    currency = message.successful_payment.currency
    await add_payment(user_id, 'stars', amount, currency, payload, 'paid')
    await message.answer('Оплата получена ✅ Подписка активирована!', reply_markup=main_menu_button_kb())
    await notify_admins(
        message.bot,
        f'💰 Успешная покупка (Stars). Пользователь {user_id} (@{message.from_user.username or "-"})',
    )

    await _resume_generation_if_pending(message.bot, user_id)


@router.callback_query(F.data == 'sub:cancel')
async def sub_cancel(callback: CallbackQuery) -> None:
    await callback.answer()
    sub = await get_active_subscription(callback.from_user.id)
    if not sub:
        await callback.message.answer('Подписка не активна. Выберите тариф 👇', reply_markup=payment_kb())
        return
    await cancel_subscription(callback.from_user.id)
    ends_at = _format_date(sub.get('ends_at', ''))
    await callback.message.answer(
        f'Подписка выключена. Генерации доступны до {ends_at}.',
        reply_markup=main_menu_button_kb(),
    )
    await notify_admins(
        callback.message.bot,
        f'❌ Отключил подписку. Пользователь {callback.from_user.id} (@{callback.from_user.username or "-"})',
    )


@router.callback_query(F.data == 'renew:now')
async def renew_now(callback: CallbackQuery) -> None:
    await callback.answer()
    options = [
        (f"🔥 {PLANS['week']['price_rub']} ₽ / неделя — {PLANS['week']['limit']} генераций", 'pay:week:yoo:renew'),
        (f"⭐ {PLANS['month']['price_rub']} ₽ / месяц — {PLANS['month']['limit']} генераций", 'pay:month:yoo:renew'),
        (f"⭐ Купить {PLANS['week']['limit']} генераций ({config.stars_one10_amount} ⭐)", 'pay:one10:stars'),
        (f"⭐ Купить {PLANS['month']['limit']} генераций ({config.stars_one40_amount} ⭐)", 'pay:one40:stars'),
    ]
    await callback.message.answer(
        '🔄 Обновить подписку\nВыберите тариф для продления:',
        reply_markup=payment_options_kb(options, back_data='renew:back'),
    )


def _extract_payment_method_id(payment) -> str | None:
    try:
        method = getattr(payment, 'payment_method', None)
        if method and getattr(method, 'id', None):
            return method.id
    except Exception:  # noqa: BLE001
        return None
    return None


def _format_date(value: str) -> str:
    try:
        dt = datetime.fromisoformat(value)
    except Exception:  # noqa: BLE001
        return value
    return dt.date().isoformat()
