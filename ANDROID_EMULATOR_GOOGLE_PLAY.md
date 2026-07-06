# Android Emulator For Google Play Testing

Этот файл фиксирует локальный эмулятор для тестирования `PMapptaro` без физического телефона.

## Установленное состояние

- Android SDK: `C:\Users\User\AppData\Local\Android\sdk`.
- Flutter doctor: без ошибок.
- Google Play system image установлен:

```text
system-images;android-35;google_apis_playstore;x86_64
```

- AVD для Google Play:

```text
apptaro_google_play
```

- Старый AVD для обычного smoke:

```text
apptaro_smoke
```

## Зачем два эмулятора

`apptaro_smoke` использует обычный default Android image. Он подходит для UI-smoke, но не подходит для Google Play Billing.

`apptaro_google_play` использует Google Play image и содержит Play Store package `com.android.vending`. Его нужно использовать для проверки Google Play Billing, purchase restore и поведения приложения как Google Play build.

## Основные команды

Запустить Google Play emulator:

```powershell
& "$env:LOCALAPPDATA\Android\sdk\emulator\emulator.exe" -avd apptaro_google_play
```

Проверить устройства:

```powershell
& "$env:LOCALAPPDATA\Android\sdk\platform-tools\adb.exe" devices
flutter devices
```

Проверить, что Play Store установлен:

```powershell
& "$env:LOCALAPPDATA\Android\sdk\platform-tools\adb.exe" shell pm list packages com.android.vending
```

Ожидаемый вывод:

```text
package:com.android.vending
```

Установить APK вручную:

```powershell
& "$env:LOCALAPPDATA\Android\sdk\platform-tools\adb.exe" install -r app\build\app\outputs\flutter-apk\app-release.apk
```

Запустить Flutter на эмуляторе:

```powershell
cd app
flutter run -d emulator-5554
```

Сделать скриншот:

```powershell
& "$env:LOCALAPPDATA\Android\sdk\platform-tools\adb.exe" exec-out screencap -p > docs\screenshots\android\pmapptaro-emulator.png
```

## Важное ограничение

Google Play Billing нельзя полноценно проверить просто установкой локального APK, если приложение не связано с Google Play Console и тестовым треком. Для покупки через Google Play обычно нужен build из internal/closed testing track, установленный через Play Store, и тестовый аккаунт в лицензировании/тестерах.

Локальный emulator все равно полезен:

- UI;
- локализация;
- startup flow;
- история чата;
- network errors;
- deeplink smoke;
- базовая проверка, что устройство Google Play совместимое.

## Current Google Play Release Smoke

Verified on `apptaro_google_play` / `emulator-5554`:

- release APK installed from `app/build/app/outputs/flutter-apk/app-release.apk`;
- package launched as `com.apptaro.app`;
- backend health passed on `http://185.171.83.116:8022/v1/health`;
- clean startup screen is fully English;
- ask-question flow is fully English;
- screenshots saved in `docs/screenshots/android/google-play/`.

Smoke screenshots:

```text
docs/screenshots/android/google-play/home-release-clean.png
docs/screenshots/android/google-play/ask-flow-release.png
```
