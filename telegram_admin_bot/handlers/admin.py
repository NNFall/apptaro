from __future__ import annotations

import os
import secrets
import shutil

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from aiogram.types.input_file import FSInputFile

from telegram_admin_bot.config import load_config

from src.repositories import admin as admin_repo


router = Router()
config = load_config()


class AdminTemplateStates(StatesGroup):
    waiting_template_file = State()


PLANS = {
    'week': {'title': 'Неделя', 'price_rub': 199},
    'month': {'title': 'Месяц', 'price_rub': 499},
    'one10': {'title': 'Разово 10', 'price_rub': 199},
    'one40': {'title': 'Разово 40', 'price_rub': 499},
    'manual': {'title': 'Ручной', 'price_rub': 0},
}


def _plan_title(plan_key: str) -> str:
    return PLANS.get(plan_key, {'title': plan_key}).get('title', plan_key)


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
    return admin_repo.has_admin(user_id)


def _normalize_tag(raw: str) -> str:
    tag = raw.strip()
    if tag.startswith('tag_'):
        tag = tag[4:]
    return tag.strip()


def _build_tag_link(tag: str) -> str | None:
    base = config.app_share_url.strip().rstrip('/')
    if not base:
        return None
    separator = '&' if '?' in base else '?'
    return f'{base}{separator}tag={tag}'


