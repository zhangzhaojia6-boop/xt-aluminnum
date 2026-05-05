# E2E Stability Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit items F23 and F24 by removing hardcoded secondary-context baseURL behavior and UTC-derived business-date fallback from E2E tests.

**Architecture:** Keep product code unchanged. Update only E2E support logic so secondary browser contexts inherit Playwright's configured baseURL and business-date fallback uses local calendar formatting.

**MES and Rule Context:** Live MES login page is reachable; this cycle uses repository contracts without printing credentials. MES/import contracts confirm `business_date`, `workshop_code`, and `machine_code` are local production-day fields, so test fallback dates must not drift across UTC boundaries.

**Tech Stack:** Playwright, JavaScript E2E specs, existing local Vite baseURL.

---

### Task 1: Remove Secondary Context BaseURL Drift

**Files:**
- Modify: `frontend/e2e/workshop-template-config.spec.js`

- [x] **Step 1: Run targeted baseline**

Run:

```bash
cd frontend && npx playwright test e2e/workshop-template-config.spec.js
```

Expected before implementation: existing test may pass, but the source still hardcodes a fallback baseURL for the secondary context.

- [x] **Step 2: Inject Playwright baseURL into the secondary context**

Use the `testInfo` fixture to read the configured baseURL, pass it to `browser.newContext({ baseURL, ... })`, and navigate with `machinePage.goto('/entry')`.

### Task 2: Use Local Business Date Fallback

**Files:**
- Modify: `frontend/e2e/owner-only-utility-workshop.spec.js`

- [x] **Step 1: Replace UTC fallback**

Add a local date formatter and change `resolveBusinessDate()` to use it when the submit payload has no valid `business_date`.

- [x] **Step 2: Verify no UTC fallback remains**

Run:

```bash
rg -n "toISOString\\(\\)\\.slice\\(0, 10\\)|baseURL = process\\.env\\.PLAYWRIGHT_BASE_URL" frontend/e2e/workshop-template-config.spec.js frontend/e2e/owner-only-utility-workshop.spec.js
```

Expected: no matches.

### Task 3: Close Audit Items And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move F23 and F24 to fixed list**

Add fixed rows for the E2E baseURL and local business-date fixes, and remove F23/F24 from the pending table.

- [x] **Step 2: Run verification**

Run:

```bash
cd frontend && npx playwright test e2e/workshop-template-config.spec.js
cd frontend && npm run test
cd frontend && npm run build
python -m pytest backend/tests/test_mobile_entry_copy_consistency.py backend/tests/test_reference_command_center_spec.py -q
python -m pytest backend/tests -q --durations=10
git diff --check
```

When `https://localhost` is backed by stale nginx assets, run the Playwright command against the live Vite server:

```powershell
cd frontend
$env:PLAYWRIGHT_BASE_URL='http://127.0.0.1:4207'
npx playwright test e2e/workshop-template-config.spec.js
```

Expected: all commands pass.

- [x] **Step 3: Review diff, commit, push**

Review for scope drift and test reliability, then commit with:

```bash
git add docs/superpowers/plans/2026-05-05-e2e-stability-cleanup.md frontend/e2e/workshop-template-config.spec.js frontend/e2e/owner-only-utility-workshop.spec.js docs/audits/2026-05-02-cleanup-round2-test-audit.md
git commit -m "test: 稳定二级浏览器上下文和业务日期"
git push
```
