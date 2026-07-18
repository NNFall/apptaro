# ASapptaro App Store Adaptation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce an isolated, review-ready iOS edition of Tarot Reader AI with StoreKit 2 billing, authoritative Apple server verification, a separate production backend, and a signed TestFlight build.

**Architecture:** Flutter selects a platform billing service while keeping chat UI independent of store APIs. The iOS service attaches a backend-issued `appAccountToken`, forwards Apple transaction IDs to the backend, and completes purchases only after verified entitlement storage. The backend verifies Apple-signed transaction data, applies idempotent entitlement lots in one SQLite transaction, processes App Store Server Notifications V2, and runs independently under `/root/ASapptaro` behind HTTPS.

**Tech Stack:** Flutter/Dart, `in_app_purchase` StoreKit 2 implementation, iOS/Xcode/CocoaPods, FastAPI, SQLite, Apple `app-store-server-library`, Docker Compose, Nginx/Caddy HTTPS, pytest, Flutter test.

---

## File Map

- `app/lib/features/billing/store_billing_service.dart`: store-neutral purchase contract and result models.
- `app/lib/features/billing/apple_store_billing_service.dart`: StoreKit product, purchase, restore, and completion flow.
- `app/lib/features/billing/billing_controller.dart`: platform selection and UI-facing billing state.
- `app/lib/core/config/app_config.dart`: Apple endpoints, HTTPS base URL, product IDs, and distribution flags.
- `app/lib/features/chat/chat_screen.dart`: Apple-compliant paywall/restore UI and iOS promo suppression.
- `app/ios/Podfile`: CocoaPods integration and iOS deployment target.
- `app/ios/Runner.xcodeproj/project.pbxproj`: bundle identifier and version/signing-compatible project settings.
- `backend/src/domain/app_store_billing_service.py`: verified Apple event orchestration.
- `backend/src/integrations/app_store_gateway.py`: App Store Server API and signed-data verification adapter.
- `backend/src/repositories/app_store_billing.py`: atomic transaction, chain, entitlement-lot, notification, and outbox persistence.
- `backend/src/api/app_store_billing.py`: app-account-token, verify, restore, and notification endpoints.
- `backend/src/core/settings.py`: Apple credentials and expected application identity.
- `backend/src/core/dependencies.py`: Apple gateway/service dependency wiring.
- `backend/src/integrations/admin_notifier.py`: Apple billing event messages.
- `backend/requirements.txt`: official Apple server library.
- `deploy/apple/docker-compose.yml`: isolated Apple backend/admin-bot services and volumes.
- `scripts/deploy/deploy_asapptaro_remote.py`: safe deployment into `/root/ASapptaro`.
- `docs/APP_STORE_RELEASE.md`: Apple account, signing, IAP, TestFlight, review, and rollback runbook.

### Task 1: Lock Apple Identity and Native iOS Build Configuration

**Files:**
- Create: `app/ios/Podfile`
- Modify: `app/ios/Runner.xcodeproj/project.pbxproj`
- Modify: `app/pubspec.yaml`
- Modify: `app/lib/core/config/app_config.dart`
- Test: `app/test/core/config/app_config_test.dart`
- Create: `scripts/check_ios_distribution.py`
- Test: `scripts/tests/test_check_ios_distribution.py`

- [ ] **Step 1: Write failing identity/configuration guards**

```dart
test('iOS distribution accepts only an explicitly supplied HTTPS backend', () {
  expect(AppConfig.validateAppleBackendUrl('https://apple-api.example.test'), isTrue);
  expect(AppConfig.validateAppleBackendUrl('http://185.171.83.116:8022'), isFalse);
  expect(AppConfig.iosBundleId, 'com.nexwit.tarot');
});
```

```python
def test_ios_project_has_apple_identity_and_no_broad_ats_exception(tmp_path):
    findings = inspect_ios_project(PROJECT_ROOT)
    assert findings.bundle_ids == {"com.nexwit.tarot", "com.nexwit.tarot.RunnerTests"}
    assert findings.has_broad_ats_exception is False
    assert findings.has_podfile is True
```

- [ ] **Step 2: Run guards and confirm RED**

Run: `cd app; flutter test test/core/config/app_config_test.dart`

Expected: FAIL because the current endpoint is HTTP and iOS identity/configuration is incomplete.

