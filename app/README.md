# apptaro Flutter Client

Flutter-клиент для Google Play версии `AI Tarot Reading`. Приложение работает как один Telegram-style чат: сообщения, inline-кнопки, история, paywall и файлы остаются прямо в ленте.

## Текущий UX

- Один основной экран: `lib/features/chat/chat_screen.dart`.
- По умолчанию интерфейс запускается на английском языке.
- Русский язык сохранен как ручная локализация через меню `Language`.
- Пользователь задает вопрос таро текстом или кнопкой `Ask a question`.
- Backend возвращает teaser/paid reading, JPG/TXT artifacts и статусы задач.
- Локальная история чата сохраняет сообщения, кнопки, pending context и file cards.
- `client_id` хранится локально и отправляется в backend через headers.

## Billing

Google Play версия не открывает YooKassa checkout URL и не делает polling `/v1/billing/payments`.

Актуальный flow:

- Flutter получает тарифы из `GET /v1/billing/summary`.
- Покупка запускается через `in_app_purchase` / Google Play Billing.
- Purchase token отправляется в backend через `POST /v1/billing/google-play/verify`.
- Backend проверяет token server-side через Google Play Developer API.
- После успешной проверки backend выдает entitlement/лимит раскладов.
- При запуске приложения выполняется silent restore Google Play покупок.

Guard-тест от регресса старой оплаты:

```powershell
cd app
flutter test test/billing/google_play_billing_ui_guard_test.dart
```

## Ключевые файлы

- `lib/features/chat/chat_screen.dart` - основной чат, onboarding, tarot flow, paywall, file cards.
- `lib/features/billing/google_play_billing_service.dart` - Google Play Billing integration.
- `lib/features/billing/billing_controller.dart` - состояние подписки, покупка, silent restore.
- `lib/data/api/appslides_api_client.dart` - backend API client.
- `lib/data/repositories/chat_transcript_repository.dart` - persistent chat snapshot.
- `lib/data/repositories/saved_files_repository.dart` - локальное сохранение и открытие файлов.
- `lib/l10n/` - lightweight локализация English/Russian.
- `lib/app/app_scope.dart` - DI для клиентских сервисов.

## Runtime

Клиент фиксированно подключается к Google Play backend:

```text
http://185.171.83.116:8022
```

Package/application id:

```text
com.apptaro.app
```

Локальное переключение backend URL в пользовательском интерфейсе намеренно отключено.

## Проверки

```powershell
cd app
flutter analyze
flutter test
flutter build appbundle --release
flutter build apk --release
```

Проверка на Android Emulator:

```powershell
flutter devices
& "$env:LOCALAPPDATA\Android\sdk\platform-tools\adb.exe" install -r build\app\outputs\flutter-apk\app-release.apk
& "$env:LOCALAPPDATA\Android\sdk\platform-tools\adb.exe" shell am start -n com.apptaro.app/com.apptaro.app.MainActivity
```

Подробности по Google Play эмулятору: `../ANDROID_EMULATOR_GOOGLE_PLAY.md`.
