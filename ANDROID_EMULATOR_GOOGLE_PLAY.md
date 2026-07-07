# Android Emulator For Google Play Testing

This file records the local Android emulator setup for `PMapptaro`.

## Current State

- Flutter doctor: clean, no issues.
- Android SDK: `C:\Users\User\AppData\Local\Android\sdk`.
- Android Emulator: installed.
- Android licenses: accepted.
- Active Google Play AVD: `apptaro_google_play`.
- Secondary UI-smoke AVD: `apptaro_smoke`.

Verified on `2026-07-07`:

```text
flutter doctor -v
flutter emulators
flutter devices
```

`flutter devices` detected the running emulator:

```text
sdk gphone64 x86 64 - emulator-5554 - android-x64 - Android 15 (API 35)
```

The running AVD name is:

```powershell
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" shell getprop ro.boot.qemu.avd_name
```

Expected output:

```text
apptaro_google_play
```

Google Play packages are present:

```powershell
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" shell pm list packages com.android.vending
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" shell pm list packages com.google.android.gms
```

Expected output includes:

```text
package:com.android.vending
package:com.google.android.gms
```

## Launch

Start the Google Play emulator:

```powershell
cd app
flutter emulators --launch apptaro_google_play
```

Or start it directly:

```powershell
& "$env:LOCALAPPDATA\Android\Sdk\emulator\emulator.exe" -avd apptaro_google_play
```

Check devices:

```powershell
flutter devices
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" devices -l
```

## Local Smoke Test

Build a debug APK:

```powershell
cd app
flutter build apk --debug
```

Install it:

```powershell
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" install -r build\app\outputs\flutter-apk\app-debug.apk
```

Launch it:

```powershell
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" shell monkey -p com.apptaro.app -c android.intent.category.LAUNCHER 1
```

Capture a screenshot:

```powershell
New-Item -ItemType Directory -Force ..\docs\screenshots\android\google-play | Out-Null
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" shell screencap -p /sdcard/emulator-current.png
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" pull /sdcard/emulator-current.png ..\docs\screenshots\android\google-play\emulator-current.png
```

Capture a UI dump:

```powershell
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" shell uiautomator dump /sdcard/window.xml
& "$env:LOCALAPPDATA\Android\Sdk\platform-tools\adb.exe" pull /sdcard/window.xml ..\docs\screenshots\android\google-play\window-current.xml
```

## Google Play Billing Limitation

Google Play Billing cannot be fully validated by installing a locally built APK only.

For a real purchase/restore test, use:

- a build uploaded to an internal or closed testing track in Google Play Console;
- a tester account accepted into that track;
- the same tester account signed into Play Store on `apptaro_google_play`;
- active products/subscriptions in Google Play Console;
- backend Google Play Developer API validation configured with the service account.

The emulator is still useful for:

- English/Russian UI smoke;
- startup flow;
- chat history persistence;
- network error behavior;
- backend connectivity;
- screenshots for review;
- basic Google Play environment compatibility.

## Smoke Evidence

Verified on `2026-07-07` with the running `apptaro_google_play` emulator:

- current debug APK built from `app/build/app/outputs/flutter-apk/app-debug.apk`;
- an older differently signed `com.apptaro.app` package was removed from the emulator;
- current debug APK installed successfully;
- app launched with `adb shell monkey -p com.apptaro.app`;
- startup screen is in English;
- UI dump contains `AI Tarot Reading`, `Ask a question`, `Balance`, `Language`, and `Help`;
- UI dump does not show the old presentation/converter entry points on the startup screen.

Artifacts:

```text
docs/screenshots/android/google-play/emulator-debug-clean-pulled-2026-07-07.png
docs/screenshots/android/google-play/window-debug-clean-2026-07-07.xml
```

Release APK verification on `2026-07-07`:

- installed `app/build/app/outputs/flutter-apk/app-release.apk`;
- package `com.apptaro.app`, version `0.1.0+10`;
- startup screen is in English;
- UI dump contains no Cyrillic text.

Artifacts:

```text
docs/screenshots/android/google-play/release-0.1.0-10-home.png
docs/screenshots/android/google-play/window-release-0.1.0-10.xml
```
