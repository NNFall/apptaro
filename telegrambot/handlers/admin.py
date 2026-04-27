import os
import secrets

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types.input_file import FSInputFile

from config import load_config, PLANS
from database.models import (
    get_bot_stats_full,
    get_tag_stats,
    get_all_tag_stats_full,
    get_ad_tag,
    add_tokens,
    set_subscription_status,
    get_active_subscription,
    get_latest_subscription,
    create_ad_tag,
    add_admin,
    remove_admin,
    list_admins,
    has_admin,
    create_promo_code,
)
from services.admin_notify import notify_admins

router = Router()
config = load_config()


class AdminTemplateStates(StatesGroup):
    waiting_template_file = State()


def _plan_title(plan_key: str) -> str:
    if plan_key in PLANS:
        return PLANS[plan_key]['title']
    if plan_key == 'manual':
        return 'Ручной'
    return plan_key


def _percent(numerator: int, denominator: int) -> float:
    if not denominator:
        return 0.0
    return (numerator / denominator) * 100.0


def _ratio(numerator: int, denominator: int) -> float:
    if not denominator:
        return 0.0
    return numerator / denominator


async def _is_admin(user_id: int) -> bool:
    if user_id in config.admin_ids:
        return True
    return await has_admin(user_id)


@router.message(Command('botstats'))
async def botstats(message: Message) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer('Команда доступна только администратору.')
        return
    stats = await get_bot_stats_full()
    users = stats['users']
    free_users = stats['free_users']
    paid_users = stats['paid_users']
    active_subs = stats['active_subs']
    week_subs = stats['week_subs']
    month_subs = stats['month_subs']
    stars_payments = stats['stars_payments']
    stars_buyers = stats['stars_buyers']
    stars_sum = stats['stars_sum']
    revenue = stats['revenue_rub']

    conv = _percent(paid_users, users)
    arpu = _ratio(revenue, users)
    arppu = _ratio(revenue, paid_users)

    lines = [
        '📊 Общая статистика бота',
        '',
        f'👥 Всего пользователей: {users}',
        f'🎁 Использовали бесплатную генерацию: {free_users}',
        f'💳 Оплативших: {paid_users}',
        f'🔥 Активных подписок: {active_subs}',
        f"🟢 Подписка {PLANS['week']['price_rub']}₽ (неделя): {week_subs}",
        f"🔵 Подписка {PLANS['month']['price_rub']}₽ (месяц): {month_subs}",
        f'⭐ Оплаты Stars (XTR): {stars_payments}',
        f'⭐ Покупателей Stars: {stars_buyers}',
        f'⭐ Сумма Stars: {stars_sum} XTR',
        f'💰 Выручка: {revenue} ₽',
        '',
        f'📈 Конверсия в оплату: {conv:.2f}%',
        f'💵 ARPU: {arpu:.2f} ₽',
        f'💎 ARPPU: {arppu:.2f} ₽',
    ]
    await message.answer('\n'.join(lines))


@router.message(Command('adstats'))
async def adstats(message: Message) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer('Команда доступна только администратору.')
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer('Использование: /adstats метка')
        return
    tag = parts[1].strip()
    if tag.startswith('tag_'):
        tag = tag[4:]
    info = await get_ad_tag(tag)
    if not info:
        await message.answer('Метка не найдена.')
        return
    stats = await get_tag_stats(tag)
    users = stats['users']
    buyers = stats['payments']
    revenue = stats['revenue']
    conv = _percent(buyers, users)
    ltv = _ratio(revenue, users)
    lines = [
        '📊 Статистика по метке',
        f'• {tag} | users {users} | buyers {buyers} | conv {conv:.1f}% | sum {revenue} | LTV {ltv:.1f}',
    ]
    await message.answer('\n'.join(lines))


@router.message(Command('adstats_all'))
async def adstats_all(message: Message) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer('Команда доступна только администратору.')
        return
    stats = await get_all_tag_stats_full()
    if not stats:
        await message.answer('Статистики пока нет.')
        return
    lines = ['📊 Статистика по всем меткам']
    for item in stats:
        users = item['users']
        buyers = item['buyers']
        revenue = item['revenue']
        conv = _percent(buyers, users)
        ltv = _ratio(revenue, users)
        lines.append(
            f"• {item['tag']} | users {users} | buyers {buyers} | conv {conv:.1f}% | sum {revenue} | LTV {ltv:.1f}"
        )
    await message.answer('\n'.join(lines))