Run: `python -m pytest scripts/tests/test_check_ios_distribution.py -q`

Expected: FAIL because bundle IDs remain `com.apptaro.app` and `Podfile` is absent.

- [ ] **Step 3: Add minimal native configuration**

Use platform-aware immutable config:

```dart
static const appleBackendBaseUrl = String.fromEnvironment('APPLE_BACKEND_BASE_URL');
static const iosBundleId = 'com.nexwit.tarot';
```

Create `Podfile` with `platform :ios, '13.0'`, `flutter_ios_podfile_setup`, the Runner target, and `flutter_install_all_ios_pods`. Update all Runner and RunnerTests bundle IDs. Increment `app/pubspec.yaml` build number above `15`. Preserve the existing Android endpoint; require the final owned HTTPS endpoint through `--dart-define=APPLE_BACKEND_BASE_URL=...` for iOS release builds rather than inventing a domain.

- [ ] **Step 4: Run configuration checks GREEN**

Run: `cd app; flutter test test/core/config/app_config_test.dart; flutter analyze`

Expected: PASS with no analyzer errors.

Run: `python -m pytest scripts/tests/test_check_ios_distribution.py -q`

Expected: PASS.

- [ ] **Step 5: Commit only Task 1 files**

```powershell
git add app/ios/Podfile app/ios/Runner.xcodeproj/project.pbxproj app/pubspec.yaml app/lib/core/config/app_config.dart app/test/core/config/app_config_test.dart scripts/check_ios_distribution.py scripts/tests/test_check_ios_distribution.py
git commit -m "build: configure iOS App Store identity"
```

### Task 2: Introduce Store-Neutral Billing Contract

**Files:**
- Create: `app/lib/features/billing/store_billing_service.dart`
- Modify: `app/lib/features/billing/google_play_billing_service.dart`
- Modify: `app/lib/features/billing/billing_controller.dart`
- Test: `app/test/features/billing/billing_controller_test.dart`

- [ ] **Step 1: Write failing controller tests**

```dart
test('controller does not restore purchases during initialization', () async {
  final store = FakeStoreBillingService();
  await BillingController(store: store).initialize();
  expect(store.restoreCalls, 0);
});

test('controller exposes a user initiated restore action', () async {
  final store = FakeStoreBillingService();
  await BillingController(store: store).restorePurchases();
  expect(store.restoreCalls, 1);
});
```

- [ ] **Step 2: Run test and confirm RED**

Run: `cd app; flutter test test/features/billing/billing_controller_test.dart`

Expected: FAIL because billing is Google-specific and automatically restores.

- [ ] **Step 3: Implement the store-neutral contract**

```dart
abstract interface class StoreBillingService {
  Stream<StoreBillingEvent> get events;
  Future<List<StoreProduct>> loadProducts();
  Future<void> buy(String productId);
  Future<void> restorePurchases();
  Future<void> dispose();
}
```

Adapt the Google service to the contract without changing Android behavior. Inject the service into `BillingController`, remove startup restore, and expose explicit restore.

- [ ] **Step 4: Run billing and existing Flutter tests GREEN**

Run: `cd app; flutter test test/features/billing/billing_controller_test.dart; flutter test`

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```powershell
git add app/lib/features/billing app/test/features/billing/billing_controller_test.dart
git commit -m "refactor: separate platform billing services"
```

### Task 3: Implement StoreKit 2 Purchase and Restore Client

**Files:**
- Create: `app/lib/features/billing/apple_store_billing_service.dart`
- Create: `app/lib/features/billing/apple_billing_api.dart`
- Modify: `app/lib/features/billing/billing_controller.dart`
- Modify: `app/lib/main.dart`
- Test: `app/test/features/billing/apple_store_billing_service_test.dart`

- [ ] **Step 1: Write failing purchase lifecycle tests**

```dart
test('verified purchase is completed only after backend acknowledgement', () async {
  await store.emitPurchased(transactionId: '200000123');
  expect(api.verifyCalls.single.transactionId, '200000123');
  expect(store.completeCalls, 1);
});

test('backend failure leaves transaction pending and reports retryable error', () async {
  api.failVerification = true;
  await store.emitPurchased(transactionId: '200000124');
  expect(store.completeCalls, 0);
  expect(events.last.retryable, isTrue);
});
```

