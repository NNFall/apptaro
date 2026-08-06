# Tarot Trial Access Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent unpaid returning users from drawing or revising three-card tarot outlines after their one-card teaser is consumed.

**Architecture:** Keep the Flutter contract unchanged and enforce access at the FastAPI boundary before calling the outline service. Reuse `BillingService.should_show_trial_teaser()`, `BillingService.can_start_generation()`, and the existing localized HTTP 402 error.

**Tech Stack:** Python, FastAPI, unittest/TestClient, SQLite, Docker Compose.

---

### Task 1: Add failing access-control regression tests

**Files:**
- Create: `backend/tests/test_outline_access_control.py`

- [x] Add a billing stub representing a returning unpaid client: teaser is unavailable and generation balance is unavailable.
- [x] Add a recording outline service that fails the test if `generate()` or `revise()` is called.
- [x] Assert that both `/v1/presentations/outline` and `/v1/presentations/outline/revise` return HTTP `402` with the existing English limit message.
- [x] Run `python -m unittest backend.tests.test_outline_access_control -v` and confirm both tests fail because the current endpoints return `200`.

### Task 2: Add the backend access guard

**Files:**
- Modify: `backend/src/api/presentations.py`

- [x] In `generate_outline`, calculate teaser eligibility first; when teaser is unavailable, require `can_start_generation(client_id)` before selecting three cards.
- [x] In `revise_outline`, require `can_start_generation(client_id)` before selecting three cards.
- [x] Return the existing localized HTTP `402` response before calling the outline service.
- [x] Run the focused regression test and confirm it passes.

### Task 3: Verify and deploy

**Files:**
- Modify: `APPTARO_PLAN.md`

- [x] Record the production incident and server-side fix in the project plan.
- [x] Run `python -m unittest discover -s backend/tests -v`.
- [x] Run `python -m compileall backend/src`.
- [x] Confirm `git diff -- app` is empty so no mobile rebuild is required.
- [x] Deploy the backend to `/root/PMapptaro`, restart `pmapptaro_backend`, and verify `/v1/health`.
- [x] Run a production API probe for the affected unpaid returning client and confirm HTTP `402`.
