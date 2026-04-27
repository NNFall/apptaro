# Slides Bot

Telegram-бот для генерации презентаций (.pptx, .pdf) и конвертации файлов.

## Быстрый старт

1. Установить зависимости:

```bash
pip install -r requirements.txt
```

2. Создать `.env` (пример ниже) и положить 4 шаблона:

```
media/templates/design_1.pptx
media/templates/design_2.pptx
media/templates/design_3.pptx
media/templates/design_4.pptx
```

Текстовый шаблон для рассылки:

```
media/templates/design_5.txt
```

Опционально: добавить превью шаблонов:

```
media/templates/preview_1.jpg
media/templates/preview_2.jpg
media/templates/preview_3.jpg
media/templates/preview_4.jpg
```

3. Запустить:

```bash
python main.py
```

## .env пример

```
BOT_TOKEN=xxx
BOT_USERNAME=your_bot_username
ADMIN_IDS=123456789,987654321

DB_PATH=/data/data.db

KIE_API_KEY=
KIE_BASE_URL=https://api.kie.ai
KIE_TEXT_MODEL=gemini-flash
KIE_TEXT_ENDPOINT=
KIE_IMAGE_MODEL=flux-nano-banana
KIE_API_URL=
KIE_IMAGE_ENDPOINT=

REPLICATE_API_TOKEN=
REPLICATE_BASE_URL=https://api.replicate.com
REPLICATE_MODEL=black-forest-labs/flux-schnell
REPLICATE_WAIT_SECONDS=60
REPLICATE_POLL_INTERVAL=1.5
REPLICATE_TIMEOUT_SECONDS=120
REPLICATE_DEFAULT_INPUT=
REPLICATE_TEXT_MODEL=google/gemini-3-flash
REPLICATE_TEXT_PROMPT_FIELD=prompt
REPLICATE_TEXT_DEFAULT_INPUT=

LIBREOFFICE_PATH=soffice

STARS_PROVIDER_TOKEN=
YOOKASSA_SHOP_ID=
YOOKASSA_SECRET=
YOOKASSA_RETURN_URL=

TEMP_DIR=media/temp
TEMPLATES_DIR=media/templates
SEND_DOCX=0

LOG_FILE=logs/bot.log
MAX_UPLOAD_MB=40
DOWNLOAD_TIMEOUT=300
TEMP_TTL_SECONDS=3600
TEMP_CLEAN_INTERVAL=600
AUTO_RENEW_INTERVAL=60
FONT_FALLBACK=Cambria
FONT_WHITELIST=Cambria,Calibri,Arial,Times New Roman
FONTS_DIR=/usr/share/fonts/custom
MAILER_ENABLED=1
MAILER_TEMPLATE_INDEX=5
MAILER_PREVIEW_MINUTES=30
MAILER_PAUSE_HOURS=12
MAILER_TICK_SECONDS=30
MAILER_RATE_PER_SEC=25
```

## Деплой на Ubuntu (Docker)

### Вариант A: docker-compose (рекомендуется)

