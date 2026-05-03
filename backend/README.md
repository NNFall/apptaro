# apptaro Backend

Backend остается FastAPI-сервисом с billing, jobs, artifacts, admin notifications и deploy-контуром из исходной платформы. Предметный слой адаптирован под расклады таро.

## Runtime

- Production backend: `http://185.171.83.116:8010`
- Remote app dir: `/root/appslides`
- SQLite: `/root/appslides/data/appslides.db`
- Billing: YooKassa через backend API.
- Admin notifications: отдельный `telegram_admin_bot/` через `ADMIN_BOT_TOKEN` и `ADMIN_IDS`.

## Product flow

Старые presentation endpoint names сохранены для совместимости клиента и deploy-процесса:

- `topic` теперь означает вопрос пользователя.
- `outline` теперь означает черновик из трех карт: ситуация, препятствие, совет.
- `render/job` теперь генерирует tarot reading вместо PPTX/PDF.
- `design_id` остается техническим compatibility-полем, в пользовательском flow не выбирается.
- Результат job содержит `reading_text` и artifacts:
  - `image` - JPG расклада;
  - `txt` - текстовый разбор.

## Tarot domain

- `src/domain/tarot_deck.py` - загрузка колоды, вытягивание карт, служебные card markers.
- `src/domain/tarot_layout.py` - сборка JPG расклада из background/layout/card images.
- `src/domain/presentation_outline_service.py` - создание и пересборка трехкарточного outline.
- `src/domain/presentation_render_service.py` - генерация текста, JPG/TXT artifacts и job result.
- `src/domain/presentation_prompts.py` - prompts для заголовка и интерпретации.
- `runtime/tarot/` - карты, background и layout, перенесенные из `telegram_taro_bot/media/tarot/`.

## Billing

Платежный каркас YooKassa не перенесен в Flutter. Backend продолжает:

- создавать платежи;
- poll/sync незавершенные YooKassa payments;
- хранить entitlements по `client_id`;
- списывать один расклад при запуске paid generation;
- уведомлять admin bot о платежах, продлениях и ошибках.

Пользовательские формулировки тарифов заменены на расклады:

- недельная подписка: 15 раскладов;
- месячная подписка: 100 раскладов.

## Admin events

Backend отправляет тематические уведомления:

- новый client/install;
- создан черновик расклада;
- расклад обновлен;
- успешный/ошибочный tarot reading;
- успешная оплата;
- manual/auto renewal success/failure;
- отмена подписки;
- file conversion success/failure как сохраненный платформенный event.

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
- `POST /v1/billing/payments`
- `GET /v1/billing/payments/{payment_id}`
- `POST /v1/billing/subscription/cancel`

## Локальный запуск

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

## Проверки

```powershell
python -m compileall backend/src telegram_admin_bot
python -m unittest discover -s backend/tests -v
python -c "import telegram_admin_bot.main; print('admin bot import ok')"
```

Deploy выполняется по [../OPERATIONS.md](../OPERATIONS.md).
