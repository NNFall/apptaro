# Tarot Trial Access Guard Design

## Problem

After the one-card free teaser is consumed, `should_show_trial_teaser()` returns
`False`. The outline API currently interprets that value as full three-card
mode without separately requiring an active reading balance. This lets an
unpaid returning client repeatedly draw three-card outlines.

## Expected behavior

- A new unpaid client may generate exactly one one-card teaser.
- A client with an active reading balance may generate and revise a three-card
  outline.
- A client whose teaser is already consumed and who has no active balance gets
  HTTP `402` before the outline service or external AI provider is called.
- Revising an outline always requires an active balance, so a consumed teaser
  cannot be expanded or repeatedly redrawn through the revision endpoint.
- The Flutter application and API response contract remain unchanged.

## Implementation

Add an access guard to `backend/src/api/presentations.py` for both
`POST /v1/presentations/outline` and
`POST /v1/presentations/outline/revise`. Reuse the existing localized reading
limit error so the current Flutter client opens its existing paywall flow.

Focused API regression tests will verify that an unpaid returning client gets
`402` and that the outline service is not invoked. Existing paid and first-time
teaser behavior remains covered by the current API suite.

## Deployment

Deploy and restart only `pmapptaro_backend`. No APK/AAB rebuild is required.
