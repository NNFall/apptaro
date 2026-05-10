from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError, TelegramServerError
from aiogram.types import BotCommand, BotCommandScopeChat, Update

from telegram_admin_bot.config import AdminBotConfig, load_config

from src.repositories.storage import configure_database_path, init_storage

from .handlers import admin as admin_handlers


logger = logging.getLogger(__name__)


def _touch_heartbeat(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text('', encoding='utf-8')


async def _set_commands(bot: Bot, admin_ids: list[int]) -> None:
    commands = [
        BotCommand(command='botstats', description='Общая статистика'),
        BotCommand(command='adstats', description='Статистика по метке'),
        BotCommand(command='adstats_all', description='Статистика по всем меткам'),
        BotCommand(command='adtag', description='Создать рекламную метку'),
        BotCommand(command='tag', description='Создать рекламную метку (alias)'),
        BotCommand(command='sub_on', description='Начислить расклады'),
        BotCommand(command='sub_off', description='Обнулить расклады'),
        BotCommand(command='sub_check', description='Проверить баланс'),
        BotCommand(command='sub_cancel', description='Отключить подписку'),
        BotCommand(command='genpromo', description='Создать промокод'),
        BotCommand(command='admin_add', description='Добавить админа'),
        BotCommand(command='admin_del', description='Удалить админа'),
        BotCommand(command='admin_list', description='Список админов'),
        BotCommand(command='templates', description='Показать файлы шаблонов'),
        BotCommand(command='template_set', description='Заменить файл шаблона'),
    ]
    await bot.set_my_commands(commands)
    for admin_id in admin_ids:
        try:
            await bot.set_my_commands(commands, scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception:  # noqa: BLE001
            logger.exception('Failed to set chat commands for admin_id=%s', admin_id)


async def _poll_updates(bot: Bot, dp: Dispatcher, config: AdminBotConfig) -> None:
    offset: int | None = None
    backoff_seconds = 1
    allowed_updates = dp.resolve_used_update_types()

    await bot.delete_webhook(drop_pending_updates=False)

    while True:
        try:
            updates: list[Update] = await bot.get_updates(
                offset=offset,
                timeout=config.polling_timeout_seconds,
                allowed_updates=allowed_updates,
                request_timeout=config.polling_timeout_seconds + 15,
            )
            _touch_heartbeat(config.heartbeat_path)
            backoff_seconds = 1

            for update in updates:
                offset = update.update_id + 1
                await dp.feed_update(bot, update)
        except asyncio.CancelledError:
            raise
        except (TelegramNetworkError, TelegramServerError):
            logger.exception('Admin bot polling failed, retry in %ss', backoff_seconds)
            await asyncio.sleep(backoff_seconds)
            backoff_seconds = min(
                max(1, config.polling_retry_max_seconds),
                backoff_seconds * 2,
            )
        except Exception:  # noqa: BLE001
            logger.exception('Unexpected admin bot polling failure, retry in %ss', backoff_seconds)
            await asyncio.sleep(backoff_seconds)
            backoff_seconds = min(
                max(1, config.polling_retry_max_seconds),
                backoff_seconds * 2,
            )


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    )

    config = load_config()
    if not config.bot_token:
        raise RuntimeError('ADMIN_BOT_TOKEN is not set')

    configure_database_path(config.database_path)
    init_storage(config.database_path)

    session = AiohttpSession()
    bot = Bot(token=config.bot_token, session=session)
    dp = Dispatcher()
    dp.include_router(admin_handlers.router)

    try:
        await _set_commands(bot, config.admin_ids)
        await _poll_updates(bot, dp, config)
    finally:
        await bot.session.close()


if __name__ == '__main__':
    asyncio.run(main())
