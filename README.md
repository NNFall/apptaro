# apptaro

`apptaro` - мобильное AI-приложение в формате единого чата для раскладов таро.

Проект построен не с нуля: это адаптация готового платформенного каркаса AppSlides под новую предметную область. Сохранены Flutter-клиент, Python backend, billing через YooKassa, локальная история чата и файлов, `client_id` как ключ установки, отдельный Telegram admin bot, deploy-процесс и GitHub workflow.

## Что делает продукт

- Пользователь задает вопрос в одном чат-экране.
- Backend вытягивает три карты: ситуация, препятствие, совет.
- Для нового неоплаченного `client_id` один раз доступен teaser: первая карта с фото и кратким разбором.
- Пользователь подтверждает расклад или просит перетянуть карты.
- Backend генерирует текстовый разбор и изображение расклада.
- Результат возвращается в чат как `JPG` и `TXT` и сохраняется локально на устройстве.
- Доступ к платным раскладам остается server-side через YooKassa и entitlement-логику backend.

## Что сохранено от платформы

- Единый Telegram-style chat UX во Flutter.
- Локальное transcript persistence между перезапусками.
- Локальное сохранение и открытие файлов.
- `X-AppSlides-Client-Id` как постоянный идентификатор установки.
- Backend API-каркас и job-based flow.
- YooKassa billing без переноса платежной логики в Flutter.
- Отдельный `telegram_admin_bot/` для админских команд и уведомлений.
- Remote deploy на `185.171.83.116` по правилам из [OPERATIONS.md](OPERATIONS.md).

## Что заменено под таро

- Стартовые тексты, help/onboarding и кнопки chat flow.
- Product flow: вместо `presentation outline -> template -> PPTX/PDF` используется `question -> 3 cards -> reading -> JPG/TXT`.
- Backend domain logic: колода, расклад, layout изображения и prompt для интерпретации.
- Тарифные формулировки и лимиты: расклады вместо генераций презентаций.
- Admin-уведомления: события раскладов, вопросов, успешных/ошибочных генераций.
- Branding: `apptaro`.

## Структура

- `app/` - Flutter-клиент с единым чатом, billing flow, локальной историей и файловым индексом.
- `backend/` - FastAPI backend, YooKassa, AI-интеграции, tarot domain services и runtime assets.
- `telegram_admin_bot/` - отдельный Telegram bot для админов.
- `telegram_taro_bot/` - источник предметной логики, текстов, prompts, сценариев и tarot assets.
- `scripts/` - dev/deploy helper scripts.

## Ключевые backend endpoints

Имена presentation endpoints сохранены для минимального API churn:

- `POST /v1/presentations/outline` - создать черновик расклада из трех карт.
- `POST /v1/presentations/outline/revise` - перетянуть/перефокусировать расклад.
- `POST /v1/presentations/jobs` - запустить генерацию полного разбора.
- `GET /v1/presentations/jobs/{job_id}` - получить статус и результат.
- `GET /v1/presentations/jobs/{job_id}/download/image` - скачать JPG расклада.
- `GET /v1/presentations/jobs/{job_id}/download/txt` - скачать текстовый разбор.
- `GET /v1/billing/summary` и `POST /v1/billing/payments` - billing через backend.

## Локальные проверки

```powershell
python -m compileall backend/src telegram_admin_bot
python -m unittest discover -s backend/tests -v

cd app
flutter analyze
flutter test
```

Для production deploy смотри [OPERATIONS.md](OPERATIONS.md). Backend изменения должны выкатываться server-side; платежную логику нельзя переносить в мобильный клиент.
