# PMapptaro / AI Tarot Reading

Google Play версия мобильного AI-приложения для раскладов таро. Проект работает как единый Telegram-style чат: пользователь задает вопрос, backend вытягивает карты, генерирует разбор и возвращает результат прямо в ленту.

## Что делает продукт

- Пользователь задает вопрос в одном чат-экране.
- Backend формирует расклад из трех карт: ситуация, препятствие, совет.
- Новый unpaid `client_id` может один раз получить teaser: первая карта с кратким разбором.
- Полный расклад требует активного entitlement.
- Backend генерирует текстовый разбор и JPG-изображение расклада.
- Результат возвращается в чат как `JPG` и `TXT` и сохраняется локально на устройстве.
- История чата, inline-кнопки, pending context и file cards сохраняются локально.

## Google Play версия

- Google Play app: `Tarot Reader AI`.
- Android package: `com.nexwit.tarot`.
- Current release version: `0.1.0+16`.
- Backend: `http://185.171.83.116:8022`.
- User-facing UI по умолчанию на английском.
- Русский язык сохранен как ручная локализация.
- Billing идет через Google Play Billing.
- Purchase token проверяется server-side через `POST /v1/billing/google-play/verify`.
- YooKassa redirect billing и deeplink return в Google Play версии отключены.
- Silent restore Google Play покупок запускается при старте приложения.

## Структура

- `app/` - Flutter-клиент: чат, локализация, Google Play Billing, локальная история и файлы.
- `backend/` - FastAPI backend: tarot domain, jobs, artifacts, entitlements, promo codes, Google Play validation.
- `telegram_admin_bot/` - отдельный Telegram bot для админских команд и уведомлений.
- `telegram_taro_bot/` - исходный RuStore/Telegram tarot bot как справочник предметной логики и assets.
- `scripts/` - deploy и вспомогательные команды.

## Ключевые endpoint'ы

- `POST /v1/presentations/outline` - создать черновик расклада.
- `POST /v1/presentations/outline/revise` - обновить/перетянуть расклад.
- `POST /v1/presentations/jobs` - запустить генерацию полного разбора.
- `GET /v1/presentations/jobs/{job_id}` - получить статус и результат.
- `GET /v1/presentations/jobs/{job_id}/download/image` - скачать JPG расклада.
- `GET /v1/presentations/jobs/{job_id}/download/txt` - скачать текстовый разбор.
- `GET /v1/billing/summary` - баланс, тарифы, active/latest subscription.
- `POST /v1/billing/google-play/verify` - проверка Google Play purchase token.
- `POST /v1/billing/promo/redeem` - активация промокода.

Legacy redirect endpoints `/v1/billing/payments` и `/v1/billing/payments/{payment_id}` возвращают `410 Gone`.

## Локальные проверки

Backend:

```powershell
python -m compileall backend/src telegram_admin_bot
python -m unittest discover -s backend/tests -v
```

Flutter:

```powershell
cd app
flutter analyze
flutter test
flutter build appbundle --release
flutter build apk --release
```

Google Play emulator:

```powershell
flutter devices
& "$env:LOCALAPPDATA\Android\sdk\platform-tools\adb.exe" install -r app\build\app\outputs\flutter-apk\app-release.apk
& "$env:LOCALAPPDATA\Android\sdk\platform-tools\adb.exe" shell am start -n com.nexwit.tarot/com.nexwit.tarot.MainActivity
```

Подробные инструкции:

- `GOOGLE_PLAY_RELEASE_CHECKLIST.md`
- `GOOGLE_PLAY_DEPLOYMENT.md`
- `ANDROID_EMULATOR_GOOGLE_PLAY.md`
- `OPERATIONS.md`
