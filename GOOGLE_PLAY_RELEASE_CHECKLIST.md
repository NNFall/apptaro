# Google Play Release Checklist

This checklist is for the Google Play version of PMapptaro.

## Package And Version

- Android package: `com.nexwit.tarot`
- Flutter version source: `app/pubspec.yaml`
- Current version: `0.1.0+15`
- Increase the build number after every new Google Play upload.

Google Play rejects builds with a `versionCode` that was already uploaded.

## Signing Files

Local signing files are intentionally not committed:

```text
app/android/key.properties
app/android/app/upload-keystore.jks
```

The committed template is:

```text
app/android/key.properties.example
```

If the local signing files are lost, Google Play uploads from this machine will stop working until the upload key is restored or reset in Play Console.

Release builds no longer fall back to debug signing. `app/android/key.properties` and `app/android/app/upload-keystore.jks` must exist locally before `flutter build appbundle --release`.

## Build Commands

From the project root:

```powershell
cd app
flutter pub get
flutter analyze
flutter test
flutter build appbundle --release
```

Release artifact:

```text
app/build/app/outputs/bundle/release/app-release.aab
```

Optional installable APK for device smoke tests:

```powershell
cd app
flutter build apk --release
```

APK artifact:

```text
app/build/app/outputs/flutter-apk/app-release.apk
```

## Backend Requirements

The released app is fixed to:

```text
http://185.171.83.116:8022
```

Before publishing, verify:

```powershell
Invoke-RestMethod http://185.171.83.116:8022/v1/health
```

Google Play purchases require:

```text
GOOGLE_PLAY_PACKAGE_NAME=com.nexwit.tarot
GOOGLE_PLAY_SERVICE_ACCOUNT_FILE=/data/google-play-service-account.json
```

Server-side path:

```text
/root/PMapptaro/data/google-play-service-account.json
```

## Readiness Check

Run the local release readiness check before uploading a new AAB:

```powershell
python scripts\dev\google_play_readiness.py --local-only
```

This checks version/package/backend URL, release APK/AAB artifacts, and the
public `GET /v1/health` endpoint. If you need an offline artifact-only check,
add `--skip-backend-health`.

Run the full local + server check before marking the release backend-ready.
Use environment variables for SSH credentials so secrets are not committed or
copied into docs:

```powershell
$env:PMAPPTARO_REMOTE_HOST='185.171.83.116'
$env:PMAPPTARO_REMOTE_USER='root'
$env:PMAPPTARO_REMOTE_PASSWORD='<server-password>'
python scripts\dev\google_play_readiness.py
```

The separate `pmapptaro_admin_bot` token and container were verified healthy in
the latest remote audit. Re-run the full readiness command after every backend
or server configuration change rather than relying on this recorded state.

## Play Console Upload

1. Open the app in Google Play Console.
2. Go to the selected test/production track.
3. Upload `app-release.aab`.
4. Add release notes.
5. Review warnings and send the release for review.

The service account can access the Play Console application and its monetization
catalog. The active product configuration verified through Android Publisher API
on `2026-07-16` is documented in `GOOGLE_PLAY_BILLING_PRODUCTS.md`.

The four configured product IDs are:

```text
weekly_readings
monthly_readings
one10_readings
one40_readings
```

Catalog access does not replace a real purchase-token validation test. A present
JSON file, active products, and a healthy backend are not sufficient proof of
the complete checkout flow.

Suggested release notes:

```text
Google Play build with English UI, localized tarot readings, Google Play Billing, and server-side purchase verification.
```

## Billing Smoke Test

Use a build installed from Google Play testing track, not a locally sideloaded APK.

Check:

- products load from Google Play;
- purchase sheet opens;
- backend accepts the purchase token;
- chat shows active balance/subscription;
- admin bot receives the purchase notification;
- reinstall or clear data restores an active Google Play entitlement.

Local emulator smoke already verified on `2026-07-07` with sideloaded release `0.1.0+11`:

