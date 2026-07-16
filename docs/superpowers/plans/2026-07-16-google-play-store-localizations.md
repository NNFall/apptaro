# Google Play Store Localizations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish policy-safe Google Play store metadata and approved graphics for `en-US`, `ru-RU`, `pt-BR`, `fr-FR`, and `zh-CN` without promoting a release.

**Architecture:** Store all approved copy and graphics in the repository as the source of truth. Apply every locale through one Android Publisher edit, cancel on any failure, commit only when all updates succeed, then verify with a fresh read-only edit.

**Tech Stack:** Google Play Android Publisher API v3, Python, google-auth, Markdown, PNG/JPEG assets.

---

### Task 1: Prepare Localized Store Metadata

**Files:**
- Create: `GOOGLE_PLAY_STORE_LISTINGS.md`

- [x] Write titles, short descriptions, full descriptions, and disclaimers for all five locales.
- [x] Verify title, short-description, and full-description character limits.

### Task 2: Preserve Approved Store Graphics

**Files:**
- Create: `docs/store/google-play/assets/icon.jpg`
- Create: `docs/store/google-play/assets/feature-graphic.png`

- [x] Copy the approved `512x512` icon and `1024x500` feature graphic into the repository.
- [x] Verify dimensions, format, and file readability.

### Task 3: Apply One Atomic Google Play Edit

- [x] Insert one edit for `com.nexwit.tarot`.
- [x] Upsert `en-US`, `ru-RU`, `pt-BR`, `fr-FR`, and `zh-CN` listings.
- [x] Replace each locale's icon and feature graphic.
- [x] Commit only after every request succeeds; otherwise delete the edit.

### Task 4: Verify And Record

- [x] Create a fresh read-only edit and verify all five localized listings.
- [x] Verify one icon and one feature graphic per locale.
- [x] Confirm existing English phone screenshots remain present.
- [x] Commit and push only the scoped localization files.
