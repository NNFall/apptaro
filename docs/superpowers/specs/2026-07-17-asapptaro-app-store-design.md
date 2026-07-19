# ASapptaro App Store Adaptation Design

Date: 2026-07-17

Branch: `codex/apple-app-store`

Workspace: `D:\papka for all\work\ASapptaro`

## Objective

Create an independent Apple App Store edition of the existing Tarot Reader AI
Flutter application. Preserve the released Google Play project in `PMapptaro`,
replace Google Play billing with Apple StoreKit for iOS, add authoritative
server-side Apple transaction handling, deploy an isolated backend, and prepare
a signed IPA for TestFlight and App Review on the rented Mac.

## Isolation

- `PMapptaro` remains the Google Play source and is not modified.
- `ASapptaro` is a complete copy, including local files and build artifacts.
- Apple work is isolated on `codex/apple-app-store` in the existing
  `NNFall/apptaro` repository.
- Existing uncommitted files copied from `PMapptaro` are preserved and are not
  included in Apple commits unless they are directly required.
- The Apple backend uses its own server directory, Docker service names, port,
  SQLite database, data directory, secrets, and admin-bot process.

## App Identity

- Product name: `Tarot Reader AI`.
- iOS bundle identifier: `com.nexwit.tarotreaderai`.
- Flutter version remains the source for iOS marketing and build versions.
- Every uploaded App Store build gets a strictly increasing build number.
- The iOS app displays Apple/App Store terminology only. Google Play,
  YooKassa, external digital-payment links, and Android-only file behavior are
  hidden from the App Store build.

## StoreKit Client Architecture

The Flutter app keeps `in_app_purchase` and uses its StoreKit 2 implementation.
An Apple-specific billing service owns product loading, purchase updates,
transaction completion, and restore. The controller selects the Apple service
on iOS and keeps platform-specific logic outside the chat UI.

Before purchase, the backend returns an Apple `appAccountToken`: a UUID mapped
to the current local client. The app attaches this UUID through the StoreKit 2
purchase parameter. For a completed or restored StoreKit transaction, the app
sends the transaction ID to the backend before calling `completePurchase`.
The backend fetches authoritative transaction data from the App Store Server API
and verifies Apple's returned JWS. Client JWS may be included as diagnostic data
but is never the sole source of authority.

The client request contains:

- transaction ID from `PurchaseDetails.purchaseID`;
- the expected operation, purchase or restore;
- whether the event came from restore.

The transaction is completed only after backend verification succeeds. This
prevents a successful Apple charge from being acknowledged before entitlement
is safely recorded.

## App Store Products

The App Store Connect products use the same logical IDs as the Google Play
edition, but they are separate Apple catalog records:

| Product ID | Apple type | Entitlement |
|---|---|---|
| `weekly_readings` | Auto-renewable subscription | 15 readings, weekly renewal |
| `monthly_readings` | Auto-renewable subscription | 100 readings, monthly renewal |
| `one10_readings` | Consumable | 10 readings |
| `one40_readings` | Consumable | 40 readings |

The two subscriptions belong to one subscription group. Consumables can be
purchased repeatedly. Apple does not restore consumed products, so their
remaining server balance is preserved by the backend rather than reconstructed
from StoreKit restore.

## Backend Verification

The backend uses Apple's official `app-store-server-library`, App Store Server
API, and Apple root certificates. It first requests transaction information in
Production and falls back to Sandbox only for Apple's transaction-not-found
response. It never trusts product ID, dates, environment, or ownership sent by
the client without verifying the signed transaction.

Verification enforces:

- valid Apple certificate chain and JWS signature;
- bundle ID `com.nexwit.tarotreaderai`;
- expected product ID and product type;
- Sandbox or Production environment according to configuration;
- no revocation and an active subscription expiration date where applicable;
- exact transaction ID match;
- expected `appAccountToken` ownership or an explicit StoreKit restore transfer;
- idempotency by Apple transaction ID.

Each event is applied inside one SQLite `BEGIN IMMEDIATE` transaction. Immutable
Apple transaction records are separate from mutable entitlement lots. The first
verified transaction creates one entitlement lot and an admin outbox record. A
replay returns the existing result without granting readings twice. Subscription
lots expire at Apple's signed `expiresDate`, not `now + plan.days`. Renewal
transactions create new lots exactly once. Consumable lots may stack and are not
silently erased by a later purchase.

