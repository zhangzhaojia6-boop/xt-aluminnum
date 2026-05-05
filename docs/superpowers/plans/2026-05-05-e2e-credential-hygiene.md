# E2E Credential Hygiene Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit item F22 by removing hardcoded real E2E account names and passwords from credentialed browser tests.

**Architecture:** Keep mocked session tokens unchanged because they are synthetic test data. Add a tiny E2E credential helper that reads environment variables and skips credentialed tests when required values are missing, then update real-login specs to use it instead of hardcoded fallbacks.

**MES and Rule Context:** Live MES login page is reachable; this cycle does not print credentials. Owner/admin login tests must use locally supplied Playwright environment variables so the repository remains safe to share.

**Tech Stack:** Playwright, JavaScript E2E specs, existing `.env` loading in `frontend/playwright.config.js`.

---

### Task 1: Add Credential Helper

**Files:**
- Create: `frontend/e2e/helpers/credentials.js`

- [x] **Step 1: Add environment lookup and skip helper**

Implement:
- `firstEnv(...names)` returns the first non-empty environment value.
- `skipWithoutCredentials(requirements)` calls `test.skip()` with a clear missing-variable message.

### Task 2: Remove Hardcoded Real Credentials

**Files:**
- Modify: `frontend/e2e/compose-smoke.spec.js`
- Modify: `frontend/e2e/login-delivery-smoke.spec.js`
- Modify: `frontend/e2e/mobile-entry-smoke.spec.js`
- Modify: `frontend/e2e/owner-only-inventory-dashboard.spec.js`
- Modify: `frontend/e2e/owner-only-contract-dashboard.spec.js`
- Modify: `frontend/e2e/owner-only-utility-workshop.spec.js`

- [x] **Step 1: Replace admin credential fallbacks**

Use `firstEnv('PLAYWRIGHT_USERNAME', 'INIT_ADMIN_USERNAME')` and `firstEnv('PLAYWRIGHT_PASSWORD', 'INIT_ADMIN_PASSWORD')`, then skip credentialed login tests if either is missing.

- [x] **Step 2: Replace owner credential fallbacks**

Use owner-specific environment variables only:
- inventory: `PLAYWRIGHT_INVENTORY_USERNAME`, `PLAYWRIGHT_INVENTORY_PASSWORD`
- contract: `PLAYWRIGHT_CONTRACT_USERNAME`, `PLAYWRIGHT_CONTRACT_PASSWORD`
- utility: `PLAYWRIGHT_UTILITY_USERNAME`, `PLAYWRIGHT_UTILITY_PASSWORD`

- [x] **Step 3: Verify hardcoded real credentials are gone**

Run:

```bash
rg -n "Admin#Gate2026_Strong|\\b591767\\b|\\b506371\\b|\\b101901\\b|\\| 'admin'|\\| 'CPK-A-" frontend/e2e
```

Expected: no matches.

### Task 3: Close Audit Item And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move F22 to fixed list**

Add a fixed row for E2E credential hygiene and remove F22 from the pending table.

- [x] **Step 2: Run verification**

Run:

```bash
cd frontend && npx playwright test e2e/compose-smoke.spec.js e2e/login-delivery-smoke.spec.js e2e/mobile-entry-smoke.spec.js e2e/owner-only-inventory-dashboard.spec.js e2e/owner-only-contract-dashboard.spec.js e2e/owner-only-utility-workshop.spec.js
cd frontend && npm run test
cd frontend && npm run build
python -m pytest backend/tests/test_mobile_entry_copy_consistency.py backend/tests/test_reference_command_center_spec.py -q
python -m pytest backend/tests -q --durations=10
git diff --check
```

Expected: targeted E2E passes or skips credentialed cases when local environment lacks required credentials; non-credentialed checks pass.

- [x] **Step 3: Review diff, commit, push**

Review for scope drift and security regression, then commit with:

```bash
git add docs/superpowers/plans/2026-05-05-e2e-credential-hygiene.md frontend/e2e/helpers/credentials.js frontend/e2e/compose-smoke.spec.js frontend/e2e/login-delivery-smoke.spec.js frontend/e2e/mobile-entry-smoke.spec.js frontend/e2e/owner-only-inventory-dashboard.spec.js frontend/e2e/owner-only-contract-dashboard.spec.js frontend/e2e/owner-only-utility-workshop.spec.js docs/audits/2026-05-02-cleanup-round2-test-audit.md
git commit -m "test: 移除 e2e 硬编码真实凭据"
git push
```
