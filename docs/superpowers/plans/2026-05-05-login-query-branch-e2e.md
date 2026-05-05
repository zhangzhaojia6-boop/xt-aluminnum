# Login Query Branch E2E Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit item F08 by adding browser-level coverage for login query branches and redirect query cleanup.

**Architecture:** Add one focused Playwright spec that drives the real `Login.vue` page and mocks only the backend endpoints needed for each branch. Keep production login code unchanged unless a test exposes a real defect.

**MES and Rule Context:** Login query branches are entry routing concerns. The downstream mobile entry mocks must still preserve the current factory structure vocabulary: workshop, machine, shift, machine-bound entry, and template type, matching the existing MES boundary where machine/workshop context gates data capture.

**Tech Stack:** Playwright E2E, Vue Router, existing mobile entry API contracts.

---

### Task 1: Add Login Query Branch E2E

**Files:**
- Create: `frontend/e2e/login-query-branches.spec.js`

- [x] **Step 1: Add shared mobile entry mocks**

Implement local helpers in the spec:
- `fillUser(overrides)` returns a fill-capable user.
- `machineInfo(overrides)` returns machine-bound context.
- `mockMobileEntry(page, options)` mocks:
  - `GET /api/v1/mobile/bootstrap`
  - `GET /api/v1/mobile/current-shift`
  - `GET /api/v1/templates/{workshop_type}`

- [x] **Step 2: Cover DingTalk auth code and redirect cleanup**

Add a test that:
- Opens `/login?redirect=/entry?auth_code=dt-code&state=state-1&workshop=ZD`.
- Mocks `POST /api/v1/dingtalk/h5-login`.
- Asserts the posted code is `dt-code`.
- Asserts the final URL is `/entry?workshop=ZD`, with `auth_code` and `state` removed.
- Asserts the mobile entry page is visible.

- [x] **Step 3: Cover machine QR login**

Add a test that:
- Opens `/login?machine=XT-ZR2-1`.
- Mocks `POST /api/v1/auth/qr-login`.
- Asserts the posted QR code is `XT-ZR2-1`.
- Returns a token, fill-capable machine user, and machine context.
- Asserts the final URL is `/entry` and the machine-bound mobile entry is visible.

- [x] **Step 4: Cover workshop QR and workshop query hints**

Add a test that:
- Opens `/login?machine=WORKSHOP-ZD`.
- Mocks `POST /api/v1/auth/qr-login` to return `type: "workshop_redirect"`.
- Asserts the login page stays visible and shows the workshop hint.
- Opens `/login?workshop=JZ`.
- Asserts the direct workshop query hint is visible.

### Task 2: Close F08 And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`
- Modify: `docs/superpowers/plans/2026-05-05-login-query-branch-e2e.md`

- [x] **Step 1: Move F08 to fixed list**

Add a fixed row for login query branch coverage and remove F08 from the pending table.

- [x] **Step 2: Run targeted verification**

Run:

```bash
cd frontend && npx playwright test e2e/login-query-branches.spec.js
cd frontend && npm run test
cd frontend && npm run build
python -m pytest backend/tests/test_mobile_entry_copy_consistency.py backend/tests/test_reference_command_center_spec.py -q
python -m pytest backend/tests -q --durations=10
git diff --check
```

Expected:
- New E2E tests pass.
- Existing frontend tests and build pass.
- Focused backend cross-contract tests and full backend suite pass.
- Diff check has no whitespace errors.

- [x] **Step 3: Review diff, commit, push**

Review for scope drift and hidden credentials, then commit with:

```bash
git add docs/superpowers/plans/2026-05-05-login-query-branch-e2e.md frontend/e2e/login-query-branches.spec.js docs/audits/2026-05-02-cleanup-round2-test-audit.md
git commit -m "test: 覆盖登录 query 分支"
git push
```
