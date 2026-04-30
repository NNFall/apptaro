FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY telegram_admin_bot/requirements.txt /tmp/telegram_admin_bot_requirements.txt
RUN pip install --no-cache-dir -r /tmp/telegram_admin_bot_requirements.txt

COPY telegram_admin_bot ./telegram_admin_bot
COPY backend/src ./backend/src

CMD ["python", "-m", "telegram_admin_bot.main"]
