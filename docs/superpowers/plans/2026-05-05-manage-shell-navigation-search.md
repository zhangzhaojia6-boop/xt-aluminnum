# Manage Shell Navigation Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit finding `F10` by adding E2E coverage for the management drawer navigation, search overlay, and keyword filtering.

**Architecture:** Do not change `ManageShell.vue`. The drawer and search overlay already exist; strengthen `frontend/e2e/manage-shell.spec.js` to lock current behavior.

**Tech Stack:** Vue 3, Vue Router, Playwright, Vite preview, Markdown audit docs.

---

### Task 1: Add Drawer Navigation E2E

**Files:**
- Modify: `frontend/e2e/manage-shell.spec.js`

- [x] **Step 1: Open mobile drawer**

Set a mobile viewport, open `/manage/overview`, click the `打开导航` button, and assert the drawer nav is visible.

- [x] **Step 2: Navigate from drawer**

Click the drawer item for `经营效益`, assert URL `/manage/factory/cost`, and assert the drawer closes.

Execution note: used `1000px` width because it exercises the drawer breakpoint while avoiding the compact-client guard that intentionally routes small fill-capable users to `/entry`.

### Task 2: Add Search Overlay E2E

**Files:**
- Modify: `frontend/e2e/manage-shell.spec.js`

- [x] **Step 1: Open search from keyboard**

Press `Control+K` and assert the search dialog appears.

- [x] **Step 2: Filter by keyword**

Fill `质量` in the search input, assert `质量` remains visible and unrelated items like `经营效益` are hidden.

- [x] **Step 3: Navigate from search result**

Click the filtered result, assert URL `/manage/quality`, and assert the search dialog closes.

### Task 3: Update Audit Ledger

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move F10 to fixed evidence**

Move `F10` from the open list to the fixed table with evidence from `frontend/e2e/manage-shell.spec.js`.

- [x] **Step 2: Keep remaining findings unchanged**

Do not edit unrelated audit findings.

### Task 4: Verification and Delivery

**Files:**
- Verify: `frontend/e2e/manage-shell.spec.js`
- Verify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Run targeted E2E**

Run `npx playwright test e2e/manage-shell.spec.js` against a local Vite preview server.

Result: `PLAYWRIGHT_BASE_URL=http://127.0.0.1:4173 npx playwright test e2e/manage-shell.spec.js` -> `5 passed`.

- [x] **Step 2: Run static checks**

Run:
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`
- `git diff --check`

Results:
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q` -> `73 passed`
- `git diff --check` -> pass

- [x] **Step 3: Commit and push**

Commit the E2E/audit closure and push `main` to `origin/main` after verification passes.

Result: completed with the E2E/audit closure delivery commit.
