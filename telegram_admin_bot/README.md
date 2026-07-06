# PMapptaro Admin Telegram Bot

Отдельный Telegram-бот для администраторов Google Play версии `AI Tarot Reading`.

Что умеет:

- смотреть общую статистику;
- смотреть статистику по рекламным меткам;
- вручную начислять и отключать расклады;
- проверять и отменять подписки;
- создавать промокоды;
- управлять списком админов.

Запуск локально:

```powershell
cd telegram_admin_bot
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m telegram_admin_bot.main
```

Важно:

- бот работает с той же SQLite-базой, что и backend `PMapptaro`;
- super-admin доступ задаётся через `ADMIN_IDS` в `.env`;
- дополнительные админы хранятся в таблице `admins`;
- команды `sub_*` в мобильной версии работают по `client_id`, а не по Telegram `user_id`.
- `ADMIN_BOT_TOKEN` должен быть токеном отдельного Telegram-бота, не тем же токеном, что используется в других проектах на сервере.
