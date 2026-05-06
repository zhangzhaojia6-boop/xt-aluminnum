# Daily Production Mapping Candidates Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add read-only candidate master-data hints for unresolved daily production rows so admins can confirm mappings without writing formal production facts.

**Architecture:** Reuse the existing daily production mapping preview. Keep hard mapping rules unchanged, and add candidate lists derived from active `Workshop` and `Equipment` names/codes/types. The management import history card displays candidate codes next to unresolved labels; no `ShiftProductionData` rows are created or modified.

**Tech Stack:** FastAPI service dataclasses, Pydantic schemas, Vue 3 import history view, pytest, node test.

---

### Task 1: Backend Candidate Contract

**Files:**
- Modify: `backend/app/services/daily_production_mapping_service.py`
- Modify: `backend/app/schemas/imports.py`
- Modify: `backend/tests/test_daily_production_mapping_service.py`
- Modify: `backend/tests/test_imports_daily_production_mapping_preview_route.py`

- [x] Add a `MappingCandidate` dataclass and `candidate_workshops` / `candidate_equipment` fields on unresolved preview rows.
- [x] Match candidates only from active master data using normalized label tokens; do not change `DAILY_PRODUCTION_MAPPING_RULES`.
- [x] Test that unresolved `精整/纵剪` exposes `JZ` workshop and `JZ-ZJ1` equipment candidates.
- [x] Test that route JSON includes candidate lists.

### Task 2: Management UI Candidate Display

**Files:**
- Modify: `frontend/src/views/imports/ImportHistory.vue`
- Modify: `frontend/tests/importHistoryPreview.test.js`

- [x] Render unresolved labels with compact candidate summaries: `车间 ...` and `机列 ...`.
- [x] Keep the card dense and operational; no onboarding or explanatory copy.
- [x] Add frontend contract assertions for `candidate_workshops`, `candidate_equipment`, and candidate summary rendering.

### Task 3: Verification And Deploy

- [x] `python -m pytest backend/tests/test_daily_production_mapping_service.py backend/tests/test_imports_daily_production_mapping_preview_route.py -q` -> 4 passed.
- [x] `node --test frontend/tests/importHistoryPreview.test.js` -> 1 passed.
- [x] `npm --prefix frontend test` -> 121 passed.
- [x] `npm --prefix frontend run build` -> passed.
- [x] `python -m pytest backend/tests -q` -> 721 passed, 124 deselected, 31 warnings.
- [x] `git diff --check` -> passed with Windows LF/CRLF warnings only.
- [x] Commit, push, deploy, verify `/readyz`, and probe production preview candidate counts read-only -> `main@c880265` deployed; `/readyz` ready with `mes_sync last_run_status=success`, `fetched_count=50`, `upserted_count=50`; production preview returned `total_rows=16`, `ready_rows=7`, `unresolved_rows=9`, `candidate_rows=9`.
