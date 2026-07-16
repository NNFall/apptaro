# Google Play Billing Products

Last verified through Google Play Developer API: `2026-07-16`

Package: `com.nexwit.tarot`

## Active Catalog

| Product ID | Type | Base plan / option | Entitlement | Base price | State |
|---|---|---|---|---|---|
| `weekly_readings` | Auto-renewing subscription | `weekly-auto`, `P1W` | 15 readings for 7 days | 199 RUB | Active |
| `monthly_readings` | Auto-renewing subscription | `monthly-auto`, `P1M` | 100 readings for 30 days | 499 RUB | Active |
| `one10_readings` | Consumable one-time product | `buy` | 10 readings | 199 RUB | Active |
| `one40_readings` | Consumable one-time product | `buy` | 40 readings | 499 RUB | Active |

Google Play generated localized prices for 173 regions. New subscribers and
new-region availability are enabled. The subscription base plans and one-time
purchase options are marked as legacy compatible for the Flutter Google Play
Billing client.

## Localized Product Listings

Every product has listings for:

- English (United States): `en-US`
- Russian: `ru-RU`
- Portuguese (Brazil): `pt-BR`
- French (France): `fr-FR`
- Chinese (Simplified): `zh-CN`

The visible name is localized by Google Play. The API verification checks that
all localized titles and descriptions contain valid Unicode text rather than
encoding replacement characters.

## Application Mapping

The product IDs already match both sides of the implementation:

- Flutter: `app/lib/features/billing/google_play_billing_service.dart`
- Backend: `backend/src/domain/billing_plans.py`

Subscriptions are verified on the backend and can be restored silently through
Google Play. One-time packs are verified first and then consumed, allowing the
same pack to be purchased again.

Product IDs cannot be renamed after creation. Any future replacement product
must get a new ID and be added to both the Flutter and backend mappings before
activation.

## Remaining Live Check

Catalog creation and API configuration do not prove checkout. The final billing
smoke test must use an app installed from an internal or closed Google Play
track with a licensed tester account. Verify purchase, backend token validation,
balance update, admin notification, and subscription restore after reinstall or
app-data clearing.
