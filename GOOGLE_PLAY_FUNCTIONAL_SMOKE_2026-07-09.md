# Google Play Functional Smoke - 2026-07-09

## Scope

Checked the Google Play adaptation of the Flutter app on Android emulator
`emulator-5554` with release APK `0.1.0+12`.

Main focus:

- language switch UX;
- main chat buttons after language switching;
- backend-dependent balance screen;
- help screen;
- start of the main tarot reading flow;
- release APK build.

## Result

The language switch is implemented as a compact header icon `文`, not as a main
chat button. Tapping it opens a bottom modal with available languages:

- `English`
- `Русский`

The main chat menu keeps only product actions:

- English: `Ask a question`, `Balance`, `Help`
- Russian: `Задать вопрос`, `Баланс`, `Помощь`

Important behavior: existing chat messages are preserved in the language they
were originally generated in. After changing language, newly generated messages
and buttons use the selected language.

## Evidence

Screenshots and UI dumps:

- `docs/screenshots/android/google-play/2026-07-09-language-check/home.png`
- `docs/screenshots/android/google-play/2026-07-09-language-check/language-modal.png`
- `docs/screenshots/android/google-play/2026-07-09-language-check/menu-ru.png`
- `docs/screenshots/android/google-play/2026-07-09-language-check/balance-ru.png`
- `docs/screenshots/android/google-play/2026-07-09-language-check/help-ru.png`
- `docs/screenshots/android/google-play/2026-07-09-language-check/ask-start-ru.png`
- `docs/screenshots/android/google-play/2026-07-09-language-check/question-final-ru.png`

## Verified Commands

```powershell
flutter test test/features/chat/chat_screen_copy_guard_test.dart
flutter test test/l10n test/data/repositories/language_repository_test.dart test/data/api/appslides_api_client_test.dart
flutter analyze
flutter test
python -m pytest backend/tests
flutter build apk --release
Invoke-RestMethod http://185.171.83.116:8022/v1/health
```

Observed results:

- chat language guard test: passed;
- localization and language API tests: passed;
- Flutter analyzer: no issues;
- full Flutter tests: 14 passed;
- backend tests: 52 passed;
- backend health: `status=ok`, `service=PMapptaro Backend`;
- release APK built: `app/build/app/outputs/flutter-apk/app-release.apk`.

## Limitations

Google Play purchase and restore cannot be fully verified from a sideloaded APK.
That final check must be done from a Google Play internal/closed test track
installation with a licensed tester account.