#### 1. Установите Docker и Compose plugin

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin
sudo systemctl enable --now docker
```

#### 2. Залейте проект на сервер

Например в `/root/slides_bot` через SFTP (Termius) или `git clone`.

#### 3. Создайте папки для данных, шаблонов и шрифтов

```bash
sudo mkdir -p /root/slides_bot/data /root/slides_bot/templates /root/slides_bot/logs /root/slides_bot/temp /root/slides_bot/fonts
```

В `/opt/slides_bot/templates` положите:

```
design_1.pptx
design_2.pptx
design_3.pptx
design_4.pptx
design_5.txt
```

#### 4. Настройте `.env`

В корне проекта (`/root/slides_bot/.env`) добавьте:

```
DB_PATH=/data/data.db
TEMPLATES_DIR=/app/media/templates
TEMP_DIR=/app/media/temp
LOG_FILE=/app/logs/bot.log
FONTS_DIR=/usr/share/fonts/custom
```

Остальные переменные как в примере выше.

#### 5. Запуск

```bash
cd /root/slides_bot
sudo docker compose up -d --build
```

SQLite будет храниться в `/root/slides_bot/data`, поэтому база не теряется при рестартах.

#### 6. Логи и перезапуск

```bash
sudo docker compose logs -f
sudo docker compose restart
```

#### 7. Обновление кода

```bash
cd /root/slides_bot
# обновить файлы
sudo docker compose down
sudo docker compose up -d --build
```

---

### Вариант B: запуск вручную через Dockerfile

### 1. Установите Docker

```bash
sudo apt update
sudo apt install -y docker.io
sudo systemctl enable --now docker
```

### 2. Залейте проект на сервер

Например в `/root/slides_bot` через SFTP (Termius) или `git clone`.

### 3. Создайте папки для данных, шаблонов и шрифтов

```bash
sudo mkdir -p /root/slides_bot/data /root/slides_bot/templates /root/slides_bot/logs /root/slides_bot/temp /root/slides_bot/fonts
```

В `/opt/slides_bot/templates` положите файлы:

```
design_1.pptx
design_2.pptx
design_3.pptx
design_4.pptx
design_5.txt
```

### 4. Настройте `.env`

В корне проекта на сервере (`/root/slides_bot/.env`) добавьте:

```
DB_PATH=/data/data.db
TEMPLATES_DIR=/app/media/templates
TEMP_DIR=/app/media/temp
LOG_FILE=/app/logs/bot.log
```

Остальные переменные как в примере выше.

### 5. Соберите образ (Dockerfile)

```bash
cd /root/slides_bot
sudo docker build -t slides_bot .
```

### 6. Запустите контейнер

```bash
sudo docker run -d \
  --name slides_bot \
  --restart unless-stopped \
  --env-file .env \
  -v /root/slides_bot/data:/data \
  -v /root/slides_bot/templates:/app/media/templates \
  -v /root/slides_bot/logs:/app/logs \
  -v /root/slides_bot/temp:/app/media/temp \
  -v /root/slides_bot/fonts:/usr/share/fonts/custom:ro \
  slides_bot
```

SQLite будет храниться в `/root/slides_bot/data`, поэтому база не теряется при рестартах.

### 7. Логи и перезапуск

```bash
sudo docker logs -f slides_bot
sudo docker restart slides_bot
```

### 8. Обновление кода

```bash
cd /root/slides_bot
# обновить файлы
sudo docker build -t slides_bot .
sudo docker stop slides_bot && sudo docker rm slides_bot
sudo docker run -d --name slides_bot --restart unless-stopped --env-file .env \
  -v /root/slides_bot/data:/data \
  -v /root/slides_bot/templates:/app/media/templates \
  -v /root/slides_bot/logs:/app/logs \
  -v /root/slides_bot/temp:/app/media/temp \
  slides_bot
```

## Примечания

- Для конвертации нужен LibreOffice в headless режиме.
- Чтобы PDF выглядел так же как PPTX, нужны те же шрифты в контейнере. В Dockerfile уже добавлены `fonts-liberation`, `fonts-dejavu-core`, `fonts-noto-core`. Если ваши шаблоны используют другие шрифты — добавьте их в `/root/slides_bot/fonts` (примонтируется в `/usr/share/fonts/custom`) и перезапустите контейнер. Бот при старте выполнит `fc-cache` и зарегистрирует шрифты.
- Добавлены `fonts-crosextra-caladea`/`fonts-crosextra-carlito` как замены Cambria/Calibri на Linux. Если нужен именно Cambria — установите шрифт в контейнер вручную и укажите `FONT_FALLBACK=Cambria`.
- Если шрифт в шаблоне не входит в `FONT_WHITELIST`, бот заменит его на `FONT_FALLBACK` при генерации, чтобы PDF и PPTX совпадали.
- Интеграция оплаты ЮKassa/Stars подготовлена как каркас. Требуется подключение провайдера и настройка webhook.
- Если KIE API не настроен, бот делает заглушки: упрощенный план и placeholder картинки.
- Для Replicate установите `REPLICATE_API_TOKEN`. Опции модели можно передать в `REPLICATE_DEFAULT_INPUT` как JSON (например, параметры качества/размера).
- Для текстового фоллбэка через Replicate используйте `REPLICATE_TEXT_MODEL` (например, `google/gemini-3-flash`) и при необходимости `REPLICATE_TEXT_PROMPT_FIELD`/`REPLICATE_TEXT_DEFAULT_INPUT`.
- Автопродление доступно только для оплат ЮKassa с сохраненной картой (save_payment_method).

## Команды администратора

- `/botstats`
- `/adstats`
- `/adstats_all`
- `/adtag <метка>`
- `/tag <метка>`
- `/templates`
- `/template_set 1|2|3|4|5` (шаблон 5 — текст рассылки)