@router.message(Command('botstats'))
async def botstats(message: Message) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer('Команда доступна только администратору.')
        return
    stats = admin_repo.get_bot_stats_full()
    users = int(stats['users'])
    free_users = int(stats['free_users'])
    paid_users = int(stats['paid_users'])
    active_subs = int(stats['active_subs'])
    week_subs = int(stats['week_subs'])
    month_subs = int(stats['month_subs'])
    stars_payments = int(stats['stars_payments'])
    stars_buyers = int(stats['stars_buyers'])
    stars_sum = int(stats['stars_sum'])
    revenue = int(stats['revenue_rub'])
    generations = int(stats['generations'])
    success = int(stats['success'])

    conv = _percent(paid_users, users)
    arpu = _ratio(revenue, users)
    arppu = _ratio(revenue, paid_users)
    success_rate = _percent(success, generations)

    lines = [
        '📊 Общая статистика AppSlides',
        '',
        f'👥 Всего клиентов: {users}',
        f'🎁 Генерировали без оплаты: {free_users}',
        f'💳 Оплативших: {paid_users}',
        f'🧾 Всего задач генерации: {generations}',
        f'✅ Успешных задач: {success} ({success_rate:.2f}%)',
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
    parts = (message.text or '').split(maxsplit=1)
    if len(parts) < 2:
        await message.answer('Использование: /adstats <метка>')
        return
    tag = _normalize_tag(parts[1])
    if not admin_repo.get_ad_tag(tag):
        await message.answer('Метка не найдена.')
        return
    stats = admin_repo.get_tag_stats(tag)
    users = int(stats['users'])
    buyers = int(stats['payments'])
    revenue = int(stats['revenue'])
    conv = _percent(buyers, users)
    ltv = _ratio(revenue, users)
    await message.answer(
        '\n'.join(
            [
                '📊 Статистика по метке',
                f'• {tag} | users {users} | buyers {buyers} | conv {conv:.1f}% | sum {revenue} | LTV {ltv:.1f}',
            ]
        )
    )


@router.message(Command('adstats_all'))
async def adstats_all(message: Message) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer('Команда доступна только администратору.')
        return
    stats = admin_repo.get_all_tag_stats_full()
    if not stats:
        await message.answer('Статистики пока нет.')
        return
    lines = ['📊 Статистика по всем меткам']
    for item in stats:
        users = int(item['users'])
        buyers = int(item['buyers'])
        revenue = int(item['revenue'])
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
    parts = (message.text or '').split(maxsplit=1)
    if len(parts) < 2:
        await message.answer('Использование: /adtag <метка>')
        return
    tag = _normalize_tag(parts[1])
    if not tag:
        await message.answer('Использование: /adtag <метка>')
        return
    admin_repo.create_ad_tag(tag, 'manual', 'manual', '')
    link = _build_tag_link(tag)
    if link:
        await message.answer(f'Метка: {tag}\nСсылка: {link}')
        return
    await message.answer(
        f'Метка: {tag}\nСсылка не настроена. При необходимости задайте APP_SHARE_URL в .env admin-бота.'
    )


@router.message(Command('sub_on'))
async def sub_on(message: Message) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer('Команда доступна только администратору.')
        return
    parts = (message.text or '').split()
    if len(parts) < 3:
        await message.answer('Использование: /sub_on <client_id> <tokens>')
        return
    client_id = parts[1].strip()
    tokens = int(parts[2])
    admin_repo.add_tokens(client_id, tokens)
    await message.answer(f'Начислено {tokens} генераций клиенту {client_id}.')


@router.message(Command('sub_off'))
async def sub_off(message: Message) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer('Команда доступна только администратору.')
        return
    parts = (message.text or '').split()
    if len(parts) < 2:
        await message.answer('Использование: /sub_off <client_id>')
        return
    client_id = parts[1].strip()
    ok = admin_repo.set_subscription_status(client_id, 'expired')
    await message.answer('Подписка отключена.' if ok else 'Активная подписка не найдена.')


@router.message(Command('sub_cancel'))
async def sub_cancel(message: Message) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer('Команда доступна только администратору.')
        return
    parts = (message.text or '').split()
    if len(parts) < 2:
        await message.answer('Использование: /sub_cancel <client_id>')
        return
    client_id = parts[1].strip()
    ok = admin_repo.cancel_subscription(client_id)
    await message.answer('Подписка отменена.' if ok else 'Активная подписка не найдена.')


@router.message(Command('sub_check'))
async def sub_check(message: Message) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer('Команда доступна только администратору.')
        return
    parts = (message.text or '').split()
    if len(parts) < 2:
        await message.answer('Использование: /sub_check <client_id>')
        return
    client_id = parts[1].strip()
    sub = admin_repo.get_active_subscription(client_id)
    if not sub:
        sub = admin_repo.get_latest_subscription(client_id)
        if not sub:
            await message.answer('Подписок не найдено.')
            return
        await message.answer(
            f"Последняя подписка: {_plan_title(sub.plan_key)}\n"
            f'Статус: {sub.status}\n'
            f'Остаток: {sub.remaining}\n'
            f'Действует до: {sub.ends_at}\n'
            f'Клиент: {sub.client_id}'
        )
        return
    await message.answer(
        f"Активная подписка: {_plan_title(sub.plan_key)}\n"
        f'Остаток: {sub.remaining}\n'
        f'Действует до: {sub.ends_at}\n'
        f'Клиент: {sub.client_id}'
    )


@router.message(Command('genpromo'))
async def genpromo(message: Message) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer('Команда доступна только администратору.')
        return
    parts = (message.text or '').split()
    if len(parts) < 2:
        await message.answer('Использование: /genpromo <tokens> [uses]')
        return
    tokens = int(parts[1])
    max_uses = int(parts[2]) if len(parts) > 2 else 1
    code = secrets.token_hex(4)
    admin_repo.create_promo_code(code, tokens, max_uses)
    await message.answer(
        f'Промокод: {code}\nГенерации: {tokens}\nИспользований: {max_uses}\n'
        'Флоу активации в мобильном клиенте будет привязан отдельно.'
    )


@router.message(Command('admin_add'))
async def admin_add_cmd(message: Message) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer('Команда доступна только администратору.')
        return
    parts = (message.text or '').split()
    if len(parts) < 2:
        await message.answer('Использование: /admin_add <telegram_user_id>')
        return
    user_id = int(parts[1])
    admin_repo.add_admin(user_id)
    await message.answer(f'Админ добавлен: {user_id}')


@router.message(Command('admin_del'))
async def admin_del_cmd(message: Message) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer('Команда доступна только администратору.')
        return
    parts = (message.text or '').split()
    if len(parts) < 2:
        await message.answer('Использование: /admin_del <telegram_user_id>')
        return
    user_id = int(parts[1])
    admin_repo.remove_admin(user_id)
    await message.answer(f'Админ удален: {user_id}')


@router.message(Command('admin_list'))
async def admin_list_cmd(message: Message) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer('Команда доступна только администратору.')
        return
    extra_admins = admin_repo.list_admins()
    all_admins = sorted(set(config.admin_ids + extra_admins))
    await message.answer('Админы: ' + ', '.join(str(item) for item in all_admins))


@router.message(Command('templates'))
async def templates_list(message: Message) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer('Команда доступна только администратору.')
        return
    sent_any = False
    for idx in range(1, 5):
        path = config.templates_dir / f'design_{idx}.pptx'
        if path.exists():
            await message.answer_document(FSInputFile(path), caption=f'Шаблон {idx}')
            sent_any = True
        else:
            await message.answer(f'Шаблон {idx} не найден.')

    mailer_path = config.templates_dir / f'design_{config.mailer_template_index}.txt'
    if mailer_path.exists():
        await message.answer_document(
            FSInputFile(mailer_path),
            caption=f'Шаблон {config.mailer_template_index} (рассылка)',
        )
        sent_any = True
    else:
        await message.answer(f'Шаблон {config.mailer_template_index} (рассылка) не найден.')

    if not sent_any:
        await message.answer('Шаблоны не найдены. Положите файлы в templates.')


@router.message(Command('template_set'))
async def template_set(message: Message, state: FSMContext) -> None:
    if not await _is_admin(message.from_user.id):
        await message.answer('Команда доступна только администратору.')
        return
    parts = (message.text or '').split(maxsplit=1)
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
        ext = 'txt'
    else:
        if not filename.lower().endswith('.pptx'):
            await message.answer('Нужен файл в формате PPTX.')
            return
        ext = 'pptx'

    config.templates_dir.mkdir(parents=True, exist_ok=True)
    config.temp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = config.temp_dir / f'template_{idx}_{secrets.token_hex(4)}.{ext}'
    await message.bot.download(message.document, destination=tmp_path)
    target_path = config.templates_dir / f'design_{idx}.{ext}'
    try:
        os.replace(tmp_path, target_path)
    except OSError:
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

