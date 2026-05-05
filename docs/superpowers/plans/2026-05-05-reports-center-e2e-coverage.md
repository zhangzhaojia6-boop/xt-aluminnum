# Reports Center E2E Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit item F19 by adding browser-level automation for the reports center's list query parameters, detail navigation, and fill-only isolation.

**Architecture:** Keep the reports page behavior unchanged. Add a dedicated Playwright spec that uses the existing review session mock helper and local reports API mocks with in-memory data, so the E2E test proves real UI wiring, query parameters, summary rendering, detail fields, and route guard behavior.

**MES and Rule Context:** Live MES login page is reachable; this cycle uses repository contracts without printing credentials. Local MES contracts and import samples confirm `business_date`, `workshop_code`, `machine_code`, `source_row_no`, and report delivery status as traceability inputs; this E2E test must verify the report list sends date/type/status filters and the detail view exposes delivery and production summary fields.

**Tech Stack:** Playwright, Vue 3, existing review E2E mocks, report display helpers.

---

### Task 1: Establish Missing E2E Baseline

**Files:**
- Create: `frontend/e2e/reports-center.spec.js`

- [x] **Step 1: Run targeted spec before it exists**

Run:

```bash
cd frontend && npx playwright test e2e/reports-center.spec.js
```

Expected before implementation: FAIL / no matching tests, proving F19 has no dedicated E2E coverage.

### Task 2: Add Reports Center E2E

**Files:**
- Create: `frontend/e2e/reports-center.spec.js`

- [x] **Step 1: Install review session mocks**

Use `setupReviewSessionAndMocks(page)` and add local routes for:
- `GET /api/v1/reports`
- `GET /api/v1/reports/:id`

- [x] **Step 2: Assert list query parameters**

Navigate to `/manage/reports`, verify the list headers and seeded report, set report type/status filters, click `查询`, and assert the captured GET params include `start_date`, `end_date`, `report_type`, and `status`.

- [x] **Step 3: Assert detail navigation and fields**

Click `查看详情`, assert `/manage/reports/detail/31`, and verify report date/type/status, final summary, core metrics, workshop summary, yield matrix, and mobile reporting summary render from the mocked detail payload.

- [x] **Step 4: Guard against fill-only leakage**

Verify a fill-only user cannot access `/manage/reports` and does not see the reports center.

### Task 3: Close Audit Item And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move F19 to fixed list**

Add a fixed row for reports center E2E coverage and remove F19 from the pending table.

- [x] **Step 2: Run focused and full verification**

Run:

```bash
cd frontend && npx playwright test e2e/reports-center.spec.js
cd frontend && npm run test
cd frontend && npm run build
python -m pytest backend/tests/test_report_export.py backend/tests/test_mobile_entry_copy_consistency.py backend/tests/test_reference_command_center_spec.py -q
python -m pytest backend/tests -q --durations=10
git diff --check
```

When `https://localhost` is backed by stale nginx assets, run the Playwright command against the live Vite server:

```powershell
cd frontend
$env:PLAYWRIGHT_BASE_URL='http://127.0.0.1:4207'
npx playwright test e2e/reports-center.spec.js
```

Expected: all commands pass.

- [x] **Step 3: Review diff, commit, push**

Review for scope drift and test reliability, then commit with:

```bash
git add docs/superpowers/plans/2026-05-05-reports-center-e2e-coverage.md frontend/e2e/reports-center.spec.js docs/audits/2026-05-02-cleanup-round2-test-audit.md
git commit -m "test: 覆盖日报交付中心关键流程"
git push
```
