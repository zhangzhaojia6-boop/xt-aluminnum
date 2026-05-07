# Pending Assignment Lineage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the management `待归属` list show why uploaded fill rows cannot yet bind to a machine line or external MES projection.

**Architecture:** Add read-only lineage fields to the existing pending-assignment API. The frontend consumes those fields as table columns, without adding mutation buttons or changing production data.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Vue 3, Element Plus, node test runner, pytest.

---

## Scope

This is a diagnostic bridge for the current "uploaded but not machine-bound" issue. It does not promote drafts, assign machine lines, write MES data, or mutate production rows.

## Files

- Modify: `backend/app/services/realtime_service.py`
- Modify: `backend/app/schemas/realtime.py`
- Modify: `backend/tests/test_realtime_service.py`
- Modify: `frontend/src/views/review/ReviewTaskCenter.vue`
- Modify: `frontend/tests/reviewTaskCenter.test.js`
- Modify: `docs/deploy/current-state.md`

## Task 1: Backend Lineage Fields

- [x] **Step 1: Add failing test coverage**

Update `backend/tests/test_realtime_service.py::test_build_pending_assignment_detail_lists_rows_and_summary` to seed:

- a creator user for one pending row,
- a local MES coil snapshot with the same tracking card and a resolvable machine,
- at least one active machine candidate in the same workshop.

Expected new item fields:

- `created_by_user_name`
- `created_by_username`
- `mes_match_count`
- `mes_machine_id`
- `mes_machine_name`
- `machine_candidate_count`
- `machine_candidate_names`

Run:

```bash
python -m pytest backend/tests/test_realtime_service.py::test_build_pending_assignment_detail_lists_rows_and_summary -q
```

Expected: FAIL until service/schema fields exist.

- [x] **Step 2: Implement read-only enrichment**

In `build_pending_assignment_detail()`:

- preload creator users by `created_by_user_id`,
- preload running, active equipment candidates by workshop,
- call existing `_load_mes_snapshot_rows()` with the pending tracking card set,
- map normalized tracking-card keys to local MES candidate rows,
- attach only read-only diagnostics to each pending item.

Do not change entry status, machine assignment, shift assignment, or aggregation.

- [x] **Step 3: Update schema**

Add optional/defaulted fields to `LivePendingAssignmentItemOut` so older clients remain compatible.

- [x] **Step 4: Run backend targeted tests**

Run:

```bash
python -m pytest backend/tests/test_realtime_service.py backend/tests/test_realtime_routes.py -q
```

Expected: pass.

## Task 2: Management Table Display

- [x] **Step 1: Add static frontend test assertions**

Update `frontend/tests/reviewTaskCenter.test.js` to assert the review page references the new lineage fields and renders source/lineage columns.

Run:

```bash
npm --prefix frontend test
```

Expected: FAIL until UI uses the fields.

- [x] **Step 2: Add columns and formatting**

In `ReviewTaskCenter.vue`:

- add a `录入来源` column,
- add a `归属线索` column,
- format `created_by_user_id=null` as `无账号录入`,
- format MES matches as `外部MES：<机列名>` or `外部MES已匹配`,
- format no MES match with workshop candidates as `车间候选 <n> 台`,
- keep existing `待归属` behavior and active business date logic unchanged.

- [x] **Step 3: Run frontend tests**

Run:

```bash
npm --prefix frontend test
```

Expected: pass.

## Task 3: Evidence, Deploy Notes, and Verification

- [x] **Step 1: Update deployment state**

Add a current-state note explaining that `待归属` now exposes creator, MES match, and machine-candidate diagnostics.

- [x] **Step 2: Run verification**

Run:

```bash
git diff --check
python -m pytest backend/tests/test_realtime_service.py backend/tests/test_realtime_routes.py -q
npm --prefix frontend test
npm --prefix frontend run build
python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_current_deploy_state_tracks_current_head_and_validation_evidence -q
```

Expected: all pass.

- [ ] **Step 3: Commit and deploy**

Commit only the touched files and leave unrelated untracked specs alone unless explicitly included.

Use:

```bash
git commit -m "fix: 展示待归属填报根因线索"
git push origin main
ssh -o BatchMode=yes root@8.140.218.13 "cd /srv/aluminum-bypass && ./scripts/deploy_systemd_host.sh --pull http://8.140.218.13"
```

- [ ] **Step 4: Production probe**

Verify:

- `/readyz` is ready,
- remote HEAD matches the commit,
- pending-assignment returns `active_business_date=2026-05-06`, `pending_total=17`,
- items show `created_by_user_id=null`, `mes_match_count=0`, and nonzero machine candidates where workshop machines exist.