- top-right language picker opens as a modal and switches English/Russian for new chat messages;
- `Help` and `Balance` work without `ClientException`;
- `Ask a question` reaches the backend and returns an English tarot teaser with card image;
- chat history and generated teaser survive `adb shell am force-stop com.nexwit.tarot` and app relaunch.

This local smoke does not replace the Google Play track billing test above because local sideloads cannot fully validate Play purchase sheets and tester-account purchases.

Additional local emulator smoke verified on `2026-07-09` with sideloaded release `0.1.0+12`:

- release APK installs and launches on `emulator-5554`;
- clean home screen is English-first and keeps the compact top-right language picker;
- balance screen loads from backend without `ClientException`, `YooKassa`, or payment test-mode notice;
- language picker opens as a modal with `English` and `Русский`.

Evidence files:

```text
docs/screenshots/android/google-play/release-0.1.0-12-home.png
docs/screenshots/android/google-play/release-0.1.0-12-balance.png
docs/screenshots/android/google-play/release-0.1.0-12-language-modal.png
docs/screenshots/android/google-play/window-release-0.1.0-12-home.xml
docs/screenshots/android/google-play/window-release-0.1.0-12-balance.xml
docs/screenshots/android/google-play/window-release-0.1.0-12-language-modal.xml
```

Additional local emulator smoke verified on `2026-07-09` with sideloaded release `0.1.0+13`:

- release APK installs with `versionCode=13`;
- clean home screen is English-first;
- the language switch is only the compact top-right `文` header button;
- main chat keyboard contains `Ask a question`, `Balance`, and `Help`, without a `Language` chat button;
- restored legacy chat transcript actions are sanitized so obsolete `Language`, `Settings`, `History`, and `Files` buttons do not return after update.

Evidence files:

```text
docs/screenshots/android/google-play/release-0.1.0-13-home.png
docs/screenshots/android/google-play/window-release-0.1.0-13-home.xml
```

Additional local emulator smoke verified on `2026-07-09` with sideloaded release `0.1.0+14`:

- release APK installs with `versionCode=14`, `versionName=0.1.0`;
- clean home screen is English-first;
- the language switch is only the compact top-right `文` header button;
- tapping `文` opens a modal with `Choose language`, `English`, and `Русский`;
- choosing `Русский` immediately adds a Russian confirmation message and Russian main menu buttons;
- Russian `Помощь` shows user ID plus Telegram and Max support links;
- Russian `Баланс` reaches the backend and does not show `YooKassa`, `ЮKassa`, or test-mode payment copy;
- `/help` typed through the composer is restored after `adb shell am force-stop com.nexwit.tarot` and relaunch;
- switching back to `English` immediately adds English main menu buttons.

Evidence files:

```text
docs/screenshots/android/google-play/2026-07-09-full-smoke-v14/SUMMARY.txt
docs/screenshots/android/google-play/2026-07-09-full-smoke-v14/01-home-en.png
docs/screenshots/android/google-play/2026-07-09-full-smoke-v14/02-language-modal-en.png
docs/screenshots/android/google-play/2026-07-09-full-smoke-v14/03-after-ru-select.png
docs/screenshots/android/google-play/2026-07-09-full-smoke-v14/06-balance-ru.png
docs/screenshots/android/google-play/2026-07-09-full-smoke-v14/09-after-force-stop-history.png
docs/screenshots/android/google-play/2026-07-09-full-smoke-v14/11-after-en-select.png
```

## Google Play Product Behavior

- `weekly_readings` and `monthly_readings` are subscription products and are restored silently through Google Play purchase restore.
- `one10_readings` and `one40_readings` are consumable one-time packs. They grant 10 and 40 readings respectively. The app verifies the purchase token on the backend first, then consumes the Google Play purchase so the same pack can be bought again.
- Consumed one-time packs are not discoverable through Google Play restore after app data is cleared. This is a Google Play Billing limitation for consumables without a user account.
- All four products and their purchase configurations were verified as `ACTIVE` through Google Play Developer API on `2026-07-16`; see `GOOGLE_PLAY_BILLING_PRODUCTS.md`.
