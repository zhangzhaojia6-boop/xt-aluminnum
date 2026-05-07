# Fill Intake Workshop Chart Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a workshop-level fill intake chart to the management realtime dashboard so draft, formal, and missing-cell pressure can be scanned by workshop, including unbound draft entries.

**Architecture:** Extend the existing realtime aggregation contract by adding entry intake counters into each workshop's `workshop_total` dict. The frontend derives dense horizontal rows from `aggregation.workshops`, then renders them immediately under the existing `填报接入` strip. No production facts are promoted, no draft rows are mutated, and formal tonnage remains scoped to submitted/verified/approved rows.

**Tech Stack:** FastAPI aggregation service, Pydantic dict contract, Vue 3, existing management command utilities, pytest, node test, Vite.

**Design Direction:** Utility command dashboard: restrained industrial palette, tabular numbers, compact horizontal bars, no onboarding copy, no nested cards.

---

### Task 1: Backend Workshop Intake Counters

**Files:**
- Modify: `backend/app/services/realtime_service.py`
- Modify: `backend/tests/test_realtime_service.py`
- Modify: `backend/tests/test_realtime_service_contract.py`

- [x] Add a regression assertion that a draft `WorkOrderEntry` without `machine_id` or `shift_id` increments its workshop's `workshop_total.draft_entry_count` and `workshop_total.total_entry_count`.
- [x] Add a contract assertion that submitted and draft rows produce per-workshop `formal_entry_count`, `draft_entry_count`, and `total_entry_count`.
- [x] Implement workshop-level counts from the full `entries` list before machine/shift cell filtering.
- [x] Keep `factory_total.output` and cell totals unchanged for unbound draft entries.
- [x] Run `python -m pytest backend/tests/test_realtime_service.py backend/tests/test_realtime_service_contract.py -q`.

### Task 2: Frontend Workshop Intake Chart

**Files:**
- Modify: `frontend/src/utils/managementCommandCenter.js`
- Modify: `frontend/tests/managementCommandCenter.test.js`
- Modify: `frontend/src/views/reports/LiveDashboard.vue`

- [x] Add `buildWorkshopFillIntakeRows(workshops, limit)` returning workshop name, formal count, draft count, missing cell count, total count, formal/draft/missing rates, and tone.
- [x] Add node tests for sorting draft-heavy workshops first and rendering missing-only workshops when no entries exist.
- [x] Render a compact `车间填报接入` section under the global `填报接入` strip with one row per workshop, three-segment meter, and numeric formal/draft/missing labels.
- [x] Keep the section responsive with fixed row structure and no nested cards.
- [x] Run `node --test frontend/tests/managementCommandCenter.test.js`.
- [x] Run `npm --prefix frontend run build`.

### Task 3: Check And Release

- [x] Run `python -m pytest backend/tests/test_realtime_service.py backend/tests/test_realtime_service_contract.py -q`.
- [x] Run `node --test frontend/tests/managementCommandCenter.test.js`.
- [x] Run `npm --prefix frontend run build`.
- [x] Run `git diff --check`.
- [x] Review the diff for read-only behavior and frontend scope.
- [x] Commit, push, deploy with `./scripts/deploy_systemd_host.sh --pull http://8.140.218.13`.
- [x] Verify production `/readyz` and a read-only production aggregation probe for workshop intake rows.
