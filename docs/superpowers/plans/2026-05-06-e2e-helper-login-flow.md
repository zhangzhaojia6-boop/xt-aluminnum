# E2E Helper Login Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit item S10 for `frontend/e2e/helpers` by replacing helper-level direct token storage writes with a mocked password login flow.

**Architecture:** Keep API response mocks in the existing E2E helper files, but move session creation behind the real login page flow. A small shared helper mocks `/api/v1/auth/login`, fills `login-username` / `login-password`, submits `login-submit`, and lets the frontend auth store write session storage itself.

**Tech Stack:** Playwright E2E helpers, pytest static guards, Markdown audit ledger.

---

### Task 1: Add The Red Static Guard

**Files:**
- Modify: `backend/tests/test_quick_cloud_trial_docs_and_ops.py`
- Create: `docs/superpowers/plans/2026-05-06-e2e-helper-login-flow.md`

- [x] **Step 1: Add a helper auth storage guard**

Assert `frontend/e2e/helpers/review-mocks.js` and `frontend/e2e/helpers/unified-entry-mocks.js` no longer call:
- `localStorage.setItem('aluminum_bypass_token'`
- `sessionStorage.setItem('aluminum_bypass_token'`
- token-bearing `addInitScript`
- token-bearing `page.evaluate`

- [x] **Step 2: Require a mocked login helper**

Assert `frontend/e2e/helpers/mock-login.js` exists and includes:
- `**/api/v1/auth/login`
- `login-username`
- `login-password`
- `login-submit`

- [x] **Step 3: Run the red guard**

Run:

```powershell
python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_e2e_helpers_use_mocked_login_flow_instead_of_storage_token_seed -q
```

Expected: FAIL because the helpers still seed token storage directly and the shared mock-login helper does not exist.

Result: historical red completed before implementation; current guard is marked `frontend_contract` and passes when explicitly selected.

### Task 2: Move Helper Sessions Behind Login

**Files:**
- Create: `frontend/e2e/helpers/mock-login.js`
- Modify: `frontend/e2e/helpers/review-mocks.js`
- Modify: `frontend/e2e/helpers/unified-entry-mocks.js`

- [x] **Step 1: Create `loginThroughMockedPassword`**

Create a helper that:
- registers `**/api/v1/auth/login`
- returns `{ access_token, token_type: 'bearer', user, machine_info }`
- navigates to `/login`
- fills `login-username` and `login-password`
- clicks `login-submit`
- waits for an authenticated landing URL

- [x] **Step 2: Update review mocks**

Remove direct storage writes from `setupReviewSessionAndMocks`. After all API mocks are registered, call `loginThroughMockedPassword(page, { token, user })`.

- [x] **Step 3: Update unified entry mocks**

Remove direct storage writes from `setupUnifiedPerCoilEntrySession`. After all API mocks are registered, call `loginThroughMockedPassword(page, { token, user, machineContext })`.

Result: `frontend/e2e/helpers/mock-login.js` now mocks `/api/v1/auth/login`, fills the login page controls, and lets the auth store create the session; both review and unified-entry helper files call it instead of writing auth token storage directly.

### Task 3: Audit And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`
- Modify: `frontend/e2e/admin-surface.spec.js` after verification exposed stale `/manage/master` title assertions

- [x] **Step 1: Move S10 to resolved**

Add `R76` for helper login-flow hardening and remove pending `S10`.

- [x] **Step 2: Run targeted checks**

Run:

```powershell
python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py -q
npm --prefix frontend run e2e -- admin-surface.spec.js manage-shell.spec.js mobile-entry-smoke.spec.js
```

Expected: PASS.

Result:
- `python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_e2e_helpers_use_mocked_login_flow_instead_of_storage_token_seed -m frontend_contract -q` -> `1 passed`
- First `PLAYWRIGHT_BASE_URL=http://127.0.0.1:4173 npm --prefix frontend run e2e -- admin-surface.spec.js manage-shell.spec.js mobile-entry-smoke.spec.js` -> `23 passed, 2 failed`; both failures were stale `/manage/master` heading assertions expecting `主数据与模板中心` after R81 had narrowed the runtime page to `车间主数据`.
- After updating the two admin-surface assertions to `车间主数据`, the same Playwright command -> `25 passed`

- [x] **Step 3: Run full checks**

Run:

```powershell
python -m pytest backend/tests -q
npm --prefix frontend test
npm --prefix frontend run build
git diff --check
```

Expected: PASS. Existing CRLF warnings are acceptable only if `git diff --check` exits 0.

Result:
- `python -m pytest backend/tests -q --durations=10` -> `651 passed, 123 deselected, 30 warnings`
- `python -m pytest backend/tests -m frontend_contract -q` -> `123 passed, 651 deselected`
- `npm --prefix frontend test` -> `110 passed`
- `npm --prefix frontend run build` -> pass
- `git diff --check` -> pass; Git emitted only existing LF-to-CRLF working-copy warnings for the changed files.

- [x] **Step 4: Review, commit, and push**

Commit:

```powershell
git add backend/tests/test_quick_cloud_trial_docs_and_ops.py frontend/e2e/helpers/mock-login.js frontend/e2e/helpers/review-mocks.js frontend/e2e/helpers/unified-entry-mocks.js frontend/e2e/admin-surface.spec.js docs/audits/2026-05-02-cleanup-round2-test-audit.md docs/superpowers/plans/2026-05-06-e2e-helper-login-flow.md
git commit -m "test: 让 e2e helpers 走登录流"
git push
```
