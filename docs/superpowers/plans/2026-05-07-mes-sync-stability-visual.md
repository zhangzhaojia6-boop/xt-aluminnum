# MES Sync Stability Visual Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the management dashboard show whether the external MES link has stayed stable across recent sync runs, not just the latest status.

**Architecture:** Reuse `mes_sync_run_logs` as the source of truth. Add a read-only backend endpoint for recent run logs, then render a compact stability strip in `LiveDashboard` using existing CSS-only bars and management language. Do not change MES polling, credentials, sync cadence, or production facts.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Vue 3, existing MES API client, pytest, node test, Vite.

---

### Task 1: Backend Recent Run Contract

**Files:**
- Modify: `backend/app/services/mes_sync_service.py`
- Modify: `backend/app/schemas/mes_sync.py`
- Modify: `backend/app/routers/mes.py`
- Test: `backend/tests/test_mes_sync_lag.py`
- Test: `backend/tests/test_factory_command_routes.py`

- [x] Add a service test that seeds recent `MesSyncRunLog` rows and expects newest-first rows with duration, counts, status, and non-secret error text.
- [x] Add Pydantic response models for recent MES sync runs and summary counts.
- [x] Add `mes_sync_service.recent_sync_runs(db, limit=12)` with limit clamp and datetime/decimal normalization.
- [x] Add `GET /api/v1/mes/sync-runs?limit=12`, using the same manager/reviewer/admin scope as `/mes/sync-status`; hide `error_message` from non-admin responses.
- [x] Run `python -m pytest backend/tests/test_mes_sync_lag.py backend/tests/test_factory_command_routes.py::test_mes_sync_status_route -q`.

### Task 2: Frontend Stability Strip

**Files:**
- Modify: `frontend/src/api/mes.js`
- Modify: `frontend/src/views/reports/LiveDashboard.vue`
- Test: `frontend/tests/managementCommandCenter.test.js`

- [x] Add `fetchMesSyncRuns(params)` to the MES API client.
- [x] Load recent sync runs with the dashboard surface through `Promise.allSettled`, so a failed trend endpoint does not blank the page.
- [x] Render a compact `MES 同步稳定性` strip showing success ratio, latest fetched/upserted counts, duration, and recent run bars.
- [x] Keep the UI read-only and production-oriented: no credential actions, no config mutation, no onboarding copy.
- [x] Add static frontend assertions for the API call, section label, CSS class, and no mutation action text.
- [x] Run `node --test frontend/tests/managementCommandCenter.test.js`.

### Task 3: Verify And Release

- [x] Run focused backend and frontend tests.
- [x] Run `python -m pytest backend/tests -q`.
- [x] Run `npm --prefix frontend test`.
- [x] Run `npm --prefix frontend run build`.
- [x] Run `git diff --check`.
- [ ] Commit, push, deploy, and verify production `/readyz`, `/api/v1/mes/sync-runs`, and the production `LiveDashboard` asset.
