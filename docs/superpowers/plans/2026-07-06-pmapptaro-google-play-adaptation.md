# PMapptaro Google Play Adaptation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert `PMapptaro` from the current RuStore/YooKassa Russian app into a Google Play-ready Tarot app with English-first localization, extensible language selection, Google Play Billing, server-side entitlement validation, a separate backend deployment, and emulator-based testing.

**Architecture:** Keep the existing Flutter chat app, FastAPI backend, SQLite entitlement model, admin Telegram bot, promo codes, stable `client_id`, tarot card/layout generation, and local chat history. Add a language layer across Flutter and backend, then add Google Play Billing as a separate billing provider while preserving the existing server-side entitlement repository. Deploy Google Play backend as a separate Docker Compose stack under `/root/PMapptaro`.

**Tech Stack:** Flutter 3.41.7, Dart 3.11.5, Android SDK 36.1, Android Emulator API 35 Google Play image, FastAPI/Python, SQLite, Docker Compose, Google Play Billing, Google Play Developer API, Telegram admin bot.

---

## Current Baseline

- Branch created: `codex/google-play-adaptation`.
- Working directory: `D:\papka for all\work\PMapptaro`.
- Repository: `https://github.com/NNFall/apptaro.git`.
- Android package: `com.apptaro.app`.
- Flutter version: `0.1.0+6`.
- Current backend URL: `http://185.171.83.116:8022`.
- Current billing: Google Play Billing in Flutter with backend token verification.
- Current release signing: debug signing config.
- Google Play emulator: `apptaro_google_play`, verified with `com.android.vending`.

## Files Map

- Modify `app/pubspec.yaml`: app package metadata, localization dependencies, Google Play Billing dependency, versionCode bumps.
- Modify `app/lib/app/app.dart`: add localization delegates and current locale wiring.
- Create `app/lib/l10n/app_language.dart`: supported app languages and helpers.
- Create `app/lib/l10n/app_localizations.dart`: simple typed localizations for chat/menu/billing copy.
- Create `app/lib/data/repositories/language_repository.dart`: persistent language preference.
- Modify `app/lib/app/app_scope.dart`: provide language repository/controller.
- Modify `app/lib/features/chat/chat_screen.dart`: replace user-facing Russian strings, add language button/action, pass language to backend.
- Modify `app/lib/data/api/appslides_api_client.dart`: send language headers/body fields and Google Play purchase verification requests.
- Modify `app/lib/data/repositories/appslides_repository.dart`: expose language-aware calls and billing verification.
- Create `app/lib/features/billing/google_play_billing_service.dart`: product loading, purchase, purchase stream, silent restore.
- Modify `app/lib/features/billing/billing_controller.dart`: route Google Play build purchase flow instead of YooKassa.
- Modify `backend/src/schemas/billing.py`: Google Play request/response schemas.
- Modify `backend/src/api/billing.py`: add Google Play verification endpoint.
- Create `backend/src/integrations/google_play_gateway.py`: service account auth and purchase token validation.
- Modify `backend/src/domain/billing_service.py`: add provider `google_play`, verify purchases, sync entitlement, notify admin.
- Modify `backend/src/repositories/billing.py`: store Google payment IDs/tokens idempotently.
- Modify `backend/src/domain/billing_plans.py`: add Google product IDs and English titles.
- Modify `backend/src/domain/presentation_prompts.py`: make tarot prompts language-aware.
- Modify `backend/src/api/presentations.py`: accept/request language and return English errors.
- Modify `backend/src/core/settings.py`: add Google Play settings and default locale settings.
- Modify `backend/src/core/dependencies.py`: wire Google Play gateway.
- Modify `backend/src/integrations/admin_notifier.py`: add Google Play payment/restore notifications.
- Modify `telegram_admin_bot/handlers/admin.py`: ensure stats and manual token commands work against Google Play DB.
- Modify `docker-compose.backend.yml`: distinct PM service/container names and data mounts.
- Modify `scripts/deploy/deploy_backend_remote.py`: safe default `/root/PMapptaro`, distinct stack, no accidental RuStore env overwrite.
- Modify `app/android/app/build.gradle.kts`: release signing and build config.
- Modify `app/android/app/src/main/AndroidManifest.xml`: label, cleartext, deep links, permissions.
- Create `GOOGLE_PLAY_RELEASE_CHECKLIST.md`: release commands, AAB upload, review notes.

## Task 1: Protect Branch And Baseline

