# Quality Center E2E Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit item F20 by adding browser-level automation for the quality center's run-checks, detail, resolve, ignore, and fill-only isolation flows.

**Architecture:** Keep the quality page behavior unchanged. Add a dedicated Playwright spec that uses the existing review session mock helper and local quality API mocks with in-memory state, so the E2E test proves real UI wiring, request parameters, prompt notes, status transitions, and detail navigation.

**MES and Rule Context:** Live MES login page is reachable; local credentials are not printed and the current cycle relies on repository contracts. Local MES contracts and historical import samples confirm `business_date`, `workshop_code`, `machine_code`, `source_row_no`, owner/QC fields, and `resolve_note` as traceability fields; this E2E test must verify quality closure records operator-entered notes and uses the selected business date.

**Tech Stack:** Playwright, Vue 3, Element Plus prompt dialogs, existing review E2E mocks.

---

### Task 1: Establish Missing E2E Baseline

**Files:**
- Create: `frontend/e2e/quality-center.spec.js`

- [x] **Step 1: Run targeted spec before it exists**

Run:

```bash
cd frontend && npx playwright test e2e/quality-center.spec.js
```

Expected before implementation: FAIL / no matching tests, proving F20 has no dedicated E2E coverage.

### Task 2: Add Quality Center E2E

**Files:**
- Create: `frontend/e2e/quality-center.spec.js`

- [x] **Step 1: Install review session mocks**

Use `setupReviewSessionAndMocks(page)` and add local routes for:
- `GET /api/v1/quality/issues`
- `POST /api/v1/quality/run-checks`
- `POST /api/v1/quality/issues/:id/resolve`
- `POST /api/v1/quality/issues/:id/ignore`

- [x] **Step 2: Assert list and detail flow**

Navigate to `/manage/quality`, verify table headers and the seeded open issue, click `详情`, and assert `/manage/quality/detail/11` shows source, field, status, and issue text.

- [x] **Step 3: Assert run-check request and refresh**

Click `运行质量检查`, assert the POST body includes the current business date, and verify a generated issue appears.

- [x] **Step 4: Assert two disposition actions**

For resolve and ignore, fill the Element Plus prompt, submit, and assert the mocked request body carries the normalized note and the visible status changes to the expected label.

- [x] **Step 5: Guard against fill-only leakage**

Verify a fill-only user cannot access `/manage/quality` and does not see the quality center.

### Task 3: Close Audit Item And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move F20 to fixed list**

Add a fixed row for quality center E2E coverage and remove F20 from the pending table.

- [x] **Step 2: Run focused and full verification**

Run:

```bash
cd frontend && npx playwright test e2e/quality-center.spec.js
cd frontend && npm run test
cd frontend && npm run build
python -m pytest backend/tests/test_quality_checks.py backend/tests/test_mobile_entry_copy_consistency.py backend/tests/test_reference_command_center_spec.py -q
python -m pytest backend/tests -q --durations=10
git diff --check
```

When `https://localhost` is backed by stale nginx assets, run the Playwright command against the live Vite server:

```powershell
cd frontend
$env:PLAYWRIGHT_BASE_URL='http://127.0.0.1:4207'
npx playwright test e2e/quality-center.spec.js
```

Expected: all commands pass.

- [x] **Step 3: Review diff, commit, push**

Review for scope drift and test reliability, then commit with:

```bash
git add docs/superpowers/plans/2026-05-05-quality-center-e2e-coverage.md frontend/e2e/quality-center.spec.js docs/audits/2026-05-02-cleanup-round2-test-audit.md
git commit -m "test: 覆盖质量中心关键流程"
git push
```
