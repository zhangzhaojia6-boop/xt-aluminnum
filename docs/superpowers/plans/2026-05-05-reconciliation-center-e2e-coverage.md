# Reconciliation Center E2E Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit item F21 by adding browser-level automation for the reconciliation center's generate, detail, confirm, ignore, and correct flows.

**Architecture:** Keep the reconciliation page behavior unchanged. Add a dedicated Playwright spec that uses the existing review session mock helper and local reconciliation API mocks with in-memory state, so the E2E test proves real UI wiring, request parameters, prompt notes, status transitions, and detail navigation.

**MES and Rule Context:** Live MES login page is reachable but no usable local credentials are configured for an inner MES login. Local MES contracts and historical import samples confirm `workshop_code`, `machine_code`, `source_row_no`, owner/QC fields, and `reason` / `resolve_note` are traceability fields; this E2E test must verify reconciliation closure records operator-entered notes.

**Tech Stack:** Playwright, Vue 3, Element Plus prompt dialogs, existing review E2E mocks.

---

### Task 1: Establish Missing E2E Baseline

**Files:**
- Create: `frontend/e2e/reconciliation-center.spec.js`

- [x] **Step 1: Run targeted spec before it exists**

Run:

```bash
cd frontend && npx playwright test e2e/reconciliation-center.spec.js
```

Result before implementation: FAIL / no matching tests, proving F21 had no dedicated E2E coverage.

### Task 2: Add Reconciliation Center E2E

**Files:**
- Create: `frontend/e2e/reconciliation-center.spec.js`

- [x] **Step 1: Install review session mocks**

Use `setupReviewSessionAndMocks(page)` and add local routes for:
- `GET /api/v1/reconciliation/items`
- `POST /api/v1/reconciliation/generate`
- `POST /api/v1/reconciliation/items/:id/confirm`
- `POST /api/v1/reconciliation/items/:id/ignore`
- `POST /api/v1/reconciliation/items/:id/correct`

- [x] **Step 2: Assert list and detail flow**

Navigate to `/manage/reconciliation`, verify table headers and the seeded open item, click `详情`, and assert `/manage/reconciliation/detail/11` shows source, field, status, and values.

- [x] **Step 3: Assert generation request and refresh**

Click `生成差异`, assert the POST body includes the current business date, and verify a generated item appears.

- [x] **Step 4: Assert three disposition actions**

For confirm, ignore, and correct, fill the Element Plus prompt, submit, and assert the mocked request body carries the typed note and the visible status changes to the expected label.

- [x] **Step 5: Guard against fill-only leakage**

Verify a fill-only user cannot access `/manage/reconciliation` and does not see the reconciliation center.

### Task 3: Close Audit Item And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move F21 to fixed list**

Add a fixed row for reconciliation center E2E coverage and remove F21 from the pending table.

- [x] **Step 2: Run focused and full verification**

Run:

```bash
cd frontend && npx playwright test e2e/reconciliation-center.spec.js
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
npx playwright test e2e/reconciliation-center.spec.js
```

Expected: all commands pass.

Recovery verification on 2026-05-06:

- `npx playwright test e2e/reconciliation-center.spec.js`: FAIL against default `https://localhost`; confirm/ignore used stale static assets without the prompt.
- `$env:PLAYWRIGHT_BASE_URL='http://127.0.0.1:4207'; npx playwright test e2e/reconciliation-center.spec.js`: PASS, `5 passed`.
- `npm run test`: PASS, `108 passed`.
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py backend/tests/test_reference_command_center_spec.py -m frontend_contract -q`: PASS, `110 passed`.
- `npm run build`: PASS.
- `python -m pytest backend/tests -q --durations=10`: PASS, `646 passed, 119 deselected, 30 warnings`.

- [x] **Step 3: Review diff, commit, push**

Review for scope drift and test reliability, then commit with:

```bash
git add docs/superpowers/plans/2026-05-05-reconciliation-center-e2e-coverage.md frontend/e2e/reconciliation-center.spec.js docs/audits/2026-05-02-cleanup-round2-test-audit.md
git commit -m "test: 覆盖差异核对中心关键流程"
git push
```

Implementation commit `d730700 test: 覆盖差异核对中心关键流程` is an ancestor of current `main`.
