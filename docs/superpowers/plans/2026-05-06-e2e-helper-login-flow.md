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

- [ ] **Step 1: Add a helper auth storage guard**

Assert `frontend/e2e/helpers/review-mocks.js` and `frontend/e2e/helpers/unified-entry-mocks.js` no longer call:
- `localStorage.setItem('aluminum_bypass_token'`
- `sessionStorage.setItem('aluminum_bypass_token'`
- token-bearing `addInitScript`
- token-bearing `page.evaluate`

- [ ] **Step 2: Require a mocked login helper**

Assert `frontend/e2e/helpers/mock-login.js` exists and includes:
- `**/api/v1/auth/login`
- `login-username`
- `login-password`
- `login-submit`

- [ ] **Step 3: Run the red guard**

Run:

```powershell
python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_e2e_helpers_use_mocked_login_flow_instead_of_storage_token_seed -q
```

Expected: FAIL because the helpers still seed token storage directly and the shared mock-login helper does not exist.

### Task 2: Move Helper Sessions Behind Login

**Files:**
- Create: `frontend/e2e/helpers/mock-login.js`
- Modify: `frontend/e2e/helpers/review-mocks.js`
- Modify: `frontend/e2e/helpers/unified-entry-mocks.js`

- [ ] **Step 1: Create `loginThroughMockedPassword`**

Create a helper that:
- registers `**/api/v1/auth/login`
- returns `{ access_token, token_type: 'bearer', user, machine_info }`
- navigates to `/login`
- fills `login-username` and `login-password`
- clicks `login-submit`
- waits for an authenticated landing URL

- [ ] **Step 2: Update review mocks**

Remove direct storage writes from `setupReviewSessionAndMocks`. After all API mocks are registered, call `loginThroughMockedPassword(page, { token, user })`.

- [ ] **Step 3: Update unified entry mocks**

Remove direct storage writes from `setupUnifiedPerCoilEntrySession`. After all API mocks are registered, call `loginThroughMockedPassword(page, { token, user, machineContext })`.

### Task 3: Audit And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [ ] **Step 1: Move S10 to resolved**

Add `R76` for helper login-flow hardening and remove pending `S10`.

- [ ] **Step 2: Run targeted checks**

Run:

```powershell
python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py -q
npm --prefix frontend run e2e -- admin-surface.spec.js manage-shell.spec.js mobile-entry-smoke.spec.js
```

Expected: PASS.

- [ ] **Step 3: Run full checks**

Run:

```powershell
python -m pytest backend/tests -q
npm --prefix frontend test
npm --prefix frontend run build
git diff --check
```

Expected: PASS. Existing CRLF warnings are acceptable only if `git diff --check` exits 0.

- [ ] **Step 4: Review, commit, and push**

Commit:

```powershell
git add backend/tests/test_quick_cloud_trial_docs_and_ops.py frontend/e2e/helpers/mock-login.js frontend/e2e/helpers/review-mocks.js frontend/e2e/helpers/unified-entry-mocks.js docs/audits/2026-05-02-cleanup-round2-test-audit.md docs/superpowers/plans/2026-05-06-e2e-helper-login-flow.md
git commit -m "test: 让 e2e helpers 走登录流"
git push
```
