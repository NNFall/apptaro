# Google Play Release Checklist

This checklist is for the Google Play version of PMapptaro.

## Package And Version

- Android package: `com.apptaro.app`
- Flutter version source: `app/pubspec.yaml`
- Current version: `0.1.0+7`
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
GOOGLE_PLAY_PACKAGE_NAME=com.apptaro.app
GOOGLE_PLAY_SERVICE_ACCOUNT_FILE=/data/google-play-service-account.json
```

Server-side path:

```text
/root/PMapptaro/data/google-play-service-account.json
```

## Play Console Upload

1. Open the app in Google Play Console.
2. Go to the selected test/production track.
3. Upload `app-release.aab`.
4. Add release notes.
5. Review warnings and send the release for review.

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