@router.message(Command('adtag'))
@router.message(Command('tag'))
async def adtag(message: Message) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer('Команда доступна только администратору.')
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer('Использование: /adtag метка')
        return
    tag = parts[1].strip()
    if tag.startswith('tag_'):
        tag = tag[4:]
    if not tag:
        await message.answer('Использование: /adtag метка')
        return
    await create_ad_tag(tag, 'manual', 'manual', '')
    bot = await message.bot.get_me()
    deeplink = f'https://t.me/{bot.username}?start={tag}'
    await message.answer(f'Метка: {tag}\nСсылка: {deeplink}')


@router.message(Command('sub_on'))
async def sub_on(message: Message) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer('Команда доступна только администратору.')
        return
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer('Использование: /sub_on <user_id> <tokens>')
        return
    user_id = int(parts[1])
    tokens = int(parts[2])
    await add_tokens(user_id, tokens)
    await message.answer(f'Начислено {tokens} генераций пользователю {user_id}.')


@router.message(Command('sub_off'))
async def sub_off(message: Message) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer('Команда доступна только администратору.')
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer('Использование: /sub_off <user_id>')
        return
    user_id = int(parts[1])
    ok = await set_subscription_status(user_id, 'expired')
    await message.answer('Подписка отключена.' if ok else 'Активная подписка не найдена.')


@router.message(Command('sub_cancel'))
async def sub_cancel(message: Message) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer('Команда доступна только администратору.')
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer('Использование: /sub_cancel <user_id>')
        return
    user_id = int(parts[1])
    ok = await set_subscription_status(user_id, 'canceled')
    await message.answer('Подписка отменена.' if ok else 'Активная подписка не найдена.')


@router.message(Command('sub_check'))
async def sub_check(message: Message) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer('Команда доступна только администратору.')
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer('Использование: /sub_check <user_id>')
        return
    user_id = int(parts[1])
    sub = await get_active_subscription(user_id)
    if not sub:
        sub = await get_latest_subscription(user_id)
        if not sub:
            await message.answer('Подписок не найдено.')
            return
        await message.answer(
            f"Последняя подписка: {_plan_title(sub['plan'])}\n"
            f"Статус: {sub['status']}\n"
            f"Остаток: {sub['remaining']}\n"
            f"Действует до: {sub['ends_at']}"
        )
        return
    await message.answer(
        f"Активная подписка: {_plan_title(sub['plan'])}\n"
        f"Остаток: {sub['remaining']}\n"
        f"Действует до: {sub['ends_at']}"
    )


@router.message(Command('genpromo'))
async def genpromo(message: Message) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer('Команда доступна только администратору.')
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer('Использование: /genpromo <tokens> [uses]')
        return
    tokens = int(parts[1])
    max_uses = int(parts[2]) if len(parts) > 2 else 1
    code = secrets.token_hex(4)
    await create_promo_code(code, tokens, max_uses)
    bot = await message.bot.get_me()
    promo_link = f'https://t.me/{bot.username}?start=promo_{code}'
    await message.answer(
        f'Промокод: {code}\nГенерации: {tokens}\nИспользований: {max_uses}\nСсылка: {promo_link}'
    )
    await notify_admins(
        message.bot,
        f'🎁 Создан промокод на {tokens} генераций: {code}\nСсылка: {promo_link}',
    )


@router.message(Command('admin_add'))
async def admin_add_cmd(message: Message) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer('Команда доступна только администратору.')
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer('Использование: /admin_add <user_id>')
        return
    user_id = int(parts[1])
    await add_admin(user_id)
    await message.answer(f'Админ добавлен: {user_id}')


@router.message(Command('admin_del'))
async def admin_del_cmd(message: Message) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer('Команда доступна только администратору.')
        return
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer('Использование: /admin_del <user_id>')
        return
    user_id = int(parts[1])
    await remove_admin(user_id)
    await message.answer(f'Админ удален: {user_id}')


