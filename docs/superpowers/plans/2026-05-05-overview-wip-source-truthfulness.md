# Overview WIP Source Truthfulness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit item F18 by stopping the overview WIP card from displaying permanent mock/fallback values as if they were live production data.

**Architecture:** Keep the overview layout. Replace `mesWipSnapshotMock` with the existing `factory-command/overview` data path, derive display labels from `source` and `freshness`, and show `--` / source status when live data is unavailable.

**MES and Rule Context:** Live MES login page is reachable but no usable local credentials are configured for an inner MES login. Local MES contracts and historical reference files confirm `workshop_code`, `machine_code`, source freshness, and owner/QC fields are traceability inputs; the overview must not show historical sample WIP tonnage as current data.

**Tech Stack:** Vue 3, existing dashboard/factory-command APIs, frontend node tests.

---

### Task 1: Add Regression Tests First

**Files:**
- Create: `frontend/src/utils/overviewWipSummary.js`
- Create: `frontend/tests/overviewWipSummary.test.js`

- [x] **Step 1: Test WIP summary from real factory-command payload**

Add node tests asserting `wip_tons`, `today_output_tons`, `source`, and `freshness` become explicit display values and source labels.

- [x] **Step 2: Test unavailable data does not show mock tonnage**

Assert unavailable/failed payloads return `--` values and a non-live source label.

- [x] **Step 3: Test OverviewCenter no longer imports the mock**

Read `frontend/src/views/review/OverviewCenter.vue` and assert it imports `fetchFactoryCommandOverview` and `buildOverviewWipSummary`, and no longer imports `mesWipSnapshotMock` or renders a hardcoded `fallback` badge.

- [x] **Step 4: Run tests and confirm red**

Run:

```bash
cd frontend && node --test tests/overviewWipSummary.test.js
```

Expected before implementation: helper import/source checks fail because the overview still uses `mesWipSnapshotMock`.
Observed before implementation:
- `cd frontend && node --test tests/overviewWipSummary.test.js`: FAIL, `ERR_MODULE_NOT_FOUND` for `frontend/src/utils/overviewWipSummary.js`.

### Task 2: Implement Overview WIP Data Source

**Files:**
- Modify: `frontend/src/views/review/OverviewCenter.vue`
- Modify: `frontend/src/utils/overviewWipSummary.js`

- [x] **Step 1: Add pure WIP summary helper**

Implement display helpers for tonnage values, source labels, and source tone from factory-command overview payloads.

- [x] **Step 2: Fetch factory-command overview safely**

Load `fetchFactoryCommandOverview()` alongside dashboard and delivery. If it fails, keep the overview usable and mark WIP source unavailable.

- [x] **Step 3: Render dynamic source and values**

Use computed WIP labels and dynamic source badge instead of sample WIP summary values.

- [x] **Step 4: Style source badge states**

Add compact scoped badge styles for live, degraded, and unavailable states.

### Task 3: Close Audit Item And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move F18 to fixed list**

Add a fixed row for overview WIP source truthfulness and remove F18 from the pending table.

- [x] **Step 2: Run focused and full verification**

Run:

```bash
cd frontend && node --test tests/overviewWipSummary.test.js
cd frontend && npm run test
cd frontend && npm run build
python -m pytest backend/tests/test_mobile_entry_copy_consistency.py backend/tests/test_reference_command_center_spec.py -q
python -m pytest backend/tests -q --durations=10
git diff --check
```

Expected: all commands pass.
Focused checks so far:
- `cd frontend && node --test tests/overviewWipSummary.test.js`: PASS, `4 passed`.
Full checks:
- `cd frontend && npm run test`: PASS, `104 passed`.
- `cd frontend && npm run build`: PASS.
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py backend/tests/test_reference_command_center_spec.py -q`: PASS, `106 passed`.
- `python -m pytest backend/tests -q --durations=10`: PASS, `743 passed, 30 warnings`.
- `git diff --check`: PASS, only Windows LF-to-CRLF warnings.

- [x] **Step 3: Review diff, commit, push**

Review for scope drift and frontend behavior, then commit with:

```bash
git add docs/superpowers/plans/2026-05-05-overview-wip-source-truthfulness.md frontend/src/views/review/OverviewCenter.vue frontend/src/utils/overviewWipSummary.js frontend/tests/overviewWipSummary.test.js docs/audits/2026-05-02-cleanup-round2-test-audit.md
git commit -m "fix: 区分总览在制料数据来源"
git push
```

Review: no scope drift found. The overview WIP card no longer imports sample WIP data, uses factory-command overview when available, and marks unavailable data without sample tonnage.
