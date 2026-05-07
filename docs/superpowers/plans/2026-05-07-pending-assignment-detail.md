# Pending Assignment Detail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only pending-assignment detail lane so managers can locate draft coil entries that are visible in fill intake but not assigned to a machine line.

**Architecture:** Reuse realtime aggregation scope and WorkOrderEntry data. Add a focused service helper and API endpoint that returns only entries missing `machine_id` or `shift_id`, then render those rows in the existing `异常与补录` management surface. This does not mutate drafts, promote entries, or change production totals.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic schemas, Vue 3, Element Plus, existing dashboard/realtime API clients, pytest, node test.

---

### Task 1: Backend Read-Only Detail Contract

**Files:**
- Modify: `backend/app/services/realtime_service.py`
- Modify: `backend/app/routers/realtime.py`
- Modify: `backend/app/schemas/realtime.py`
- Test: `backend/tests/test_realtime_service.py`
- Test: `backend/tests/test_realtime_routes.py`

- [x] Write a service test that seeds a draft `WorkOrderEntry` with `machine_id=None`, `shift_id=3`, and verifies the detail helper returns entry id, tracking card, workshop, shift, status, entry type, input/output tons, and `missing_fields=['machine_id']`.
- [x] Write a service test that verifies scoped workshop users only see rows from their workshop.
- [x] Add Pydantic response models for pending-assignment rows and response envelope.
- [x] Add `GET /api/v1/aggregation/live/pending-assignment?business_date=YYYY-MM-DD&workshop_id=...` using the same realtime user and scope checks as `/aggregation/live`.
- [x] Add route tests for admin access and workshop scope filtering.
- [x] Run `python -m pytest backend/tests/test_realtime_service.py backend/tests/test_realtime_routes.py -q`.

### Task 2: Frontend Review Surface

**Files:**
- Modify: `frontend/src/api/realtime.js`
- Modify: `frontend/src/views/review/ReviewTaskCenter.vue`
- Test: `frontend/tests/managementCommandCenter.test.js` or a focused existing frontend contract test

- [x] Add `fetchPendingAssignmentEntries(params)` to the realtime API client.
- [x] Add a `待归属` tab in `ReviewTaskCenter`, loaded together with dashboard data for the selected date.
- [x] Render rows with workshop, shift, tracking card, output tons, missing fields, and status; keep table dense and production-oriented.
- [x] Add static frontend contract assertions that the review page wires the new API call, tab label, table columns, and no mutation action text.
- [x] Run `node --test frontend/tests/reviewTaskCenter.test.js` and `node --test frontend/tests/managementCommandCenter.test.js`.
- [x] Run `npm --prefix frontend run build`.

### Task 3: Verification And Release

- [x] Run focused backend tests: `python -m pytest backend/tests/test_realtime_service.py backend/tests/test_realtime_routes.py -q`.
- [x] Run frontend tests: `npm --prefix frontend test`.
- [x] Run backend full suite if focused tests pass: `python -m pytest backend/tests -q`.
- [x] Run `npm --prefix frontend run build`.
- [x] Run `git diff --check`.
- [x] Commit and push with a conventional commit.
- [x] Deploy with `ssh root@8.140.218.13 "cd /srv/aluminum-bypass && ./scripts/deploy_systemd_host.sh --pull http://8.140.218.13"`.
- [x] Verify production `/readyz` and the pending-assignment detail endpoint returns the 17 draft rows; current `factory_output=29.85` comes from submitted bound rows, while the `120.46t` pending draft output stays outside formal output totals.
