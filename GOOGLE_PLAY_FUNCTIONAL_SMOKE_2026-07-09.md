# Google Play Functional Smoke - 2026-07-09

## Scope

Checked the Google Play adaptation of the Flutter app on Android emulator
`emulator-5554` with release APK `0.1.0+14`.

Main focus:

- language switch UX;
- main chat buttons after language switching and after transcript restore;
- backend-dependent balance screen;
- help screen;
- start of the main tarot reading flow;
- release APK/AAB build.

## Result

The language switch is implemented as a compact header icon `文`, not as a main
chat button. Tapping it opens a bottom modal with available languages:

- `English`
- `Русский`

The main chat menu keeps only product actions:

- English: `Ask a question`, `Balance`, `Help`
- Russian: `Задать вопрос`, `Баланс`, `Помощь`

Additional `0.1.0+13` verification confirms that restored legacy transcript
actions are sanitized: obsolete `Language`, `Settings`, `History`, and `Files`
buttons do not return as chat buttons after update.

Important behavior: existing chat messages are preserved in the language they
were originally generated in. After changing language from the header modal, the
app immediately appends a localized confirmation message with localized main
menu buttons, so the user does not need to reopen the menu manually.

## Evidence

Screenshots and UI dumps:

- `docs/screenshots/android/google-play/2026-07-09-language-check/home.png`
- `docs/screenshots/android/google-play/2026-07-09-language-check/language-modal.png`
- `docs/screenshots/android/google-play/2026-07-09-language-check/menu-ru.png`
- `docs/screenshots/android/google-play/2026-07-09-language-check/balance-ru.png`
- `docs/screenshots/android/google-play/2026-07-09-language-check/help-ru.png`
- `docs/screenshots/android/google-play/2026-07-09-language-check/ask-start-ru.png`
- `docs/screenshots/android/google-play/2026-07-09-language-check/question-final-ru.png`
- `docs/screenshots/android/google-play/release-0.1.0-13-home.png`
- `docs/screenshots/android/google-play/window-release-0.1.0-13-home.xml`
- `docs/screenshots/android/google-play/2026-07-09-full-smoke-v14/SUMMARY.txt`
- `docs/screenshots/android/google-play/2026-07-09-full-smoke-v14/01-home-en.png`
- `docs/screenshots/android/google-play/2026-07-09-full-smoke-v14/02-language-modal-en.png`
- `docs/screenshots/android/google-play/2026-07-09-full-smoke-v14/03-after-ru-select.png`
- `docs/screenshots/android/google-play/2026-07-09-full-smoke-v14/04-help-ru.png`
- `docs/screenshots/android/google-play/2026-07-09-full-smoke-v14/06-balance-ru.png`
- `docs/screenshots/android/google-play/2026-07-09-full-smoke-v14/09-after-force-stop-history.png`
- `docs/screenshots/android/google-play/2026-07-09-full-smoke-v14/11-after-en-select.png`

## Verified Commands

```powershell
flutter test test/features/chat/chat_screen_copy_guard_test.dart
flutter test test/domain/models/chat_transcript_entry_test.dart
flutter test test/l10n test/data/repositories/language_repository_test.dart test/data/api/appslides_api_client_test.dart
flutter analyze
flutter test
python -m pytest backend/tests
flutter build appbundle --release
flutter build apk --release
Invoke-RestMethod http://185.171.83.116:8022/v1/health
adb shell dumpsys package com.apptaro.app
adb shell uiautomator dump /data/local/tmp/window.xml
```

Observed results:

- chat language guard test: passed;
- transcript action sanitizer test: passed;
- localization and language API tests: passed;
- Flutter analyzer: no issues;
- full Flutter tests: 16 passed;
- backend tests: 67 passed;
- backend health: `status=ok`, `service=PMapptaro Backend`;
- release APK built: `app/build/app/outputs/flutter-apk/app-release.apk`;
- release AAB built: `app/build/app/outputs/bundle/release/app-release.aab`;
- installed APK reports `versionCode=14`, `versionName=0.1.0`;
- fresh UI dump contains `文`, `Ask a question`, `Balance`, and `Help`, but no main `Language` chat button;
- full smoke passed English home, language modal, Russian help, Russian balance, `/help` composer command persistence after force-stop, and switch back to English.

## Limitations

Google Play purchase and restore cannot be fully verified from a sideloaded APK.
That final check must be done from a Google Play internal/closed test track
installation with a licensed tester account.
