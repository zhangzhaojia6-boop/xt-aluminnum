# Compact Desktop Query Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit finding `F12` by verifying compact clients default to the entry surface while `desktop=1` keeps management routes accessible for responsive review.

**Architecture:** Do not change `frontend/src/router/index.js`. The guard already implements `desktop=1`; add focused Playwright coverage using stored review/admin session mocks.

**Tech Stack:** Vue Router 4, Playwright, Vite preview, Markdown audit docs.

---

### Task 1: Add Compact Route E2E

**Files:**
- Modify: `frontend/e2e/login-delivery-smoke.spec.js`

- [x] **Step 1: Assert compact default route**

Set viewport `430x932`, seed a fill-capable review/admin session, visit `/manage/overview`, and assert the user lands on `/entry` with no `manage-shell`.

- [x] **Step 2: Assert desktop query exemption**

In the same compact viewport and session type, visit `/manage/overview?desktop=1`, assert the user stays on `/manage/overview?desktop=1`, and assert `manage-shell` is visible.

### Task 2: Update Audit Ledger

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move F12 to fixed evidence**

Move `F12` from the open list to the fixed table with evidence from `frontend/e2e/login-delivery-smoke.spec.js`.

- [x] **Step 2: Keep remaining findings unchanged**

Do not edit unrelated audit findings.

### Task 3: Verification and Delivery

**Files:**
- Verify: `frontend/e2e/login-delivery-smoke.spec.js`
- Verify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Run targeted E2E**

Run `npx playwright test e2e/login-delivery-smoke.spec.js` against a local Vite preview server.

Result: `PLAYWRIGHT_BASE_URL=http://127.0.0.1:4173 npx playwright test e2e/login-delivery-smoke.spec.js -g "compact manage routes default"` -> `1 passed`.

- [x] **Step 2: Run static checks**

Run:
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`
- `git diff --check`

Results:
- `npm --prefix frontend run build` -> pass
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q` -> `73 passed`
- `git diff --check` -> pass

- [x] **Step 3: Commit and push**

Commit the E2E/audit closure and push `main` to `origin/main` after verification passes.

Result: completed with the E2E/audit closure delivery commit.
