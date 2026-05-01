# Backend

## Current Runtime

- Production backend is deployed on:
  - `http://185.171.83.116:8010`
- Mobile/web client is fixed to this endpoint.
- Server layout on the remote host:
  - `/root/appslides/backend`
  - `/root/appslides/data`
  - `/root/appslides/templates`
  - `/root/appslides/temp`
  - `/root/appslides/logs`
- SQLite is mounted outside the container:
  - `/root/appslides/data/appslides.db`
- Fonts are not uploaded separately; the container uses system font fallbacks.
- Billing target for the current MVP is `YooKassa` in test mode, wired through backend APIs and chat-style client flow.
- Billing summary/generation checks now auto-sync unfinished YooKassa payments, so a paid subscription can become active without the user manually reopening a specific payment poll route.
- Backend now forwards legacy-style admin notifications into the separate Telegram admin bot using `ADMIN_BOT_TOKEN + ADMIN_IDS`.
- Current notification events mirrored from the legacy Telegram bot:
  - new client first seen;
  - outline created;
  - outline updated by comment;
  - YooKassa payment success;
  - manual renewal success/failure;
  - auto-renew success/failure with payment status and payment id;
  - subscription canceled;
  - presentation generation success/failure;
  - file conversion success/failure.
- Operational workflow for `git -> push -> deploy -> restart` is documented in `../OPERATIONS.md`.

Здесь будет серверная часть `AppSlides`.

Назначение backend:

- работа с AI/API;
- генерация outline/title/slides;
- генерация изображений;
- сборка `PPTX`;
- конвертация `PDF/DOCX/PPTX`;
- долгие фоновые job-задачи;
- минимальный серверный state: пользователи, устройства, подписки, платежи, entitlements, jobs;
- админ-инструменты и техлогика.

Технологическое направление на текущем этапе:

- Python backend;
- API-слой поверх логики из `telegrambot/services`;
- дальнейшая цель: вынести продуктовые сервисы из Telegram-зависимостей.

Стартовая структура:

```text
backend/
  src/
    api/
    core/
    domain/
    integrations/
    jobs/
    repositories/
    schemas/
  tests/
  runtime/
    templates/
    temp/
```

Текущий статус:

- поднят первый `FastAPI`-каркас;
- есть `healthcheck`;
- есть первые endpoints для генерации и пересборки outline;
- есть sync render и async job flow для презентаций и конвертаций;
- есть convenience download routes поверх job-результатов;
- есть локальные smoke-тесты на `unittest` без привязки к реальному AI;
- `backend/.venv` уже поднят локально и зависимости установлены;
- локальный backend успешно стартует и отвечает на `GET /v1/health`;
- backend автоматически подхватывает `.env` из:
  - `backend/.env`
  - корня проекта
  - `telegrambot/.env`

Быстрый запуск:

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Полезные endpoints:

- `GET /v1/health`
- `GET /v1/artifacts/{artifact_id}`
- `POST /v1/conversions/jobs`
- `GET /v1/conversions/jobs/{job_id}`
- `GET /v1/conversions/jobs/{job_id}/download`
- `GET /v1/templates/presentation`
- `POST /v1/presentations/outline`
- `POST /v1/presentations/outline/revise`
- `POST /v1/presentations/render`
- `POST /v1/presentations/jobs`
- `GET /v1/presentations/jobs/{job_id}`
- `GET /v1/presentations/jobs/{job_id}/download/pptx`
- `GET /v1/presentations/jobs/{job_id}/download/pdf`
- `GET /v1/billing/summary`
- `POST /v1/billing/payments`
- `GET /v1/billing/payments/{payment_id}`
- `POST /v1/billing/subscription/cancel`

Для billing и generation-запросов клиент передает `X-AppSlides-Client-Id`.

Пример запроса на outline:

```json
{
  "topic": "Удивительные факты о космосе для школьников",
  "slides_total": 7
}
```

Пример ответа:

```json
{
  "title": "Удивительные факты о космосе",
  "outline": [
    "Что такое космос",
    "Как устроена Солнечная система"
  ],
  "slides_total": 7,
  "content_slides": 6
}
```

Пример запроса на рендер презентации:

```json
{
  "topic": "Удивительные факты о космосе для школьников",
  "title": "Факты о космосе",
  "outline": [
    "Что такое космос",
    "Солнечная система",
    "Интересные планеты",
    "Кометы и астероиды",
    "Космос и человек",
    "Будущее исследований"
  ],
  "design_id": 1,
  "generate_pdf": true
}
```

Что делает `render` сейчас:

- генерирует тексты слайдов;
- генерирует или подставляет placeholder-изображения;
- собирает `PPTX` по выбранному шаблону;
- пытается собрать `PDF`, если `generate_pdf=true` и доступен LibreOffice;
- регистрирует артефакты и отдает `download_url`.

Важно:

- пока это синхронный render endpoint, не job queue;
- download-хранилище сейчас in-memory на процесс, это промежуточный этап до полноценной job/DB модели.

Async jobs:

- `POST /v1/presentations/jobs` создает фоновую задачу рендера;
- `GET /v1/presentations/jobs/{job_id}` отдает статус `queued/running/succeeded/failed`;
- `GET /v1/presentations/jobs/{job_id}/download/pptx` и `GET /v1/presentations/jobs/{job_id}/download/pdf` отдают итоговые файлы, когда job завершена;
- `POST /v1/conversions/jobs` принимает multipart upload и создает фоновую задачу конвертации;
- `GET /v1/conversions/jobs/{job_id}` отдает статус и артефакт после завершения.
- `GET /v1/conversions/jobs/{job_id}/download` отдает итоговый сконвертированный файл.

Текущее ограничение job model:

- store задач и download registry живут в памяти процесса;
- после рестарта сервера статусы и ссылки пропадут;
- это промежуточный этап до Redis/Postgres.

Smoke-проверка:

```bash
python -m unittest discover -s backend/tests -v
```

Для `fastapi.testclient` в backend requirements теперь включен `httpx`.

PowerShell helper scripts:

```powershell
# старт backend в фоне
.\scripts\dev\start_backend.ps1

# healthcheck
.\scripts\dev\backend_health.ps1

# остановка backend
.\scripts\dev\stop_backend.ps1
```

Что проверяется сейчас:

- `GET /v1/health`
- `GET /v1/templates/presentation`
- `POST /v1/presentations/outline`
- async presentation job + `download/pptx`
- async conversion job + `download`
