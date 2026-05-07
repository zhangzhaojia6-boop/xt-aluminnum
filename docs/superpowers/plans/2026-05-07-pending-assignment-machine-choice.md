# Pending Assignment Machine Choice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let managers choose a machine line for pending fill rows when a workshop has multiple candidates, then run the existing binding entry action.

**Architecture:** Extend the existing pending-assignment detail contract with candidate machine ids and names. Keep the backend action guarded: it still requires an explicit machine id when candidates are ambiguous. The review table renders a compact machine selector only for pending rows that need it.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, Vue 3, Element Plus, pytest, node test runner.

---

## Task 1: Candidate Contract

**Files:**
- Modify: `backend/app/services/realtime_service.py`
- Modify: `backend/app/schemas/realtime.py`
- Test: `backend/tests/test_realtime_service.py`

- [x] Add `machine_candidates: [{ machine_id, machine_name }]` to pending-assignment rows.
- [x] Keep `machine_candidate_count` and `machine_candidate_names` for compatibility.
- [x] Verify the existing pending-assignment service test expects the new candidate list.

## Task 2: Review Table Selector

**Files:**
- Modify: `frontend/src/views/review/ReviewTaskCenter.vue`
- Test: `frontend/tests/reviewTaskCenter.test.js`

- [x] Preserve one-click `绑定入账` for rows with MES machine or exactly one candidate.
- [x] For multiple candidates, show a compact `el-select` and pass the selected `machine_id` to `promote_draft_entry`.
- [x] Keep the action disabled until a machine is selected.

## Task 3: Verification And Release

- [x] Run `python -m pytest backend/tests/test_realtime_service.py backend/tests/test_realtime_routes.py backend/tests/test_assistant_action_service.py -q`.
- [x] Run `npm --prefix frontend test`.
- [x] Run `npm --prefix frontend run build`.
- [x] Run `git diff --check`.
- [ ] Commit, push, deploy, then verify production pending rows expose candidate ids and the front-end asset contains the selector/action markers.
