# PMapptaro Google Play Adaptation Audit

Дата аудита: 2026-07-06.

## Git

- Рабочая папка: `D:\papka for all\work\PMapptaro`.
- Репозиторий: `https://github.com/NNFall/apptaro.git`.
- Создана рабочая ветка: `codex/google-play-adaptation`.
- Worktree отдельный не создавался, потому что рабочая папка явно задана пользователем.

На момент старта уже были незакоммиченные изменения:

- `AGENT_HANDOFF.md` modified.
- `APPSLIDES_PLAN.md` deleted.
- `PRODUCT_ADAPTATION_GUIDE.md` modified.
- `backend/tests/test_api_smoke.py` modified.
- Несколько папок `docs/screenshots/android/...` untracked.

Эти изменения не откатывались и не удалялись.

## Flutter app

Ключевые факты:

- `app/pubspec.yaml`:
  - `name: appslides`;
  - `description: AppSlides mobile client scaffold.`;
  - `version: 0.1.0+6`.
- `app/lib/app/app.dart` использует обычный `MaterialApp` без локализации.
- `app/pubspec.yaml` не содержит `flutter_localizations`, `intl`, `easy_localization` или аналогичный слой.
- Основной chat-flow находится в `app/lib/features/chat/chat_screen.dart`.
- API client находится в `app/lib/data/api/appslides_api_client.dart`.
- Backend URL зафиксирован в `app/lib/core/config/app_config.dart` как `http://185.171.83.116:8010`.
- Client headers уже отправляют оба заголовка:
  - `X-Apptaro-Client-Id`;
  - `X-AppSlides-Client-Id`.

Риски:

- В пользовательском UI много hardcoded русских строк.
- Продуктовые названия и классы местами остаются `AppSlides`.
- Для Google Play нужен HTTPS или отдельное решение по cleartext.
- Локализация должна быть добавлена как слой, а не простая замена строк.

## Android

Файлы:

- `app/android/app/build.gradle.kts`.
- `app/android/app/src/main/AndroidManifest.xml`.

Текущее состояние:

- `namespace = "com.apptaro.app"`.
- `applicationId = "com.apptaro.app"`.
- Release build сейчас подписывается debug config:

```kotlin
signingConfig = signingConfigs.getByName("debug")
```

- Manifest содержит `android:usesCleartextTraffic="true"`.
- Storage/media permissions удаляются через `tools:node="remove"`, это хорошо для Google Play.
- Есть deep links:
  - `apptaro://billing/return`;
  - legacy `appslides://billing/return`.

Риски:

- Google Play release нельзя публиковать с debug signing.
- После первой публикации package id менять нельзя.
- Для Google Play лучше убрать cleartext traffic и перевести backend на HTTPS.

## Backend

Ключевые файлы:

- `backend/src/api/billing.py`.
- `backend/src/domain/billing_service.py`.
- `backend/src/domain/billing_plans.py`.
- `backend/src/domain/presentation_prompts.py`.
- `backend/src/integrations/yookassa_gateway.py`.
- `backend/src/repositories/billing.py`.
- `backend/src/core/settings.py`.
- `backend/src/core/dependencies.py`.

Текущее состояние:

- Billing полностью завязан на YooKassa.
- Provider в платежах и подписках сейчас `yookassa`.
- Планы заданы в рублях.
- Есть recurring/autorenew YooKassa logic.
- Google Play purchase token validation отсутствует.
- Prompts и backend-generated тексты русскоязычные.
- В `presentation_prompts.py` есть legacy presentation prompt functions, оставшиеся от платформенного каркаса.

Риски:

- Google Play Billing нельзя внедрять только на клиенте.
- Backend должен проверять purchase token через Google Play Developer API.
- Нужно сохранить entitlement model, promo codes и trial teaser logic.
- Нужно не смешать новую Google Play базу с `/root/apptaro/data/appslides.db`.

## Admin bot

Ключевые файлы:

- `telegram_admin_bot/main.py`.
- `telegram_admin_bot/handlers/admin.py`.
- `telegram_admin_bot/config.py`.

Текущее состояние:

- Admin bot русскоязычный.
- Команды `sub_*`, `genpromo`, статистика и уведомления есть.
- Для Google Play можно оставить русский admin UI, если заказчик не попросит иначе.

Риски:

- Admin bot должен читать базу Google Play backend, а не RuStore backend.
- Container/service names должны отличаться от `/root/apptaro`.

## Deploy

Файлы:

- `docker-compose.backend.yml`.
- `scripts/deploy/deploy_backend_remote.py`.

Текущее состояние:

- Compose services:
  - `apptaro_backend`;
  - `apptaro_admin_bot`.
- Deploy script default remote dir: `/root/appslides`.
- Handoff старого RuStore проекта указывает remote dir `/root/apptaro`.

Для Google Play нужно:

- Новый remote dir: `/root/PMapptaro`.
- Новые service/container names.
- Отдельный port.
- Отдельный `/root/PMapptaro/data/appslides.db`.
- Google Play service account хранить в примонтированной `data/`, не в git.

## Android Emulator

Установлено/проверено:

- Flutter doctor: без ошибок.
- Android SDK: `C:\Users\User\AppData\Local\Android\sdk`.
- Android licenses accepted.
- Существующий AVD `apptaro_smoke` использует `system-images;android-35;default;x86_64`.
- Установлен Google Play образ `system-images;android-35;google_apis_playstore;x86_64`.
- Создан AVD `apptaro_google_play`.
- Эмулятор `apptaro_google_play` запущен и загрузился.
- `adb devices` видит `emulator-5554`.
- Play Store пакет найден: `com.android.vending`.
- `flutter devices` видит `sdk gphone64 x86 64`.

Команды:

```powershell
& "$env:LOCALAPPDATA\Android\sdk\emulator\emulator.exe" -avd apptaro_google_play
& "$env:LOCALAPPDATA\Android\sdk\platform-tools\adb.exe" devices
flutter devices
```

## Вывод

Переход к Google Play реалистичен, но это не косметическая правка. Нужны три больших технических слоя:

- нормальная локализация Flutter + backend prompts;
- Google Play Billing с server-side validation;
- отдельная production-инфраструктура `/root/PMapptaro`.

Начинать реализацию нужно с локализации и release-контура. Billing лучше трогать после того, как UI/backend уже говорят на английском и есть стабильный emulator smoke flow.
