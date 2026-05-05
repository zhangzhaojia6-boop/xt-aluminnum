# Router State Preservation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep legacy compatibility links from losing runtime query and hash state when they redirect into `数据中枢` canonical routes.

**Architecture:** Add a small router redirect helper that preserves `to.query` and `to.hash`, then apply it only to `/review/*` and `/admin/*` compatibility routes. Lock the behavior with static contract tests because this repository already verifies router invariants through backend copy-consistency tests.

**Tech Stack:** Vue Router 4, Vite, pytest, Node test runner.

---

### Task 1: Contract Tests

**Files:**
- Modify: `backend/tests/test_mobile_entry_copy_consistency.py`

- [x] **Step 1: Write failing compatibility-route test**

Add a test that expects `/review/*` and `/admin/*` redirects to use a query/hash-preserving helper instead of string redirects.

- [x] **Step 2: Add mobile deep-link coverage**

Add a focused test for `/mobile/report/*`, `/mobile/report-advanced/*`, and `/mobile/ocr/*` query/hash preservation. This closes the audit test gap without changing mobile behavior.

- [ ] **Step 3: Run targeted red check**

Run: `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`

Expected: fail before implementation because the `/review/*` and `/admin/*` helper is missing.

Execution note: skipped red repro in this continuation because the router implementation was already present in the working tree.

### Task 2: Router Implementation

**Files:**
- Modify: `frontend/src/router/index.js`

- [x] **Step 1: Add redirect helper**

Add `preserveRouteState(path)` near existing router helpers. It should return `{ path, query: to.query, hash: to.hash }`.

- [x] **Step 2: Convert legacy routes**

Convert `/review/*` and `/admin/*` compatibility redirects from strings to `preserveRouteState(...)`. Leave mounted `/manage` routes and already-correct `/mobile/*` redirects untouched.

- [x] **Step 3: Run targeted green check**

Run: `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`

Expected: pass.

Result: `73 passed`.

### Task 3: Audit Docs and Verification

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`
- Modify as needed after full backend run: `docs/deploy/current-state.md`
- Modify as needed after full backend run: `backend/tests/test_quick_cloud_trial_docs_and_ops.py`

- [x] **Step 1: Update audit status**

Move F06 and F07 from open findings to fixed evidence after tests exist and pass.

- [x] **Step 2: Run full verification**

Run:
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`
- `node --test tests/*.test.js`
- `npm run build`
- `python -m pytest backend/tests -q`
- `git diff --check`

Results:
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q` -> `73 passed`
- `node --test tests/*.test.js` -> `0 tests, 0 failures`
- `npm --prefix frontend run build` -> pass
- `python -m pytest backend/tests -q` -> `680 passed`
- `git diff --check` -> pass

- [x] **Step 3: Commit and push**

Commit with a conventional message and push `main` to `origin/main` after verification passes.

Result: committed and pushed `305e60143e0d21f922f1139b7dfbc3e8fb292ea6` (`fix: 保留兼容路由状态`) to `origin/main`.