**Files:**
- Modify: `GOOGLE_PLAY_ADAPTATION_AUDIT.md`
- Modify: `ANDROID_EMULATOR_GOOGLE_PLAY.md`
- Modify: `docs/superpowers/plans/2026-07-06-pmapptaro-google-play-adaptation.md`

- [x] **Step 1: Create branch**

Run:

```powershell
git switch -c codex/google-play-adaptation
```

Expected: branch `codex/google-play-adaptation`.

- [x] **Step 2: Capture existing dirty state**

Run:

```powershell
git status --short --branch
```

Expected: existing modified/untracked files are visible and not reverted.

- [x] **Step 3: Verify Android toolchain**

Run:

```powershell
flutter doctor -v
```

Expected: no Flutter/Android issues.

- [x] **Step 4: Create Google Play AVD**

Run:

```powershell
& "$env:LOCALAPPDATA\Android\sdk\cmdline-tools\latest\bin\sdkmanager.bat" "system-images;android-35;google_apis_playstore;x86_64"
if (-not (Test-Path "$env:USERPROFILE\.android\avd\apptaro_google_play.avd")) {
  'no' | & "$env:LOCALAPPDATA\Android\sdk\cmdline-tools\latest\bin\avdmanager.bat" create avd -n apptaro_google_play -k "system-images;android-35;google_apis_playstore;x86_64" -d pixel_5
}
```

Expected: `apptaro_google_play` exists.

- [x] **Step 5: Verify Google Play package in emulator**

Run:

```powershell
& "$env:LOCALAPPDATA\Android\sdk\emulator\emulator.exe" -avd apptaro_google_play
& "$env:LOCALAPPDATA\Android\sdk\platform-tools\adb.exe" shell pm list packages com.android.vending
```

Expected: `package:com.android.vending`.

## Task 2: Baseline Tests Before Product Changes

**Files:**
- Read: `backend/tests/`
- Read: `app/test/`

- [x] **Step 1: Run backend tests**

Run:

```powershell
python -m unittest discover -s backend/tests -v
```

Expected: pass or document existing failures in `GOOGLE_PLAY_ADAPTATION_AUDIT.md`.

Actual: 11 tests passed.

- [x] **Step 2: Compile backend and admin bot**

Run:

```powershell
python -m compileall backend/src telegram_admin_bot
```

Expected: compile success.

Actual: compile success.

- [x] **Step 3: Fetch Flutter dependencies**

Run:

```powershell
cd app
flutter pub get
```

Expected: dependency resolution success.

Actual: dependency resolution success.

- [x] **Step 4: Run Flutter tests and analyze**

Run:

```powershell
cd app
flutter test
flutter analyze
```

Expected: pass or document existing failures before changing behavior.

Actual: `flutter test` passed, `flutter analyze` reported no issues.

## Task 3: Flutter Localization Foundation

**Files:**
- Modify: `app/pubspec.yaml`
- Modify: `app/lib/app/app.dart`
- Modify: `app/lib/app/app_scope.dart`
- Create: `app/lib/l10n/app_language.dart`
- Create: `app/lib/l10n/app_localizations.dart`
- Create: `app/lib/data/repositories/language_repository.dart`

- [x] **Step 1: Add localization dependencies**

Add to `app/pubspec.yaml`:

```yaml
dependencies:
  flutter_localizations:
    sdk: flutter
  intl: ^0.20.2
```

Expected: `flutter pub get` succeeds.

Actual: `flutter pub get` succeeds; `flutter_localizations` and `intl` are added.

- [x] **Step 2: Create language model**

Create `app/lib/l10n/app_language.dart` with supported languages:

```dart
import 'package:flutter/widgets.dart';

enum AppLanguage {
  english('en', 'English'),
  russian('ru', 'Русский');

  const AppLanguage(this.code, this.label);

  final String code;
  final String label;

  Locale get locale => Locale(code);

  static AppLanguage fromCode(String? code) {
    final normalized = (code ?? '').toLowerCase().split('-').first;
    return AppLanguage.values.firstWhere(
      (item) => item.code == normalized,
      orElse: () => AppLanguage.english,
    );
  }
}
```

- [x] **Step 3: Create language repository**

Create `app/lib/data/repositories/language_repository.dart`:

