# apptaro Backend

FastAPI backend для Google Play версии `AI Tarot Reading`: tarot reading jobs, artifacts, entitlements, promo codes, Google Play Billing validation и admin notifications.

## Runtime

- Production backend: `http://185.171.83.116:8022`
- Remote app dir: `/root/PMapptaro`
- SQLite: `/root/PMapptaro/data/pmapptaro.db`
- Google Play service account on host: `/root/PMapptaro/data/google-play-service-account.json`
- Google Play service account in Docker: `/data/google-play-service-account.json`
- Admin bot: отдельный `telegram_admin_bot/`, `ADMIN_BOT_TOKEN`, `ADMIN_IDS`
- Legacy YooKassa redirect billing: disabled by default via `ENABLE_LEGACY_YOOKASSA_BILLING=0`

## Product Flow

Старые endpoint names `presentations/*` сохранены как compatibility слой для Flutter-клиента:

- `topic` означает вопрос пользователя.
- `outline` означает черновик трехкартного расклада.
- `render/job` генерирует tarot reading вместо PPTX/PDF.
- `design_id` остается техническим compatibility-полем и не выбирается пользователем.
- Job result содержит `reading_text` и artifacts:
  - `image` - JPG расклада;
  - `txt` - текстовый разбор.

Trial teaser:

- Новый unpaid `client_id` может один раз получить one-card preview.
- После teaser следующий полный reading требует entitlement.

## Tarot Domain

- `src/domain/tarot_deck.py` - загрузка колоды, вытягивание карт, orientation markers.
- `src/domain/tarot_layout.py` - сборка JPG расклада из background/layout/card images.
- `src/domain/presentation_outline_service.py` - создание/обновление трехкартного outline.
- `src/domain/presentation_render_service.py` - генерация текста, JPG/TXT artifacts и job result.
- `src/domain/presentation_prompts.py` - prompts для заголовков, teaser, full reading и follow-up.
- `runtime/tarot/` - карты, background и layout из исходного Telegram tarot bot.

## Billing

Основной billing для Google Play версии:

- `GET /v1/billing/summary` - тарифы, баланс, active/latest subscription.
- `POST /v1/billing/google-play/verify` - server-side validation Google Play purchase token.
- `POST /v1/billing/promo/redeem` - активация промокода.
- `POST /v1/billing/subscription/cancel` - legacy/manual cancel compatibility.

Flutter Google Play client не использует YooKassa checkout и не вызывает `/v1/billing/payments`.

В backend пока сохранены внутренние legacy YooKassa методы для совместимости старого платформенного каркаса. Public redirect endpoints в Google Play backend отключены и возвращают `410 Gone`. Даже при наличии старых YooKassa ключей legacy billing не включается без явного `ENABLE_LEGACY_YOOKASSA_BILLING=1`.

Google Play product ids задаются в `src/domain/billing_plans.py`:

```text
weekly_readings
monthly_readings
one10_readings
one40_readings
```

## Admin Events

Backend отправляет тематические уведомления:

- new client/install;
- outline created/updated;
- tarot reading success/failure;
- Google Play purchase success/failure;
- promo redeemed;
- manual grant/cancel events;
- file conversion success/failure as compatibility event.

## Endpoints

- `GET /v1/health`
- `GET /v1/templates/presentation`
- `POST /v1/presentations/outline`
- `POST /v1/presentations/outline/revise`
- `POST /v1/presentations/jobs`
- `GET /v1/presentations/jobs/{job_id}`
- `GET /v1/presentations/jobs/{job_id}/download/image`
- `GET /v1/presentations/jobs/{job_id}/download/txt`
- `GET /v1/artifacts/{artifact_id}`
- `GET /v1/billing/summary`
- `POST /v1/billing/google-play/verify`
- `POST /v1/billing/promo/redeem`
- `POST /v1/billing/subscription/cancel`

Disabled legacy redirect endpoints:

- `POST /v1/billing/payments`
- `GET /v1/billing/payments/{payment_id}`

Оба endpoint возвращают `410 Gone` с указанием использовать `POST /v1/billing/google-play/verify`.

## Local Run

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

## Checks

Run from repository root:

```powershell
python -m compileall backend/src telegram_admin_bot
python -m unittest discover -s backend/tests -v
python -c "import telegram_admin_bot.main; print('admin bot import ok')"
```

Deploy process: `../OPERATIONS.md`.
