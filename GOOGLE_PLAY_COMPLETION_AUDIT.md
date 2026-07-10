# Google Play Completion Audit

Last updated: 2026-07-10

Branch: `codex/google-play-adaptation`

App version: `0.1.0+14`

Android package: `com.apptaro.app`

Backend endpoint: `http://185.171.83.116:8022`

## Overall Status

The Google Play adaptation is implemented and locally verified for the Flutter
client, backend API, localization, Google Play Billing API surface, purchase
token validation logic, local storage invariants, and Android release artifacts.

The full objective is not complete yet because three checks require external
state that is not currently satisfied:

1. The separate Google Play admin Telegram bot still needs a unique
   `ADMIN_BOT_TOKEN`; the server currently has the same admin token hash in
   `/root/PMapptaro/.env` and `/root/apptaro/.env`, so `pmapptaro_admin_bot`
   is stopped.
2. Google Play purchase and restore still need a real internal/closed test
   track smoke test from a Play Store install. A sideloaded release APK cannot
   prove the Google purchase sheet and licensed tester flow.
3. The configured service account can authenticate, but Android Publisher API
   currently returns `404 Package not found: com.apptaro.app` when listing
   subscriptions. The Play Console application/package and application-level
   service-account permissions must be confirmed before purchase validation can
   work with a real token.

## Requirement Matrix

| # | Requirement | Current status | Evidence | Remaining action |
|---|-------------|----------------|----------|------------------|
| 1 | Audit current Flutter app, backend, admin bot, and source Telegram bot behavior. | Done | `GOOGLE_PLAY_ADAPTATION_AUDIT.md`, `SOURCE_HANDOFF_RUSTORE_APPTARO.md`, `docs/superpowers/plans/2026-07-06-pmapptaro-google-play-adaptation.md` | None for local audit. |
| 2 | Configure Android Emulator for local testing without a physical phone. | Done | `ANDROID_EMULATOR_GOOGLE_PLAY.md`; device `emulator-5554` was used for release APK smoke tests. | None. |
| 3 | Prepare Google Play package, signing, AAB, versionCode, release pipeline. | Verified locally | `app/pubspec.yaml` has `0.1.0+14`; `app/android/app/build.gradle.kts` uses `com.apptaro.app`; release APK/AAB artifacts exist under `app/build/app/outputs/`. | Upload each new AAB to Play Console with a higher build number. |
| 4 | Fully translate user-facing app UI to English. | Verified locally | `app/lib/l10n/`; `flutter test`; smoke screenshots in `docs/screenshots/android/google-play/2026-07-09-language-check/`. | Continue copy review as product text changes. |
| 5 | Add localization architecture: device language detection plus manual language selection. MVP English + Russian. | Verified locally | `app/lib/l10n/app_language.dart`, `app/lib/data/repositories/language_repository.dart`, header language modal in `app/lib/features/chat/chat_screen.dart`; `test/l10n`, `test/data/repositories/language_repository_test.dart`, `test/features/chat/chat_screen_copy_guard_test.dart`, and `docs/screenshots/android/google-play/2026-07-09-full-smoke-v14/`. | Add more languages by extending `AppLanguage`, localizations, backend prompts, and tests. |
| 6 | Translate backend-generated texts, errors, prompts, and AI answers according to user language. | Verified by tests | `backend/src/core/dependencies.py` reads `X-Apptaro-Language`; `backend/src/api/presentations.py`; `backend/src/domain/presentation_prompts.py`; tests `backend/tests/test_api_language_routing.py`, `backend/tests/test_prompt_localization.py`, `backend/tests/test_generation_fallback_localization.py`, `backend/tests/test_tarot_deck_localization.py`. | Continue adding tests for new prompt surfaces. |
| 7 | Replace YooKassa billing with Google Play Billing in the Google Play version. | Verified locally | `app/lib/features/billing/google_play_billing_service.dart`; `app/lib/features/billing/billing_controller.dart`; `app/test/billing/google_play_billing_ui_guard_test.dart`; backend redirects return 410 in `backend/src/api/billing.py`; tests `backend/tests/test_google_play_api_surface.py`, `backend/tests/test_legacy_yookassa_disabled.py`. | Real Play Store billing smoke remains external. |
| 8 | Server-side validation of Google Play purchase token on backend. | Verified by tests; live API access not ready | `backend/src/integrations/google_play_gateway.py`; `backend/src/domain/billing_service.py`; tests `backend/tests/test_google_play_billing.py`, `backend/tests/test_google_play_settings.py`. The service account authenticates, but Android Publisher API currently returns `404 Package not found: com.apptaro.app`. | Confirm the exact Play Console package and grant the service account application-level access, then repeat the API probe and validate a real purchase token. |
| 9 | Silent restore after reinstall or data clear. | Verified by code/tests, external purchase pending | `BillingController.initialize()` calls `restoreGooglePlayPurchases(silent: true)`; `GooglePlayBillingService.restorePurchases()`; restore tests in `backend/tests/test_google_play_billing.py`; release checklist documents Play track restore. | Confirm from a Google Play test-track install with a licensed tester. |
| 10 | Deploy separate backend to `/root/PMapptaro` with separate data folder, SQLite DB, Docker services, and admin Telegram bot. | Partially complete | Remote read-only check: `/root/PMapptaro` exists; `/root/PMapptaro/data/pmapptaro.db` exists; `/root/PMapptaro/data/google-play-service-account.json` exists; `pmapptaro_backend` is running on `0.0.0.0:8022->8000/tcp`; `GET /v1/health` returns `PMapptaro Backend`; `docker-compose.backend.yml` defines `pmapptaro_backend` and `pmapptaro_admin_bot`. | Create a unique Telegram bot token for this stack, set it in `telegram_admin_bot/.env`, deploy full stack without `--backend-only`, verify `pmapptaro_admin_bot` stays running. |
| 11 | Do not break local chat history, stable client_id, promo codes, admin bot, tarot generation, entitlement logic. | Verified by tests and smoke | `app/lib/data/repositories/chat_transcript_repository.dart`; `app/lib/data/repositories/client_session_repository.dart`; storage migration tests; `backend/tests/test_billing_promo.py`; `backend/tests/test_admin_notifier.py`; `backend/tests/test_admin_bot_polling.py`; Android smoke screenshots show chat history and tarot flow. | Re-test after billing/admin-token changes. |
| 12 | Commit after major stages, run checks, and summarize progress. | Ongoing | Branch contains staged milestones and docs: `GOOGLE_PLAY_RELEASE_CHECKLIST.md`, `GOOGLE_PLAY_DEPLOYMENT.md`, `GOOGLE_PLAY_FUNCTIONAL_SMOKE_2026-07-09.md`; latest smoke commit records screenshots and UI dumps. | Continue this workflow for each next release/build. |

