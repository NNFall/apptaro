# App

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
- добавлен runtime-конфиг backend endpoint:
  - для Android emulator по умолчанию используется `http://10.0.2.2:8000`
  - endpoint можно менять прямо в `Settings`
  - есть встроенная проверка `/v1/health`
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