- [ ] **Step 2: Run tests and confirm RED**

Run: `cd app; flutter test test/features/billing/apple_store_billing_service_test.dart`

Expected: FAIL because Apple service/API do not exist.

- [ ] **Step 3: Implement Apple purchase service**

Load exactly `weekly_readings`, `monthly_readings`, `one10_readings`, and `one40_readings`. Request `/v1/billing/apple/account-token` before buying, attach the returned UUID as StoreKit 2 `appAccountToken`, listen to purchase updates, send `purchaseID` to `/v1/billing/apple/verify`, and call `completePurchase` only after a successful response. Mark restored events with operation `restore`.

- [ ] **Step 4: Run Apple billing tests GREEN**

Run: `cd app; flutter test test/features/billing/apple_store_billing_service_test.dart; flutter analyze`

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

```powershell
git add app/lib/features/billing app/lib/main.dart app/test/features/billing/apple_store_billing_service_test.dart
git commit -m "feat: add StoreKit purchase and restore client"
```

### Task 4: Build Apple-Compliant Paywall and iOS Feature Guards

**Files:**
- Modify: `app/lib/features/chat/chat_screen.dart`
- Create: `app/lib/features/billing/apple_paywall_copy.dart`
- Test: `app/test/features/billing/apple_paywall_test.dart`
- Test: `app/test/features/chat/ios_distribution_guard_test.dart`

- [ ] **Step 1: Write failing UI and copy tests**

```dart
testWidgets('iOS paywall shows localized store prices and restore action', (tester) async {
  await tester.pumpWidget(buildPaywall(platform: TargetPlatform.iOS));
  expect(find.text(r'$4.99'), findsOneWidget);
  expect(find.text('Restore Purchases'), findsOneWidget);
  expect(find.textContaining('automatically renews'), findsOneWidget);
});

testWidgets('iOS distribution does not expose promo redemption', (tester) async {
  await tester.pumpWidget(buildChat(platform: TargetPlatform.iOS));
  expect(find.textContaining('/promo'), findsNothing);
});
```

- [ ] **Step 2: Run tests and confirm RED**

Run: `cd app; flutter test test/features/billing/apple_paywall_test.dart test/features/chat/ios_distribution_guard_test.dart`

Expected: FAIL because the current chat copy and buttons are Google-specific.

- [ ] **Step 3: Implement compliant UI**

Render `ProductDetails.price` and StoreKit-provided currency, renewal period, included readings, automatic-renewal/cancellation copy, tappable Privacy Policy and Terms of Use, and an explicit `Restore Purchases` button. Hide Google Play, YooKassa, and `/promo` entitlement paths on iOS while retaining Android behavior.

- [ ] **Step 4: Run UI tests and localization guard GREEN**

Run: `cd app; flutter test test/features/billing/apple_paywall_test.dart test/features/chat/ios_distribution_guard_test.dart; flutter test`

Expected: PASS.

- [ ] **Step 5: Commit Task 4**

```powershell
git add app/lib/features/chat/chat_screen.dart app/lib/features/billing/apple_paywall_copy.dart app/test/features
git commit -m "feat: add App Store compliant purchase UI"
```

### Task 5: Add Atomic Apple Billing Persistence

**Files:**
- Create: `backend/src/repositories/app_store_billing.py`
- Modify: `backend/src/repositories/storage.py`
- Test: `backend/tests/test_app_store_billing_repository.py`

- [ ] **Step 1: Write failing repository tests**

```python
def test_apply_transaction_is_idempotent_and_grants_once(repo):
    first = repo.apply_verified_transaction(subscription_transaction())
    replay = repo.apply_verified_transaction(subscription_transaction())
    assert first.granted == 15
    assert replay.granted == 0
    assert repo.remaining_readings(CLIENT_ID) == 15

def test_consumable_lots_stack(repo):
    repo.apply_verified_transaction(consumable_transaction("tx-1", 10))
    repo.apply_verified_transaction(consumable_transaction("tx-2", 40))
    assert repo.remaining_readings(CLIENT_ID) == 50
```

- [ ] **Step 2: Run tests and confirm RED**

Run: `cd backend; python -m pytest tests/test_app_store_billing_repository.py -q`

