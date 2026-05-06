# Daily Production Management Preview Implementation Plan

> **For agentic workers:** Keep this change small. The goal is visibility, not formal production posting.

**Goal:** Surface the read-only daily production mapping gate in the management import history page so admins can see whether a staged `daily_production_report` is ready before any `ShiftProductionData` write.

**Architecture:** Reuse `daily_production_mapping_service`. Add a read-only imports route that returns the latest or selected mapping preview. Frontend loads it beside import history and renders compact status bars plus unresolved labels. No formal production rows are created or changed.

**Tech Stack:** FastAPI, Pydantic schemas, Vue 3, existing imports API, frontend node tests, pytest.

---

### Task 1: Backend API Contract

**Files:**
- Modify: `backend/app/schemas/imports.py`
- Modify: `backend/app/routers/imports.py`
- Create: `backend/tests/test_imports_daily_production_mapping_preview_route.py`

- [x] Add Pydantic response models for mapping rows and preview.
- [x] Add `GET /api/v1/imports/daily-production/mapping-preview?batch_id=...`.
- [x] Test that the route returns `ready_rows`, `unresolved_rows`, unresolved labels, and does not require a write path.

### Task 2: Management UI Preview

**Files:**
- Modify: `frontend/src/api/imports.js`
- Modify: `frontend/src/views/imports/ImportHistory.vue`
- Create: `frontend/tests/importHistoryPreview.test.js`

- [x] Add `fetchDailyProductionMappingPreview(batchId)`.
- [x] In `ImportHistory.vue`, find the newest `daily_production_report` batch and render the mapping preview above the table.
- [x] Use compact production-workbench styling: status strip, counts, unresolved labels; no explanatory marketing copy.

### Task 3: Verification And Deploy

- [x] `python -m pytest backend/tests/test_imports_daily_production_mapping_preview_route.py backend/tests/test_daily_production_mapping_service.py backend/tests/test_quick_cloud_trial_docs_and_ops.py -q`：38 passed，1 deselected
- [x] `node --test frontend/tests/importHistoryPreview.test.js`：1 passed
- [x] `npm --prefix frontend run build`：passed
- [x] `python -m pytest backend/tests -q`：719 passed，124 deselected，31 warnings
- [x] `npm --prefix frontend test`：120 passed
- [x] `git diff --check`：passed with Windows LF/CRLF warnings only
- [ ] Commit, push, pull production, verify `/readyz`.
