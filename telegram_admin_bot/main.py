from __future__ import annotations

import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import BotCommand, BotCommandScopeChat

from telegram_admin_bot.config import load_config

from src.repositories.storage import configure_database_path, init_storage

from .handlers import admin as admin_handlers


async def _set_commands(bot: Bot, admin_ids: list[int]) -> None:
    commands = [
        BotCommand(command='botstats', description='Общая статистика'),
        BotCommand(command='adstats', description='Статистика по метке'),
        BotCommand(command='adstats_all', description='Статистика по всем меткам'),
        BotCommand(command='adtag', description='Создать рекламную метку'),
        BotCommand(command='tag', description='Создать рекламную метку (alias)'),
        BotCommand(command='sub_on', description='Начислить генерации'),
        BotCommand(command='sub_off', description='Обнулить генерации'),
        BotCommand(command='sub_check', description='Проверить баланс'),
        BotCommand(command='sub_cancel', description='Отключить подписку'),
        BotCommand(command='genpromo', description='Создать промокод'),
        BotCommand(command='admin_add', description='Добавить админа'),
        BotCommand(command='admin_del', description='Удалить админа'),
        BotCommand(command='admin_list', description='Список админов'),
        BotCommand(command='templates', description='Показать шаблоны'),
        BotCommand(command='template_set', description='Заменить шаблон'),
    ]
    for admin_id in admin_ids:
        await bot.set_my_commands(commands, scope=BotCommandScopeChat(chat_id=admin_id))


async def main() -> None:
    config = load_config()
    if not config.bot_token:
        raise RuntimeError('ADMIN_BOT_TOKEN is not set')

    configure_database_path(config.database_path)
    init_storage(config.database_path)

    session = AiohttpSession()
    bot = Bot(token=config.bot_token, session=session)
    dp = Dispatcher()
    dp.include_router(admin_handlers.router)
    await _set_commands(bot, config.admin_ids)
    await dp.start_polling(bot)


if __name__ == '__main__':
    asyncio.run(main())

