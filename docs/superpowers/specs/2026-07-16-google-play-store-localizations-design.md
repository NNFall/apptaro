# Google Play Store Localizations Design

## Scope

Extend the `Tarot Reader AI` Google Play store presence from the existing
English listing to five supported store locales:

- English (United States), `en-US`
- Russian, `ru-RU`
- Portuguese (Brazil), `pt-BR`
- French (France), `fr-FR`
- Chinese (Simplified), `zh-CN`

This change affects only Google Play store metadata and graphics. It does not
claim that Portuguese, French, or Chinese are already available inside the app;
those application localizations remain a separate implementation stage.

## Product Names

Each title must remain within Google Play's 30-character limit:

- `en-US`: `Tarot Reader AI`
- `ru-RU`: `ИИ Таро: расклады и гадание`
- `pt-BR`: `Tarô IA: Leituras de Cartas`
- `fr-FR`: `Tarot IA : Tirages de Cartes`
- `zh-CN`: `AI塔罗：在线占卜与解读`

## Copy Direction

Each locale receives a native short description and full description rather
than a literal machine translation. The copy covers:

- three-card AI-assisted tarot readings;
- relationships, work, money, future, and personal reflection;
- current situation, main obstacle, and advice/direction;
- simple explanations of cards and arcana;
- 24/7 access and local chat history where applicable;
- an explicit entertainment and self-reflection disclaimer;
- no medical, legal, financial, or psychological advice claims.

The Russian listing uses the supplied RuStore description as its source, edited
only to fit Google Play metadata limits and policy-safe wording. The other
locales preserve the same product meaning and FAQ structure without keyword
stuffing.

## Graphics

Use the supplied files as the canonical Google Play graphics for every locale:

- App icon: `C:\Users\User\Downloads\photo_2026-07-16_12-36-04.jpg`
  (`512x512`)
- Feature graphic: `C:\Users\User\Downloads\Frame 41.png`
  (`1024x500`)

The icon is uploaded as `icon` and the background as `featureGraphic`. Existing
phone screenshots remain unchanged for `en-US`. Other localized listings rely
on the approved shared visual direction until matching in-app localizations and
localized screenshots are produced.

## Publishing Flow

1. Create one Android Publisher edit.
2. Upsert all five localized listings.
3. Upload the icon and feature graphic for each locale.
4. Commit the edit without promoting or publishing a release.
5. Create a fresh read-only edit and verify titles, description lengths, and
   graphics for every locale.

Any API error cancels the edit so that Google Play does not retain a partially
updated listing.

## Success Criteria

- Five listings are returned by the Google Play Developer API.
- Every title is at most 30 characters.
- Every short description is at most 80 characters.
- Every full description is at most 4,000 characters.
- Every locale has one icon and one feature graphic.
- Existing `en-US` phone screenshots remain present.
- No release is submitted for review or promoted automatically.