## Fresh Evidence Collected For This Audit

Commands and observations:

```powershell
git status --short --branch
```

- Current branch: `codex/google-play-adaptation`.
- Existing unrelated dirty work remains unstaged and was not modified by this audit:
  `AGENT_HANDOFF.md`, `APPSLIDES_PLAN.md`, `PRODUCT_ADAPTATION_GUIDE.md`,
  `backend/tests/test_api_smoke.py`, and older untracked screenshot folders.

```powershell
(Get-Content app/pubspec.yaml | Select-String '^version:').Line
Select-String -Path app/android/app/build.gradle.kts -Pattern 'namespace =|applicationId ='
Invoke-RestMethod http://185.171.83.116:8022/v1/health
Get-Item app/build/app/outputs/flutter-apk/app-release.apk, app/build/app/outputs/bundle/release/app-release.aab
```

- Version: `0.1.0+14`.
- Namespace and application ID: `com.apptaro.app`.
- Backend health: `{"status":"ok","service":"PMapptaro Backend","environment":"production","version":"0.1.0"}`.
- Release artifacts exist:
  - `app/build/app/outputs/flutter-apk/app-release.apk`
  - `app/build/app/outputs/bundle/release/app-release.aab`

Read-only server check:

- `/root/PMapptaro` exists.
- `/root/PMapptaro/data/pmapptaro.db` exists.
- `/root/PMapptaro/data/google-play-service-account.json` exists.
- Backend-only deploy to `/root/PMapptaro` completed on `2026-07-09`; `pmapptaro_backend` was recreated and is running on `0.0.0.0:8022->8000/tcp`.
- `pmapptaro_admin_bot` is stopped with `Exited (137)`.
- Masked token scan shows `/root/PMapptaro/.env` and `/root/apptaro/.env`
  share the same admin bot token hash.
- The backend service account obtains an authorized Google API session, but
  `GET /androidpublisher/v3/applications/com.apptaro.app/subscriptions` returns
  `404 Package not found: com.apptaro.app`.

Post-audit verification commands:

```powershell
python scripts\dev\google_play_readiness.py --local-only
python scripts\dev\google_play_readiness.py
flutter analyze
flutter test
python -m pytest backend/tests
flutter build appbundle --release
flutter build apk --release
```

Observed results:

- `python scripts\dev\google_play_readiness.py --local-only`: all local checks passed, including public `GET /v1/health`.
- `python scripts\dev\google_play_readiness.py`: local and remote checks ran; remote backend checks passed, remote admin bot checks failed because the bot container is stopped and the admin token duplicates `/root/apptaro/.env`.
- `flutter analyze`: no issues found.
- `flutter test`: 16 tests passed.
- `python -m pytest backend/tests`: 67 tests passed.
- `flutter build appbundle --release`: built `app-release.aab`.
- `flutter build apk --release`: built `app-release.apk`.
- Android emulator smoke installed release `versionCode=14` and passed English home, language modal, immediate Russian buttons after language switch, Russian help, Russian balance, chat history after force-stop, and switch back to English.

## Next Required Actions

1. Provide or create a unique Telegram bot token for the Google Play PMapptaro
   admin bot.
2. Update `telegram_admin_bot/.env` with that token.
3. Run full backend deploy to `/root/PMapptaro` without `--backend-only`.
4. Verify `pmapptaro_admin_bot` stays running and receives `/start`.
5. Confirm that the Play Console application package is exactly
   `com.apptaro.app` and grant the service account access to that application.
6. Repeat the read-only Android Publisher subscriptions probe and require HTTP
   `200` before testing purchases.
7. Upload the latest AAB to a Google Play internal/closed track.
8. Install from Google Play as a licensed tester and verify:
   - product list loads;
   - weekly/monthly subscription purchase works;
   - one-time pack purchase works and is consumed;
   - reinstall/data clear silently restores active subscription;
   - backend admin notification receives purchase/restore events.