Expected: FAIL because the Apple repository and tables do not exist.

- [ ] **Step 3: Implement SQLite schema and one atomic apply operation**

Create immutable `apple_transactions`, `apple_subscription_chains`, `apple_notifications`, `entitlement_lots`, `apple_app_accounts`, and `admin_outbox` tables. Use `BEGIN IMMEDIATE`; insert the Apple transaction with a unique transaction ID; grant one lot only when insertion succeeds; store signed expiry for subscriptions; stack consumables; preserve current Android tables.

- [ ] **Step 4: Run persistence and regression tests GREEN**

Run: `cd backend; python -m pytest tests/test_app_store_billing_repository.py tests/test_google_play_billing.py -q`

Expected: PASS.

- [ ] **Step 5: Commit Task 5**

```powershell
git add backend/src/repositories/app_store_billing.py backend/src/repositories/storage.py backend/tests/test_app_store_billing_repository.py
git commit -m "feat: persist Apple entitlements atomically"
```

### Task 6: Verify Apple Transactions with the Official Server Library

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/src/integrations/app_store_gateway.py`
- Modify: `backend/src/core/settings.py`
- Test: `backend/tests/test_app_store_gateway.py`
- Test: `backend/tests/fixtures/apple/`

- [ ] **Step 1: Write failing verification tests**

```python
def test_verifies_matching_bundle_product_and_transaction(gateway, apple_fixture):
    result = gateway.get_verified_transaction(apple_fixture.transaction_id)
    assert result.bundle_id == "com.nexwit.tarot"
    assert result.product_id == "weekly_readings"

def test_rejects_wrong_bundle_id(gateway, wrong_bundle_fixture):
    with pytest.raises(AppStoreValidationError, match="bundle"):
        gateway.verify_signed_transaction(wrong_bundle_fixture)
```

- [ ] **Step 2: Run tests and confirm RED**

Run: `cd backend; python -m pytest tests/test_app_store_gateway.py -q`

Expected: FAIL because the gateway is absent.

- [ ] **Step 3: Implement official Apple verification adapter**

Pin `app-store-server-library==3.1.1`. Build `AppStoreServerAPIClient` and `SignedDataVerifier` from mounted `.p8`, key ID, issuer ID, numeric app ID, Apple root certificates, bundle ID, and environment. Query Production first and retry Sandbox only for transaction-not-found. Reject transaction mismatch, unknown product, wrong bundle/environment, revocation, or expired subscription.

- [ ] **Step 4: Run gateway tests GREEN**

Run: `cd backend; python -m pytest tests/test_app_store_gateway.py -q`

Expected: PASS without network calls in fixture tests.

- [ ] **Step 5: Commit Task 6**

```powershell
git add backend/requirements.txt backend/src/integrations/app_store_gateway.py backend/src/core/settings.py backend/tests/test_app_store_gateway.py backend/tests/fixtures/apple
git commit -m "feat: verify App Store transactions"
```

### Task 7: Expose Account Token, Purchase Verification, and Restore APIs

**Files:**
- Create: `backend/src/domain/app_store_billing_service.py`
- Create: `backend/src/api/app_store_billing.py`
- Modify: `backend/src/core/dependencies.py`
- Modify: `backend/src/main.py`
- Test: `backend/tests/test_app_store_billing_api.py`

- [ ] **Step 1: Write failing API tests**

```python
def test_account_token_is_stable_uuid_for_client(client):
    one = client.post('/v1/billing/apple/account-token', headers=client_headers()).json()
    two = client.post('/v1/billing/apple/account-token', headers=client_headers()).json()
    assert UUID(one['app_account_token'])
    assert one == two

def test_replayed_transaction_does_not_double_grant(client, gateway):
    first = client.post('/v1/billing/apple/verify', json=verify_body('tx-1'))
    replay = client.post('/v1/billing/apple/verify', json=verify_body('tx-1'))
    assert first.json()['granted'] == 15
    assert replay.json()['granted'] == 0
