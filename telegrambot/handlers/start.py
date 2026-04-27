from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery

from config import load_config
from database.models import upsert_user, record_user_tag, get_ad_tag, get_user, use_promo_code
from keyboards.inline import main_menu_kb, main_menu_button_kb
from services.logger import get_logger
from services.admin_notify import notify_admins

router = Router()
logger = get_logger()
config = load_config()


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    user = message.from_user
    existing = await get_user(user.id)
    is_new_user = existing is None
    await upsert_user(user.id, user.username or '', user.first_name or '', user.last_name or '')
    logger.info('User start: id=%s username=%s', user.id, user.username)
    args = ''
    if message.text:
        parts = message.text.split(maxsplit=1)
        if len(parts) > 1:
            args = parts[1].strip()
    promo_code = ''
    if args.startswith('promo_'):
        promo_code = args[6:].strip()
    if promo_code:
        ok, msg, tokens = await use_promo_code(user.id, promo_code)
        await message.answer(msg)
        if ok:
            await notify_admins(
                message.bot,
                f'🎁 Промокод активирован: {promo_code} (+{tokens}) пользователем {user.id} (@{user.username or "-"})',
            )
    notified = False
    if args and not promo_code:
        candidates = [args]
        if args.startswith('tag_'):
            candidates.append(args[4:])
        else:
            candidates.append(f'tag_{args}')
        for candidate in candidates:
            info = await get_ad_tag(candidate)
            if info:
                await record_user_tag(user.id, candidate, args)
                if is_new_user:
                    await notify_admins(
                        message.bot,
                        f'👤 Новый пользователь: {user.id} (@{user.username or "-"}) , метка: {candidate}',
                    )
                    notified = True
                break
    if is_new_user and not notified:
        await notify_admins(
            message.bot,
            f'👤 Новый пользователь: {user.id} (@{user.username or "-"}) , метка: без метки',
        )
    await message.answer(
        '🎬 AI Презентации\n'
        'Создавай презентации и конвертируй файлы за пару минут.\n\n'
        '🚀 Генерация — по теме и пожеланиям\n'
        '🎨 Дизайны — 4 шаблона на выбор\n'
        '🖼️ Иллюстрации — авто‑генерация\n'
        '🧰 Инструменты — PDF/DOCX/PPTX\n\n'
        'Выбирай раздел ниже 👇',
        reply_markup=main_menu_kb(),
    )


@router.message(Command('menu'))
async def cmd_menu(message: Message) -> None:
    user = message.from_user
    logger.info('User menu: id=%s username=%s', user.id, user.username)
    await message.answer('Главное меню 📌', reply_markup=main_menu_kb())


@router.message(Command('help'))
async def cmd_help(message: Message) -> None:
    user = message.from_user
    logger.info('User help: id=%s username=%s', user.id, user.username)
    await message.answer(
        '❓ Помощь\n'
        '1) Нажмите «Создать презентацию»\n'
        '2) Укажите тему и пожелания\n'
        '3) Утвердите план и дизайн\n'
        '4) Получите PPTX и PDF\n\n'
        f'Если что-то не работает — напишите в поддержку:\n{config.support_username}',
        reply_markup=main_menu_button_kb(),
    )


@router.callback_query(F.data == 'menu:main')
async def menu_callback(callback: CallbackQuery) -> None:
    user = callback.from_user
    logger.info('Menu click: main user=%s username=%s', user.id, user.username)
    await callback.answer()
    await callback.message.answer('Главное меню 📌', reply_markup=main_menu_kb())


@router.callback_query(F.data == 'menu:help')
async def help_callback(callback: CallbackQuery) -> None:
    user = callback.from_user
    logger.info('Menu click: help user=%s username=%s', user.id, user.username)
    await callback.answer()
    await callback.message.answer(
        '❓ Помощь\n'
        '1) Нажмите «Создать презентацию»\n'
        '2) Укажите тему и пожелания\n'
        '3) Утвердите план и дизайн\n'
        '4) Получите PPTX и PDF\n\n'
        f'Если что-то не работает — напишите в поддержку:\n{config.support_username}',
        reply_markup=main_menu_button_kb(),
    )
