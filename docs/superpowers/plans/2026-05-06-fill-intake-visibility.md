# Fill Intake Visibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make current fill-test data visible in the management realtime surface by showing submitted versus draft intake counts without promoting draft records into formal production facts.

**Architecture:** Extend the existing realtime aggregation payload with formal, draft, and total entry counts. Counts are computed across all entries so unbound draft tests remain visible, while formal output totals still only use eligible cell rows. Reuse `LiveDashboard.vue` as the management surface and render a compact status strip from the existing `/api/v1/realtime/aggregation/live` response. No `ShiftProductionData` rows are created or mutated.

**Tech Stack:** FastAPI, Pydantic, existing realtime service, Vue 3, node static tests, pytest.

---

### Task 1: Realtime Aggregation Counts

**Files:**
- Modify: `backend/app/services/realtime_service.py`
- Modify: `backend/app/schemas/realtime.py`
- Modify: `backend/tests/test_realtime_service.py`

- [x] Add failing test coverage for `overall_progress.formal_entry_count`, `overall_progress.draft_entry_count`, `overall_progress.total_entry_count`, and per-cell `draft_count`.
- [x] Implement counts in `aggregate_live_payload()` from existing `entries` without changing weight totals or submission status semantics; unbound draft entries count toward intake visibility but not output totals.
- [x] Expose `draft_count` on `LiveShiftCellOut`.
- [x] Run `python -m pytest backend/tests/test_realtime_service.py -q` -> 4 passed.

### Task 2: Management First-Screen Intake Strip

**Files:**
- Modify: `frontend/src/utils/managementCommandCenter.js`
- Modify: `frontend/src/views/reports/LiveDashboard.vue`
- Modify: `frontend/tests/managementCommandCenter.test.js`

- [x] Add `buildFillIntakeSummary(aggregation)` helper that returns formal, draft, total, missing, draft rate, and tone.
- [x] Render a compact `填报接入` strip above existing distribution sections with labels `已进入正式`, `草稿待提交`, and `缺报班次`.
- [x] Keep styling dense and workbench-like: no helper copy, no marketing copy, no nested cards.
- [x] Run `node --test frontend/tests/managementCommandCenter.test.js` -> 15 passed.

### Task 3: Verification And Release

- [x] Run focused backend and frontend tests.
- [x] Run `npm --prefix frontend run build` -> passed.
- [x] Run `python -m pytest backend/tests -q` -> 721 passed, 124 deselected, 31 warnings.
- [x] Run `npm --prefix frontend test` -> 121 passed.
- [x] Run `git diff --check` -> passed with Windows LF/CRLF warnings only.
- [x] Review diff for read-only behavior and UI scope.
- [x] Run `python -m pytest backend/tests/test_realtime_service.py backend/tests/test_realtime_service_contract.py -q` -> 8 passed.
- [x] Commit, push, deploy, and verify `/readyz` -> `main@efc8ed3` deployed; `/readyz` ready with `mes_sync last_run_status=success`, `fetched_count=50`, `upserted_count=50`; production data probe returned `work_order_entries draft=156`, `mobile_shift_reports draft=3`, `mobile_coil_agg/voided=28`.

### Task 4: Unbound Draft Intake Regression

- [x] Add failing regression coverage for a draft `WorkOrderEntry` without `machine_id` or `shift_id`: it must count in `overall_progress.draft_entry_count/total_entry_count`, while factory and cell output totals stay unchanged.
- [x] Move aggregate entry counts to the full `entries` list before cell filtering; keep per-cell counts and production tons scoped to bound machine+shift rows.
- [x] Run `python -m pytest backend/tests/test_realtime_service.py::test_aggregate_live_payload_groups_workshops_machines_and_shifts -q` before the fix -> failed on `draft_entry_count` and `total_entry_count`.
- [x] Run `python -m pytest backend/tests/test_realtime_service.py backend/tests/test_realtime_service_contract.py -q` -> 8 passed.
- [x] Run `python -m pytest backend/tests -q` -> 721 passed, 124 deselected, 31 warnings.
- [x] Run `git diff --check` -> passed with Windows LF/CRLF warnings only.
- [x] Commit, push, deploy, and verify production API -> `main@2f888bb` deployed; `/readyz` ready with `mes_sync last_run_status=success`, `fetched_count=50`, `upserted_count=50`; `/api/v1/aggregation/live?business_date=2026-05-06` returned `formal_entry_count=0`, `draft_entry_count=17`, `total_entry_count=17`.
