import asyncio

from aiohttp import ClientTimeout
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import BotCommand
from aiogram.types import BotCommandScopeChat

from config import load_config
from services.logger import setup_logger, get_logger
from services.runtime import set_storage
from services.auto_renew import auto_renew_loop
from services.mailer import mailer_loop
from database.db import init_db, DB_PATH
from handlers import start, presentation_gen, file_converter, subscription, admin


async def _set_commands(bot: Bot, admin_ids: list[int]) -> None:
    user_commands = [
        BotCommand(command='start', description='Запуск и главное меню'),
        BotCommand(command='menu', description='Главное меню'),
        BotCommand(command='balance', description='Баланс / подписка'),
        BotCommand(command='help', description='Помощь'),
        BotCommand(command='presentation', description='Создать презентацию'),
        BotCommand(command='pdf2docx', description='PDF → DOCX'),
        BotCommand(command='docx2pdf', description='DOCX → PDF'),
        BotCommand(command='pptx2pdf', description='PPTX → PDF'),
    ]
    admin_commands = user_commands + [
        BotCommand(command='sub_on', description='Начислить генерации'),
        BotCommand(command='sub_off', description='Обнулить генерации'),
        BotCommand(command='sub_check', description='Проверить баланс'),
        BotCommand(command='sub_cancel', description='Отключить подписку'),
        BotCommand(command='adstats', description='Статистика по метке'),
        BotCommand(command='adstats_all', description='Статистика по всем меткам'),
        BotCommand(command='botstats', description='Общая статистика бота'),
        BotCommand(command='adtag', description='Создать метку'),
        BotCommand(command='tag', description='Создать метку (alias)'),
        BotCommand(command='genpromo', description='Создать промокод'),
        BotCommand(command='admin_add', description='Добавить админа'),
        BotCommand(command='admin_del', description='Удалить админа'),
        BotCommand(command='admin_list', description='Список админов'),
        BotCommand(command='templates', description='Показать шаблоны'),
        BotCommand(command='template_set', description='Заменить шаблон'),
    ]
    await bot.set_my_commands(user_commands)
    for admin_id in admin_ids:
        await bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))


async def _cleanup_temp_dir(config) -> None:
    import os
    import shutil
    import time

    while True:
        now = time.time()
        try:
            os.makedirs(config.temp_dir, exist_ok=True)
            for name in os.listdir(config.temp_dir):
                path = os.path.join(config.temp_dir, name)
                try:
                    age = now - os.path.getmtime(path)
                except OSError:
                    continue
                if age < config.temp_ttl_seconds:
                    continue
                if os.path.isdir(path):
                    try:
                        shutil.rmtree(path, ignore_errors=True)
                    except OSError:
                        pass
                elif os.path.isfile(path):
                    try:
                        os.remove(path)
                    except OSError:
                        pass
        except OSError:
            pass
        await asyncio.sleep(config.temp_clean_interval)


async def main() -> None:
    config = load_config()
    setup_logger(config.log_file, config.log_max_lines)
    logger = get_logger()
    logger.info('Bot starting...')
    if not config.bot_token:
        raise RuntimeError('BOT_TOKEN is not set')

    await init_db()
    _log_startup_checks(config, logger)

    session = AiohttpSession(timeout=config.download_timeout)
    bot = Bot(token=config.bot_token, session=session)
    dp = Dispatcher()
    set_storage(dp.storage)

    dp.include_router(start.router)
    dp.include_router(presentation_gen.router)
    dp.include_router(file_converter.router)
    dp.include_router(subscription.router)
    dp.include_router(admin.router)

    await _set_commands(bot, config.admin_ids)
    logger.info('Bot started')
    asyncio.create_task(_cleanup_temp_dir(config))
    asyncio.create_task(auto_renew_loop(bot, config))
    asyncio.create_task(mailer_loop(bot, config))
    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()


def _log_startup_checks(config, logger) -> None:
    import os
    import subprocess

    logger.info('DB_PATH=%s', DB_PATH)
    if os.path.exists(DB_PATH):
        logger.info('DB file found')
    else:
        logger.warning('DB file not found, new database will be created on write')

    missing = []
    for idx in range(1, 5):
        path = os.path.join(config.templates_dir, f'design_{idx}.pptx')
        if not os.path.exists(path):
            missing.append(path)
    if missing:
        logger.warning('Missing templates: %s', ', '.join(missing))
    else:
        logger.info('Templates OK (1-4)')

    fonts_dir = (config.fonts_dir or '').strip()
    if fonts_dir:
        if os.path.isdir(fonts_dir):
            count = 0
            sample = []
            try:
                for root, _dirs, files in os.walk(fonts_dir):
                    for name in files:
                        if not name.lower().endswith(('.ttf', '.otf', '.ttc')):
                            continue
                        count += 1
                        if len(sample) < 3:
                            sample.append(os.path.join(root, name))
            except OSError:
                count = 0
                sample = []
            if sample:
                logger.info('Fonts dir: %s (files=%s, sample=%s)', fonts_dir, count, '; '.join(sample))
            else:
                logger.info('Fonts dir: %s (files=%s)', fonts_dir, count)
            if os.name != 'nt':
                try:
                    subprocess.run(['fc-cache', '-f', fonts_dir], check=True, capture_output=True, text=True)
                    logger.info('Fonts cache updated for %s', fonts_dir)
                except FileNotFoundError:
                    logger.warning('fc-cache not found, fonts may not be picked up')
                except Exception:  # noqa: BLE001
                    logger.warning('Fonts cache update failed for %s', fonts_dir)
        else:
            logger.warning('Fonts dir not found: %s', fonts_dir)

    mailer_path = os.path.join(config.templates_dir, f'design_{config.mailer_template_index}.txt')
    if os.path.exists(mailer_path):
        logger.info('Mailer template: %s', mailer_path)
    else:
        logger.warning('Mailer template not found: %s', mailer_path)


if __name__ == '__main__':
    asyncio.run(main())