```

- [ ] **Step 2: Run tests and confirm RED**

Run: `cd backend; python -m pytest tests/test_app_store_billing_api.py -q`

Expected: FAIL with 404 endpoints.

- [ ] **Step 3: Implement service and endpoints**

Create stable UUID account-token mapping, verify purchase ownership, support explicit subscription restore transfer by original transaction chain, return authoritative balance and expiry, and map validation failures to safe 4xx responses without leaking Apple secrets.

- [ ] **Step 4: Run API and smoke tests GREEN**

Run: `cd backend; python -m pytest tests/test_app_store_billing_api.py tests/test_api_smoke.py -q`

Expected: PASS.

- [ ] **Step 5: Commit Task 7**

```powershell
git add backend/src/domain/app_store_billing_service.py backend/src/api/app_store_billing.py backend/src/core/dependencies.py backend/src/main.py backend/tests/test_app_store_billing_api.py
git commit -m "feat: add Apple billing API"
```

### Task 8: Process App Store Server Notifications V2

**Files:**
- Modify: `backend/src/api/app_store_billing.py`
- Modify: `backend/src/domain/app_store_billing_service.py`
- Modify: `backend/src/integrations/admin_notifier.py`
- Test: `backend/tests/test_app_store_notifications.py`
- Test: `backend/tests/test_admin_notifier.py`

- [ ] **Step 1: Write failing notification tests**

```python
def test_duplicate_notification_uuid_is_applied_once(client, signed_renewal):
    first = client.post('/v1/billing/apple/notifications', json={'signedPayload': signed_renewal})
    replay = client.post('/v1/billing/apple/notifications', json={'signedPayload': signed_renewal})
    assert first.status_code == replay.status_code == 200
    assert entitlement_lot_count('renewal-tx') == 1

def test_invalid_signature_returns_400(client):
    response = client.post('/v1/billing/apple/notifications', json={'signedPayload': 'invalid'})
    assert response.status_code == 400
```

- [ ] **Step 2: Run tests and confirm RED**

Run: `cd backend; python -m pytest tests/test_app_store_notifications.py -q`

Expected: FAIL because notification handling is absent.

- [ ] **Step 3: Implement notification verification and outbox delivery**

Verify the outer JWS and nested transaction/renewal JWS. Handle renewal, expiration, grace period, billing retry, refund, and revocation; record unknown verified types; deduplicate by notification UUID and transaction ID; return 503 only for transient internal failures. Add concise Telegram messages for purchase, restore, renewal, expiration, refund, revocation, billing retry, and validation failure.

- [ ] **Step 4: Run notification/admin tests GREEN**

Run: `cd backend; python -m pytest tests/test_app_store_notifications.py tests/test_admin_notifier.py -q`

Expected: PASS.

- [ ] **Step 5: Commit Task 8**

```powershell
git add backend/src/api/app_store_billing.py backend/src/domain/app_store_billing_service.py backend/src/integrations/admin_notifier.py backend/tests/test_app_store_notifications.py backend/tests/test_admin_notifier.py
git commit -m "feat: handle App Store billing notifications"
```

### Task 9: Add Isolated Apple Deployment and HTTPS Readiness

**Files:**
- Create: `deploy/apple/docker-compose.yml`
- Create: `deploy/apple/.env.example`
- Create: `scripts/deploy/deploy_asapptaro_remote.py`
- Create: `scripts/check_asapptaro_deployment.py`
- Test: `scripts/tests/test_asapptaro_deployment.py`
- Create: `docs/APP_STORE_RELEASE.md`

- [ ] **Step 1: Write failing isolation checks**

```python
def test_compose_uses_isolated_names_and_data():
    compose = load_compose('deploy/apple/docker-compose.yml')
    assert compose.services == {'asapptaro_backend', 'asapptaro_admin_bot'}
    assert '/root/PMapptaro' not in compose.raw
    assert '/root/ASapptaro/data' in compose.raw
