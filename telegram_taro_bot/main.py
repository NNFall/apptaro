import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeChat
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.exceptions import TelegramBadRequest

from config import load_config
from database.db import setup as setup_db
from handlers import all_routers
from services.subscription_tasks import subscription_watcher
from services.smart_mailer import smart_mailing_loop


async def main() -> None:
    config = load_config()
    if not config.bot_token:
        raise RuntimeError('BOT_TOKEN is empty. Fill .env')

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)s | %(name)s | %(message)s',
    )
    logger = logging.getLogger(__name__)

    await setup_db(config.database_path)

    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    for router in all_routers:
        dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)
    user_cmds = [
        BotCommand(command='start', description='Запуск и главное меню'),
        BotCommand(command='menu', description='Главное меню'),
        BotCommand(command='ask', description='Задать вопрос таро'),
        BotCommand(command='balance', description='Баланс'),
        BotCommand(command='help', description='Помощь'),
        BotCommand(command='invite', description='Пригласить друга'),
    ]

    await bot.set_my_commands(user_cmds)
    if config.admin_ids:
        admin_cmds = user_cmds + [
            BotCommand(command='sub_on', description='Начислить расклады'),
            BotCommand(command='sub_off', description='Обнулить расклады'),
            BotCommand(command='sub_check', description='Проверить баланс'),
            BotCommand(command='sub_cancel', description='Отключить подписку'),
            BotCommand(command='adstats', description='Статистика по метке'),
            BotCommand(command='adstats_all', description='Статистика по всем меткам'),
            BotCommand(command='botstats', description='Общая статистика бота'),
            BotCommand(command='adtag', description='Создать метку'),
            BotCommand(command='genpromo', description='Создать промокод'),
            BotCommand(command='admin_add', description='Добавить админа'),
            BotCommand(command='admin_del', description='Удалить админа'),
            BotCommand(command='admin_list', description='Список админов'),
        ]
        for admin_id in config.admin_ids:
            try:
                await bot.set_my_commands(admin_cmds, scope=BotCommandScopeChat(chat_id=admin_id))
            except TelegramBadRequest as e:
                logger.warning('Skip admin commands for chat_id=%s error=%s', admin_id, e)
    asyncio.create_task(subscription_watcher(bot))
    asyncio.create_task(smart_mailing_loop(bot))
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


if __name__ == '__main__':
    asyncio.run(main())
