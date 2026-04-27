# App

## Active UI Direction

- Current active client UI is no longer a tabbed mobile app shell.
- The app is now moving to a single-screen Telegram-style bot experience:
  - one chat feed;
  - bot and user bubbles;
  - inline/reply-like action buttons;
  - command-style input;
  - file cards inside the conversation;
  - Telegram-like green wallpaper and compact header/composer layout.
- The active chat client already has:
  - local persistent transcript restore after restart;
  - `/help`, `/balance`, `/settings`, `/history`, `/files` command-style flows;
  - local file cards with `Открыть` / `Удалить` actions directly inside the chat;
  - preserved backend-driven presentation/converter flows inside the same conversation.
- The previous dashboard-style design is archived in `../old_design/flutter_ui_v1/`.
- Visual/product notes for this redesign are stored in `../instructions/design_refs/telegram_bot_ui_brief.md`.

## Current Runtime

- Mobile/web client is now hard-wired to the remote backend:
  - `http://185.171.83.116:8010`
- Local URL switching inside the app is intentionally removed.
- The chat now drives billing from the same conversation:
  - `/balance` loads live subscription state from backend;
  - plan selection opens YooKassa checkout in test mode;
  - payment status is polled back into the chat;
  - returning to the app from YooKassa triggers an immediate payment re-check;
  - if the user was blocked on the template step, successful payment resumes presentation creation automatically;
  - generation is blocked when balance is exhausted.
- The app sends a persistent `X-AppSlides-Client-Id` header on backend requests so billing and generation limits are tied to the installed client.
- Operational workflow for `git -> push -> server deploy` is documented in `../OPERATIONS.md`.

Здесь будет Flutter-клиент `AppSlides`.

Назначение приложения:

- сценарий создания презентации;
- сценарий конвертации файлов;
- локальная история пользователя;
- локальное хранение результатов;
- подписки, paywall, восстановление покупок;
- настройки и поддержка.

Стартовая структура:

```text
app/
  lib/
    bootstrap/
    app/
    core/
    data/
    domain/
    features/
      home/
      presentation/
      converter/
      subscription/
      history/
      settings/
    shared/
  assets/
    images/
    icons/
  test/
```

На текущем шаге это уже реальный Flutter-проект с подключенным backend API, локальной историей и локальным файловым индексом для сохраненных результатов.

Обновление:

- добавлен ручной Flutter-ready scaffold:
  - `pubspec.yaml`
  - `lib/main.dart`
  - `bootstrap/`
  - `app/`
  - базовые экраны по основным сценариям
- добавлен первичный client/data layer под backend API:
  - `lib/data/api/appslides_api_client.dart`
  - `lib/data/repositories/appslides_repository.dart`
  - `lib/domain/models/...`
- добавлен `AppScope` для DI без внешнего state-management пакета:
  - `lib/app/app_scope.dart`
- экран `Presentation` больше не заглушка:
  - загружает templates
  - вызывает `outline` и `outline/revise`
  - запускает `presentation jobs`
  - показывает polling статуса и download URLs
  - сохраняет готовые `PPTX/PDF` в локальное хранилище приложения
- экран `Converter` больше не заглушка:
  - открывает системный file picker
  - запускает `conversion jobs`
  - показывает polling статуса и download URL результата
  - сохраняет готовый файл в локальное хранилище приложения
- экран `History` теперь восстанавливает и очищает локальную историю через persistent storage
  - показывает список локально сохраненных файлов
  - умеет открыть локальный файл системным приложением
  - умеет удалить локальную копию и убрать ее из индекса/истории
- `LocalHistoryRepository` больше не только in-memory:
  - восстанавливает записи при старте
  - сохраняет outline/render/conversion события локально
  - держит ограничение по числу записей
- добавлен `SavedFilesRepository`:
  - скачивает артефакты с backend download routes
  - сохраняет их в app-specific storage
  - ведет persistent-index локальных файлов
  - открывает и удаляет локальные файлы
- backend endpoint теперь зафиксирован:
  - приложение всегда использует `http://185.171.83.116:8010`
  - локальное переключение URL из `Settings` отключено
  - в `Settings` оставлена только проверка `/v1/health`
- в среде разработки установлен Flutter SDK:
  - `C:\Users\User\develop\flutter`
- `app/` уже переведен в настоящий Flutter-проект:
  - сгенерированы `android/`, `ios/`, `web/`, `windows/`
  - выполнены `flutter pub get`, `flutter analyze`, `flutter test`
  - выполнен `flutter build web`
  - выполнен `flutter build apk`
  - собран Android-артефакт `build/app/outputs/flutter-apk/app-release.apk`
- Android toolchain приведен в рабочее состояние:
  - установлен `cmdline-tools`
  - приняты Android SDK licenses
  - `flutter doctor` проходит по Android toolchain без ошибок
- текущие системные блокеры:
  - для `flutter build windows` нужен Windows Developer Mode
  - в `flutter doctor` может всплывать временный timeout по `Network resources`, это сетевой шум, не блокер для локальной разработки

Следующий практический шаг:

```bash
# отдельно подними backend
.\scripts\dev\start_backend.ps1

cd app
flutter run -d chrome
# или после запуска Android-эмулятора / подключения телефона
flutter run -d android
# или собрать installable Android APK
flutter build apk
```

Важно: `flutter run` не завершится сам по себе. Это нормальная живая dev-сессия с hot reload. Останавливать ее нужно через `q` в терминале.