@router.message(Command('admin_list'))
async def admin_list_cmd(message: Message) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer('Команда доступна только администратору.')
        return
    extra_admins = await list_admins()
    all_admins = sorted(set(config.admin_ids + extra_admins))
    await message.answer('Админы: ' + ', '.join(str(x) for x in all_admins))


@router.message(Command('templates'))
async def templates_list(message: Message) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer('Команда доступна только администратору.')
        return
    sent_any = False
    for idx in range(1, 5):
        path = os.path.join(config.templates_dir, f'design_{idx}.pptx')
        if os.path.exists(path):
            await message.answer_document(FSInputFile(path), caption=f'Шаблон {idx}')
            sent_any = True
        else:
            await message.answer(f'Шаблон {idx} не найден.')

    mailer_idx = config.mailer_template_index
    mailer_path = os.path.join(config.templates_dir, f'design_{mailer_idx}.txt')
    if os.path.exists(mailer_path):
        await message.answer_document(
            FSInputFile(mailer_path),
            caption=f'Шаблон {mailer_idx} (рассылка)',
        )
        sent_any = True
    else:
        await message.answer(f'Шаблон {mailer_idx} (рассылка) не найден.')

    if not sent_any:
        await message.answer('Шаблоны не найдены. Положите файлы в media/templates.')


@router.message(Command('template_set'))
async def template_set(message: Message, state: FSMContext) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer('Команда доступна только администратору.')
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer('Использование: /template_set 1|2|3|4|5')
        return
    try:
        idx = int(parts[1].strip())
    except ValueError:
        await message.answer('Укажите номер шаблона: 1, 2, 3, 4 или 5.')
        return
    if idx not in (1, 2, 3, 4, config.mailer_template_index):
        await message.answer('Укажите номер шаблона: 1, 2, 3, 4 или 5.')
        return
    await state.update_data(template_idx=idx)
    await state.set_state(AdminTemplateStates.waiting_template_file)
    if idx == config.mailer_template_index:
        await message.answer(f'Пришлите TXT файл для замены шаблона {idx} (рассылка).')
    else:
        await message.answer(f'Пришлите PPTX файл для замены шаблона {idx}.')


@router.message(AdminTemplateStates.waiting_template_file, F.document)
async def template_set_file(message: Message, state: FSMContext) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer('Команда доступна только администратору.')
        await state.clear()
        return
    data = await state.get_data()
    idx = data.get('template_idx')
    if idx not in (1, 2, 3, 4, config.mailer_template_index):
        await message.answer('Не удалось определить номер шаблона. Повторите /template_set.')
        await state.clear()
        return
    filename = message.document.file_name or ''
    if idx == config.mailer_template_index:
        if not filename.lower().endswith('.txt'):
            await message.answer('Нужен файл в формате TXT.')
            return
    else:
        if not filename.lower().endswith('.pptx'):
            await message.answer('Нужен файл в формате PPTX.')
            return
    os.makedirs(config.templates_dir, exist_ok=True)
    os.makedirs(config.temp_dir, exist_ok=True)
    ext = 'txt' if idx == config.mailer_template_index else 'pptx'
    tmp_path = os.path.join(config.temp_dir, f'template_{idx}_{secrets.token_hex(4)}.{ext}')
    await message.bot.download(message.document, destination=tmp_path)
    target_path = os.path.join(config.templates_dir, f'design_{idx}.{ext}')
    try:
        os.replace(tmp_path, target_path)
    except OSError:
        import shutil
        shutil.copy2(tmp_path, target_path)
        try:
            os.remove(tmp_path)
        except OSError:
            pass
    await state.clear()
    if idx == config.mailer_template_index:
        await message.answer(f'Шаблон {idx} (рассылка) обновлен ✅')
    else:
        await message.answer(f'Шаблон {idx} обновлен ✅')


@router.message(AdminTemplateStates.waiting_template_file)
async def template_set_file_invalid(message: Message) -> None:
    await message.answer('Пришлите файл шаблона.')