A restored subscription may transfer its original transaction chain to the
current local client ID, allowing access after reinstall even when the local
installation ID changes. The previous installation must not remain a second
independent owner of the same Apple subscription.

## Server Notifications V2

An unauthenticated HTTPS endpoint receives only Apple's `signedPayload`. The
backend verifies and decodes the JWS before processing it. Notification UUIDs
and transaction IDs are stored for idempotency.

The handler updates entitlements for renewals, expiration, billing retry,
grace-period changes, revocation, refunds, renewal preference changes, and
one-time charge events. Unknown notification types are recorded and return a
successful response after signature verification so Apple does not retry a
payload that is valid but newer than the deployed code.

The admin Telegram bot receives formatted notifications for Apple purchase,
restore, renewal, expiration, refund, revocation, billing retry, and validation
errors.

## Secrets

Secrets are mounted into the backend container and never committed:

- Apple In-App Purchase private key `.p8`;
- key ID;
- issuer ID;
- numeric App Apple ID;
- bundle ID;
- Apple root certificate files;
- expected environment;
- admin bot token.

The upload App Store Connect API key may be separate from the In-App Purchase
server key. Both stay on the rented Mac or in protected server secrets.

## Deployment

The server target is `/root/ASapptaro`. The deployment creates separate names
such as `asapptaro_backend` and `asapptaro_admin_bot`, a dedicated external
port, and `/root/ASapptaro/data/asapptaro.db`. It must not mount or modify
`/root/PMapptaro` data.

The iOS client and Apple notifications use an HTTPS domain with a valid public
certificate. The current plain HTTP IP endpoint is not used by the App Store
build and no broad App Transport Security exception is added. The production
notification URL is an HTTPS reverse-proxy route to the Apple notifications
endpoint. Sandbox and production notification URLs are configured in App Store
Connect after the endpoint is deployed.

## Rented Mac Workflow

The Mac must support Xcode 26 or newer with the iOS 26 SDK. Work is performed
through SSH for setup/build commands and GUI access for Xcode signing or
Transporter when needed.

The release sequence is:

1. clone or update `codex/apple-app-store`;
2. install the matching stable Flutter SDK and CocoaPods;
3. run Flutter and backend test suites;
4. open `app/ios/Runner.xcworkspace` and select the Apple team;
5. select `com.nexwit.tarotreaderai` and enable automatic signing;
6. create the App Store Connect app and IAP catalog;
7. build with `flutter build ipa --release`;
8. validate and upload the IPA through Xcode or Transporter;
9. test purchases and restore through TestFlight Sandbox;
10. attach the first IAP products to the app version and submit together.

## Review Compliance

- All digital purchases use Apple In-App Purchase.
- The app includes a visible user-initiated Restore Purchases action for
  subscriptions. Restore is not automatically started at application launch.
- Subscription copy states the renewal period, included readings, localized
  price from StoreKit, automatic renewal, and cancellation route.
- Terms of Use and Privacy Policy are accessible before purchase.
- Proprietary promo-code redemption is unavailable in the iOS distribution
  build because it grants digital entitlement outside Apple IAP.
- App privacy answers include backend identifiers, purchase data, diagnostics,
  and AI request content actually collected by the application.
- The review account or review flow can reach the backend and complete a real
  Sandbox purchase.
- Tarot output is presented as entertainment and reflective guidance, not as
  medical, legal, financial, or guaranteed predictive advice.

## Verification

Local verification includes Flutter analyze/tests, backend tests, product-ID
guards, Apple JWS fixture tests, notification idempotency tests, and a no-Google-
copy guard for iOS surfaces. Windows cannot prove signing or StoreKit Sandbox.

External completion requires all of the following:

- unsigned iOS build succeeds on the rented Mac;
- signed IPA validates and uploads;
- TestFlight install launches;
- all four products load with localized prices;
- both subscription and consumable purchases grant exactly once;
- subscription restore survives reinstall;
- renewal/refund notification tests update backend state;
- the build and first IAP products are accepted for App Review.