```

- [ ] **Step 2: Run tests and confirm RED**

Run: `python -m pytest scripts/tests/test_asapptaro_deployment.py -q`

Expected: FAIL because the Apple deployment files do not exist.

- [ ] **Step 3: Implement safe deployment assets**

Mount `/root/ASapptaro/data`, Apple secrets, roots, and admin-bot environment. Use unique container names, port, healthcheck, restart policy, and log rotation. Make the deploy script upload only Apple branch artifacts, create a timestamped DB backup before restart, validate the resolved target begins with `/root/ASapptaro`, and verify the HTTPS health endpoint after deployment.

- [ ] **Step 4: Write the release runbook and run checks GREEN**

Document Apple Developer membership, paid-app agreement, tax/banking, App record, IAP key/issuer/key ID/app ID, bundle registration, notification URLs, Xcode signing, StoreKit Sandbox, TestFlight, review metadata, privacy/age rating, encryption, review notes, and rollback.

Run: `python -m pytest scripts/tests/test_asapptaro_deployment.py -q; python scripts/check_asapptaro_deployment.py --local-only`

Expected: PASS without contacting production.

- [ ] **Step 5: Commit Task 9**

```powershell
git add deploy/apple scripts/deploy/deploy_asapptaro_remote.py scripts/check_asapptaro_deployment.py scripts/tests/test_asapptaro_deployment.py docs/APP_STORE_RELEASE.md
git commit -m "ops: add isolated App Store deployment"
```

### Task 10: Build on Mac, Validate StoreKit Sandbox, and Upload TestFlight

**Files:**
- Create: `scripts/macos/bootstrap_ios.sh`
- Create: `scripts/macos/build_testflight.sh`
- Modify: `docs/APP_STORE_RELEASE.md`

- [ ] **Step 1: Verify Mac prerequisites over SSH**

Run:

```bash
sw_vers
xcodebuild -version
xcrun --sdk iphoneos --show-sdk-version
flutter --version
pod --version
```

Expected: supported macOS, Xcode 26 or newer, iOS 26 SDK, stable Flutter,
CocoaPods, and Python 3.11 or newer.

- [ ] **Step 2: Bootstrap and test the copied project on Mac**

Run:

```bash
git checkout codex/apple-app-store
chmod +x scripts/macos/bootstrap_ios.sh scripts/macos/build_testflight.sh
./scripts/macos/bootstrap_ios.sh
```

Expected: all commands PASS, `app/ios/Runner.xcworkspace` exists, Flutter is on
stable channel, and tracked `app/ios/Podfile.lock` is unchanged. On the first
Mac run, commit the generated lock and rerun bootstrap.

- [ ] **Step 3: Configure signing and build an IPA**

Select the Apple team for `com.nexwit.tarot` in `Runner.xcworkspace`, then run:

```bash
export APPLE_BACKEND_BASE_URL='https://api.example.com'
export APPLE_PRIVACY_POLICY_URL='https://example.com/privacy'
./scripts/macos/build_testflight.sh --build-name 1.0.0 --build-number 17
```

Expected: production URL probes PASS and exactly one signed, distribution-profile
verified `app/build/ios/ipa/*.ipa` with version `1.0.0` and build `17`.

- [ ] **Step 4: Upload and prove TestFlight purchase flows**

Upload using Xcode Organizer or Transporter. Install the processed build from TestFlight and verify all four localized products load, weekly/monthly purchase grants once, 10/40 consumables stack, explicit restore survives reinstall, cancellation/refund/renewal Sandbox notifications update the backend, and admin Telegram events arrive.

- [ ] **Step 5: Record evidence and commit scripts/runbook updates**

```powershell
git add scripts/macos docs/APP_STORE_RELEASE.md
git commit -m "docs: record TestFlight release workflow"
```

### Task 11: Final Regression, Review, Push, and Submission Gate

**Files:**
- Modify only files required by review findings.

- [ ] **Step 1: Run full local regression**

```powershell
cd app
flutter analyze
flutter test
cd ..\backend
python -m pytest -q
cd ..
python scripts/check_ios_distribution.py
python scripts/check_asapptaro_deployment.py --local-only
```

Expected: every command PASS.

- [ ] **Step 2: Review the complete Apple diff**

Run: `git diff 0d277248601e2c16e496302fc40ced6e620c01c6...HEAD --check`

Expected: no whitespace errors, no secrets, no edits to unrelated copied dirty files, no Apple code in `PMapptaro`.

- [ ] **Step 3: Push the isolated branch**

Run: `git push -u origin codex/apple-app-store`

Expected: remote branch exists and contains only intentional Apple commits.

- [ ] **Step 4: Enforce the external completion gate**

Do not mark the App Store goal complete until the signed IPA is accepted by App Store Connect, the TestFlight build launches, Sandbox purchase/restore and notifications are proven, IAP products are attached to the first version, and Apple accepts the version for App Review.
