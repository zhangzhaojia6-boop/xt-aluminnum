# Admin Surface Audit Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close stale audit finding `F01` after verifying `/manage/admin` no longer renders a placeholder page.

**Architecture:** Do not change runtime UI. Use existing router and Playwright evidence to update the audit ledger from open finding to fixed evidence.

**Tech Stack:** Vue Router 4, Playwright, Vite preview, Markdown audit docs.

---

### Task 1: Verify Admin Surface Reality

**Files:**
- Read: `frontend/src/router/index.js`
- Read: `frontend/e2e/admin-surface.spec.js`
- Read: `frontend/src/views/reports/LiveDashboard.vue`

- [x] **Step 1: Confirm router target**

Verify `/manage/admin` redirects to `/manage/admin/settings`, and that `/manage/admin/settings` renders `LiveDashboard`.

Result: `frontend/src/router/index.js` maps `path: 'admin'` to `/manage/admin/settings`, and `path: 'admin/settings'` renders `LiveDashboard`.

- [x] **Step 2: Confirm E2E contract**

Verify `frontend/e2e/admin-surface.spec.js` asserts `live-dashboard` is visible and `.xt-placeholder-page` count is `0`.

Result: the first admin surface test asserts URL `/manage/admin/settings`, `live-dashboard` visibility, and `.xt-placeholder-page` count `0`.

### Task 2: Update Audit Ledger

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move F01 to fixed evidence**

Move `F01` from the open list to the fixed table with evidence from router and E2E.

- [x] **Step 2: Keep remaining findings unchanged**

Do not edit unrelated audit findings.

### Task 3: Verification and Delivery

**Files:**
- Verify: `frontend/e2e/admin-surface.spec.js`
- Verify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Run targeted E2E**

Run: `npm --prefix frontend run build`, then serve the built frontend and run `npx playwright test e2e/admin-surface.spec.js`.

Results:
- `npm --prefix frontend run build` -> pass
- `PLAYWRIGHT_BASE_URL=http://127.0.0.1:4173 npx playwright test e2e/admin-surface.spec.js` -> `9 passed`

- [x] **Step 2: Run document/static checks**

Run:
- `python -m pytest backend/tests/test_reference_command_center_spec.py backend/tests/test_mobile_entry_copy_consistency.py -q`
- `git diff --check`

Results:
- `python -m pytest backend/tests/test_reference_command_center_spec.py backend/tests/test_mobile_entry_copy_consistency.py -q` -> `106 passed`
- `git diff --check` -> pass

- [x] **Step 3: Commit and push**

Commit the audit closure and push `main` to `origin/main` after verification passes.

Result: completed with the audit closure delivery commit.