```dart
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../l10n/app_language.dart';

class LanguageRepository extends ChangeNotifier {
  static const String _key = 'apptaro.language.v1';

  AppLanguage? _selected;

  AppLanguage? get selected => _selected;

  Future<void> restore() async {
    final prefs = await SharedPreferences.getInstance();
    _selected = AppLanguage.fromCode(prefs.getString(_key));
    notifyListeners();
  }

  Future<void> setLanguage(AppLanguage language) async {
    _selected = language;
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_key, language.code);
    notifyListeners();
  }
}
```

- [x] **Step 4: Wire MaterialApp locale**

Modify `app/lib/app/app.dart` to use:

```dart
localizationsDelegates: const [
  AppLocalizations.delegate,
  GlobalMaterialLocalizations.delegate,
  GlobalCupertinoLocalizations.delegate,
  GlobalWidgetsLocalizations.delegate,
],
supportedLocales: AppLanguage.values.map((item) => item.locale).toList(),
```

Expected: app can rebuild when selected language changes.

Actual: language foundation tests pass, full `flutter test` passes, and `flutter analyze` reports no issues.

## Task 4: Translate Chat UI And User Messages

**Files:**
- Modify: `app/lib/features/chat/chat_screen.dart`
- Modify: `app/lib/features/home/home_screen.dart`
- Modify: `app/lib/features/settings/settings_screen.dart`
- Modify: `app/lib/features/subscription/subscription_screen.dart`
- Modify: `app/lib/data/repositories/backend_config_repository.dart`

- [x] **Step 1: Inventory remaining Russian strings**

Run:

```powershell
rg -n "[А-Яа-яЁё]" app/lib app/android
```

Expected: list of strings to translate.

Actual: `rg -n "[А-Яа-яЁё]" app/lib app/android` used to scope remaining UI/backend-facing strings.

- [x] **Step 2: Replace chat start menu copy**

Use English product copy:

```text
🔮 AI Tarot Reading
Ask a question and get a clear three-card reading in minutes.

✨ One free card for new users
🃏 Full three-card spread with subscription
💬 Follow-up questions in the same chat

Choose an option below 👇
```

- [x] **Step 3: Replace key buttons**

Use these English labels:

```text
🔮 Ask a question
💳 Balance
? Help
🏠 Main menu
🔁 Try again
✅ Continue
⬅️ Back
```

- [x] **Step 4: Add language switch action**

Add a visible compact action in chat header or menu:

```text
🌐 Language
English
Русский
```

Expected: selected language is saved locally and survives app restart.

Actual: chat menu includes `Language`, `set_language` is restorable from persisted chat actions, and selected language is stored in `LanguageRepository`.

- [x] **Step 5: Run UI string scan again**

Run:

```powershell
rg -n "[А-Яа-яЁё]" app/lib app/android
```

Expected: only Russian localization values and admin/dev-only strings remain.

Actual: legacy technical screens (`presentation`, `converter`, `history`, `home`, `settings`, `subscription`) now use English user-facing copy. The scan still finds Russian strings only in explicit Russian localization branches (`ru:` / `isRussian`) and language labels.

## Task 5: Backend Language-Aware Requests

**Files:**
- Modify: `app/lib/data/api/appslides_api_client.dart`
- Modify: `app/lib/data/repositories/appslides_repository.dart`
- Modify: `backend/src/core/dependencies.py`
- Modify: `backend/src/api/presentations.py`
- Modify: `backend/src/schemas/presentation.py`

- [x] **Step 1: Send language in client headers**

Add request header:

```dart
'X-Apptaro-Language': currentLanguage.code,
```

Expected: every backend request can identify the language.

- [x] **Step 2: Add backend dependency for language**

Add dependency in `backend/src/core/dependencies.py`:

```python
def get_request_language(x_apptaro_language: str | None = Header(default=None, alias='X-Apptaro-Language')) -> str:
    value = (x_apptaro_language or 'en').strip().lower().split('-')[0]
    return value if value in {'en', 'ru'} else 'en'
```

- [x] **Step 3: Pass language into presentation flow**

Modify outline/render endpoints to pass `language` into prompt generation and service calls.

Expected: backend can generate English or Russian responses from the same API.

Actual: Flutter sends `X-Apptaro-Language`; backend resolves it through `get_request_language`; outline/render/text-generation calls receive the resolved language.

## Task 6: Backend Prompt Localization

**Files:**
- Modify: `backend/src/domain/presentation_prompts.py`
- Test: `backend/tests/test_prompt_localization.py`

- [x] **Step 1: Add tests for English prompts**

Create `backend/tests/test_prompt_localization.py`:

```python
import unittest

from src.domain.presentation_prompts import tarot_reading_prompt


class PromptLocalizationTests(unittest.TestCase):
    def test_english_prompt_requires_english_answer(self):
        prompt = tarot_reading_prompt(
            'Will my career improve?',
            '1) The Magician, upright',
            mode='teaser',
            language='en',
        )
        self.assertIn('Answer only in English', prompt)
        self.assertIn('Will my career improve?', prompt)

    def test_russian_prompt_remains_available(self):
        prompt = tarot_reading_prompt(
            'Что с работой?',
            '1) Маг, прямое положение',
            mode='teaser',
            language='ru',
        )
        self.assertIn('Отвечай только на русском языке', prompt)
```

- [x] **Step 2: Update prompt signatures**

Change public prompt functions to accept:

```python
language: str = 'en'
```

Expected: old callers still work, new callers can request English.

- [x] **Step 3: Implement English prompt copy**

Use core instruction:

```text
You are an experienced tarot reader. Answer only in English. Return the answer in Telegram legacy Markdown. Do not use HTML tags or markdown headings. Use only the cards and orientations provided by the user. Do not replace cards, add new cards, or change orientation.
```

- [x] **Step 4: Run prompt tests**

Run:

```powershell
python -m unittest backend.tests.test_prompt_localization -v
```

Expected: pass.

Actual: covered by `python -m unittest discover -s backend/tests -v`.

## Task 7: Google Play Billing Client

**Files:**
- Modify: `app/pubspec.yaml`
- Create: `app/lib/features/billing/google_play_billing_service.dart`
- Modify: `app/lib/features/billing/billing_controller.dart`
- Modify: `app/lib/features/chat/chat_screen.dart`
- Test: `app/test/google_play_billing_service_test.dart`

- [x] **Step 1: Add billing dependency**

Add:

```yaml
dependencies:
  in_app_purchase: ^3.3.0
```

- [x] **Step 2: Define product IDs**

Use default Google Play products:

```text
weekly_readings
monthly_readings
one10_readings
one40_readings
```

Expected: backend maps these to existing plan keys `week`, `month`, `one10`, `one40`.

- [x] **Step 3: Implement purchase stream**

Google Play service must:

- load products;
- start purchase;
- listen to purchase stream;
- send purchased/restored token to backend;
- complete purchase only after backend accepts or after safe failure handling;
- silently restore owned purchases when user opens billing or taps a tariff.

Actual: implemented in `app/lib/features/billing/google_play_billing_service.dart`; `BillingController` routes checkout through Google Play and silently restores purchases on initialization.

## Task 8: Google Play Billing Backend

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/src/integrations/google_play_gateway.py`
- Modify: `backend/src/core/settings.py`
- Modify: `backend/src/core/dependencies.py`
- Modify: `backend/src/schemas/billing.py`
- Modify: `backend/src/api/billing.py`
- Modify: `backend/src/domain/billing_service.py`
- Modify: `backend/src/repositories/billing.py`
- Test: `backend/tests/test_google_play_billing.py`

- [x] **Step 1: Add Google auth dependency**

Add to `backend/requirements.txt`:

```text
google-auth>=2.35.0
requests>=2.32.0
```

- [x] **Step 2: Add settings**

Add settings:

```python
google_play_package_name: str
google_play_service_account_file: str
google_play_service_account_json: str
google_play_test_mode: bool
```

- [x] **Step 3: Add verify endpoint**

Endpoint:

```text
POST /v1/billing/google-play/verify
```

Request fields:

```json
{
  "product_id": "weekly_readings",
  "purchase_token": "...",
  "package_name": "com.apptaro.app",
  "restored": false
}
```

Expected: response returns updated `BillingSummaryResponse`.

- [x] **Step 4: Make verification idempotent**

Same token sent twice must not double-grant readings.

- [x] **Step 5: Add tests**

Test cases:

- valid subscription grants entitlement;
- restored valid subscription grants entitlement and sends restore notification;
- invalid token returns 400/503 without granting;
- repeated token does not double grant.

Actual: `backend/tests/test_google_play_billing.py` covers valid purchase, failed purchase without entitlement, repeated token, depleted repeated token, and restore to a new local client.

## Task 9: Separate PM Backend Deployment

**Files:**
- Modify: `docker-compose.backend.yml`
- Modify: `scripts/deploy/deploy_backend_remote.py`
- Modify: `backend/.env.example`
- Modify: `telegram_admin_bot/.env.example`
- Create: `GOOGLE_PLAY_DEPLOYMENT.md`

- [x] **Step 1: Rename services for PM**

Use names:

```yaml
services:
  pmapptaro_backend:
  pmapptaro_admin_bot:
```

Container names:

```text
pmapptaro_backend
pmapptaro_admin_bot
```

- [x] **Step 2: Set remote dir default**

Default deploy dir for this branch:

```text
/root/PMapptaro
```

- [x] **Step 3: Use separate port**

Default host port:

```text
8022
```

If port is occupied, inspect server before changing.

- [x] **Step 4: Add Google Play service account mount**

Store service account on server:

```text
/root/PMapptaro/data/google-play-service-account.json
```

Container path:

```text
/data/google-play-service-account.json
```

## Task 10: Android Release Pipeline

**Files:**
- Modify: `app/android/app/build.gradle.kts`
- Modify: `app/.gitignore` if needed
- Create: `app/android/key.properties.example`
- Create: `GOOGLE_PLAY_RELEASE_CHECKLIST.md`

- [ ] **Step 1: Add release signing config**

Gradle should read `key.properties`:

```kotlin
val keystoreProperties = java.util.Properties()
val keystorePropertiesFile = rootProject.file("key.properties")
if (keystorePropertiesFile.exists()) {
    keystoreProperties.load(java.io.FileInputStream(keystorePropertiesFile))
}
```

- [ ] **Step 2: Keep secrets ignored**

Ensure ignored:

```text
app/android/key.properties
app/android/app/upload-keystore.jks
*.jks
*.keystore
```

- [ ] **Step 3: Build AAB**

Run:

```powershell
cd app
flutter build appbundle --release
```

Expected output:

```text
app/build/app/outputs/bundle/release/app-release.aab
```

## Task 11: Emulator Smoke And Screenshots

**Files:**
- Create: `docs/screenshots/android/google-play/`
- Modify: `ANDROID_EMULATOR_GOOGLE_PLAY.md`

- [ ] **Step 1: Run app on emulator**

Run:

```powershell
cd app
flutter run -d emulator-5554
```

Expected: app starts on `apptaro_google_play`.

- [ ] **Step 2: Verify English UI**

Check:

- title;
- start message;
- question prompt;
- billing menu;
- help;
- language switch.

- [ ] **Step 3: Capture screenshots**

Run:

```powershell
& "$env:LOCALAPPDATA\Android\sdk\platform-tools\adb.exe" exec-out screencap -p > docs\screenshots\android\google-play\home.png
```

Expected: screenshots saved for release review.

## Task 12: Final Verification Before Google Play Upload

**Files:**
- Modify: `GOOGLE_PLAY_RELEASE_CHECKLIST.md`

- [ ] **Step 1: Run all local checks**

Run:

```powershell
python -m unittest discover -s backend/tests -v
python -m compileall backend/src telegram_admin_bot
cd app
flutter pub get
flutter analyze
flutter test
flutter build appbundle --release
```

Expected: all pass.

- [ ] **Step 2: Verify no user-facing Russian in English mode**

Run:

```powershell
rg -n "[А-Яа-яЁё]" app/lib backend/src/domain backend/src/api
```

Expected: only Russian localization values, admin-only text, or Russian language branch prompts remain.

- [ ] **Step 3: Verify backend health**

Run:

```powershell
Invoke-RestMethod http://185.171.83.116:8022/v1/health
```

Expected:

```json
{"status":"ok"}
```

- [ ] **Step 4: Verify Google Play purchase on test track**

Use a Google Play internal/closed testing build installed from Play Store.

Expected:

- purchase opens Google Play billing sheet;
- backend receives token;
- entitlement appears in billing summary;
- admin bot receives payment notification;
- reinstall/clear data can restore entitlement silently.

## Execution Order

1. Finish Task 2 baseline tests.
2. Implement Tasks 3-6 localization first.
3. Run emulator smoke for English UI.
4. Implement Tasks 7-8 Google Play Billing.
5. Implement Task 9 separate backend deploy.
6. Implement Task 10 release signing/AAB.
7. Run Tasks 11-12 verification.

## Self-Review

- Spec coverage: all user requirements are mapped to tasks.
- Placeholder scan: no `TBD`/`TODO` implementation placeholders are used.
- Type consistency: language codes use `en` and `ru`; billing plan keys stay `week`, `month`, `one10`, `one40`; Google product IDs are mapped separately.
