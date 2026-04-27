# Telegram Bot UI Brief

## Source

This brief is based on the user-provided Telegram bot screenshots attached in the project discussion on `2026-04-26`.

## Product requirement

- The mobile client must feel like a Telegram bot wrapped into an APK, not like a classic multi-tab application.
- One screen only:
  - header;
  - scrollable chat history;
  - inline/reply-like buttons under bot messages;
  - bottom composer with a menu button and text input.
- The user should be able to control the product like a bot:
  - by tapping buttons;
  - by typing commands;
  - by typing free-form text such as the presentation topic or revision comments.

## Visual direction

- Telegram-like green wallpaper background.
- White bot bubbles on the left.
- Pale green user bubbles on the right.
- Soft green action buttons below bot messages.
- Compact white header with bot title and subtitle.
- Compact white composer area at the bottom.
- File outputs must appear as chat-native cards inside the feed.

## Screen references

### Reference A — main menu

Observed from the screenshot:

- white bot bubble with a short product intro;
- emoji-led value proposition lines;
- a vertical stack of green action buttons:
  - create presentation;
  - PDF → DOCX;
  - DOCX → PDF;
  - PPTX → PDF;
  - balance/subscription;
  - help.

### Reference B — help and balance

Observed from the screenshot:

- user commands such as `/help` and `/balance` appear as right-side bubbles;
- the bot answers with text-heavy formatted messages;
- subscription text is plain readable text with emoji accents and a clear CTA button below;
- support handle and offer/legal links are shown as part of the message body.

## Interaction rules to keep

- No bottom tab bar.
- No dashboard cards as the primary navigation model.
- No separate full-screen settings/history/presentation/converter pages in the active UX.
- Main flows should unfold inside the chat itself:
  - presentation topic;
  - slides count;
  - outline review;
  - design choice;
  - generation progress;
  - final files;
  - converter prompts;
  - help;
  - balance;
  - settings;
  - history.

## Business notes

- Marketplace target for MVP: `RuStore`.
- Product billing target: `YooKassa`.
- `Telegram Stars` should not be carried into the mobile app roadmap.

## Archive

- Previous dashboard-style Flutter UI is preserved in `../../old_design/flutter_ui_v1/`.
