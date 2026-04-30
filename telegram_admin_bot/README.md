# AppSlides Admin Telegram Bot

Отдельный Telegram-бот для администраторов `AppSlides`.

Что умеет:

- смотреть общую статистику;
- смотреть статистику по рекламным меткам;
- вручную начислять и отключать генерации;
- проверять и отменять подписки;
- создавать промокоды;
- управлять списком админов;
- смотреть и заменять шаблоны презентаций.

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

- бот работает с той же SQLite-базой, что и backend `appslides`;
- super-admin доступ задаётся через `ADMIN_IDS` в `.env`;
- дополнительные админы хранятся в таблице `admins`;
- команды `sub_*` в мобильной версии работают по `client_id`, а не по Telegram `user_id`.
