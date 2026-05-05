# Manage Shell Collapse Persistence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit finding `F09` by verifying the management sidebar collapsed state survives a page reload.

**Architecture:** Keep `ManageShell.vue` unchanged because it already persists `xt-sidebar-collapsed` in `localStorage`. Strengthen the existing Playwright test to assert storage state and reload behavior.

**Tech Stack:** Vue 3, Playwright, Vite preview, Markdown audit docs.

---

### Task 1: Strengthen E2E Coverage

**Files:**
- Modify: `frontend/e2e/manage-shell.spec.js`

- [x] **Step 1: Assert collapsed storage state**

Extend `sidebar collapses and remembers state` to assert `localStorage.getItem('xt-sidebar-collapsed') === 'true'` after clicking the collapse button.

- [x] **Step 2: Assert reload persistence**

Reload the page and assert `.xt-manage--collapsed` is still visible.

- [x] **Step 3: Assert expanded storage state**

Click the collapse button again and assert `localStorage.getItem('xt-sidebar-collapsed') === 'false'`.

### Task 2: Update Audit Ledger

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move F09 to fixed evidence**

Move `F09` from the open list to the fixed table with evidence from `frontend/e2e/manage-shell.spec.js`.

- [x] **Step 2: Keep remaining findings unchanged**

Do not edit unrelated audit findings.

### Task 3: Verification and Delivery

**Files:**
- Verify: `frontend/e2e/manage-shell.spec.js`
- Verify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Run targeted E2E**

Run `npx playwright test e2e/manage-shell.spec.js` against a local Vite preview server.

Result: `PLAYWRIGHT_BASE_URL=http://127.0.0.1:4173 npx playwright test e2e/manage-shell.spec.js` -> `3 passed`.

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
