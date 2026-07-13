# PMapptaro Google Play Package And Listing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align the Google Play build with the existing `Tarot Reader AI` Play Console application (`com.nexwit.tarot`), produce signed release artifacts, deploy the matching backend configuration, and prepare an English store listing with four verified phone screenshots.

**Architecture:** The package identifier is one release invariant shared by Android, Flutter billing requests, backend Google Play validation, deploy scripts, readiness checks, tests, and documentation. The migration changes those sources together, then verifies the built AAB and the live Android Publisher API. Store screenshots are captured from the real English Flutter Web client at a phone aspect ratio and exported as 24-bit `1080x1920` PNG files.

**Tech Stack:** Flutter/Dart, Android Gradle/Kotlin, FastAPI/Python, Google Play Developer API, Docker Compose, Playwright CLI, PowerShell, Git.

---

### Task 1: Lock The New Package In Tests

**Files:**
- Modify: `backend/tests/test_google_play_readiness.py`
- Modify: `backend/tests/test_google_play_gateway.py`
- Modify: `backend/tests/test_google_play_billing.py`

- [ ] **Step 1: Replace expected package fixtures with `com.nexwit.tarot`.**
- [ ] **Step 2: Run the focused tests and verify they fail because production configuration still uses `com.apptaro.app`.**

Run:

```powershell
python -m pytest backend/tests/test_google_play_readiness.py backend/tests/test_google_play_gateway.py backend/tests/test_google_play_billing.py
```

Expected: readiness assertions fail on the old Android/backend package.

### Task 2: Migrate Android, Flutter, Backend, And Deploy Configuration

**Files:**
- Modify: `app/android/app/build.gradle.kts`
- Move: `app/android/app/src/main/kotlin/com/apptaro/app/MainActivity.kt`
- Modify: `app/lib/core/config/app_config.dart`
- Modify: `backend/src/core/settings.py`
- Modify: `scripts/dev/google_play_readiness.py`
- Modify: `scripts/deploy/deploy_backend_remote.py`
- Modify: `backend/.env.example`
- Modify: `app/pubspec.yaml`

- [ ] **Step 1: Set every production package source to `com.nexwit.tarot`.**
- [ ] **Step 2: Move `MainActivity.kt` to `com/nexwit/tarot` and update its Kotlin package declaration.**
- [ ] **Step 3: Increase the Flutter build number from `14` to `15`.**
- [ ] **Step 4: Run focused tests and require all tests to pass.**

Run:

```powershell
python -m pytest backend/tests/test_google_play_readiness.py backend/tests/test_google_play_gateway.py backend/tests/test_google_play_billing.py
```

Expected: all focused tests pass.

### Task 3: Verify And Build Release Artifacts

**Files:**
- Verify: `app/build/app/outputs/bundle/release/app-release.aab`
- Verify: `app/build/app/outputs/flutter-apk/app-release.apk`

- [ ] **Step 1: Run `flutter analyze` and `flutter test`.**
- [ ] **Step 2: Run the complete backend test suite.**
- [ ] **Step 3: Build signed release AAB and APK.**
- [ ] **Step 4: Inspect artifact metadata and require package `com.nexwit.tarot`, version code `15`.**

### Task 4: Deploy Matching Backend Configuration

**Files:**
- Modify: server `/root/PMapptaro/.env` through the deployment script
- Preserve: server `/root/PMapptaro/data/pmapptaro.db`
- Preserve: server `/root/PMapptaro/data/google-play-service-account.json`

- [ ] **Step 1: Deploy the full stack to `/root/PMapptaro`.**
- [ ] **Step 2: Verify backend and admin-bot container health.**
- [ ] **Step 3: Probe Android Publisher purchase endpoints for `com.nexwit.tarot`.**

Expected: the API recognizes the application package; an invalid probe token fails as a missing purchase, not as `applicationNotFound`.

### Task 5: Prepare English Google Play Listing

**Files:**
- Create: `GOOGLE_PLAY_STORE_LISTING_EN.md`

- [ ] **Step 1: Write the app name, short description, full description, category, support details, privacy notes, and release notes.**
- [ ] **Step 2: Verify character limits: title at most 30, short description at most 80, full description at most 4000.**

### Task 6: Capture Four Phone Screenshots

**Files:**
- Create: `docs/store/google-play/en-US/phone/01-home.png`
- Create: `docs/store/google-play/en-US/phone/02-question-flow.png`
- Create: `docs/store/google-play/en-US/phone/03-reading.png`
- Create: `docs/store/google-play/en-US/phone/04-language-and-help.png`
- Create: `docs/store/google-play/en-US/phone/README.md`

- [ ] **Step 1: Start Flutter Web against the production backend.**
- [ ] **Step 2: Use Playwright to exercise the English home, question, reading, and support/language flows.**
- [ ] **Step 3: Capture clean 9:16 screenshots and export each as 24-bit `1080x1920` PNG.**
- [ ] **Step 4: Inspect every screenshot for correct language, readable text, no debug UI, no browser chrome, no personal data, and no distortion.**

### Task 7: Final Readiness And Git Milestone

**Files:**
- Modify: `GOOGLE_PLAY_COMPLETION_AUDIT.md`
- Modify: `GOOGLE_PLAY_RELEASE_CHECKLIST.md`
- Modify: `GOOGLE_PLAY_DEPLOYMENT.md`

- [ ] **Step 1: Run the full local and remote readiness check.**
- [ ] **Step 2: Record artifact paths, package, version, API status, screenshot paths, and remaining real Play purchase test.**
- [ ] **Step 3: Commit only scoped project changes and push `codex/google-play-adaptation`.**
