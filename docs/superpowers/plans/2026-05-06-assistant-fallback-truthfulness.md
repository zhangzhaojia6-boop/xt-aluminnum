# Assistant Fallback Truthfulness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop AI assistant fallback capabilities from presenting deterministic mock mode as online/live-ready capability.

**Architecture:** Keep assistant routes and quick actions available. Change capability metadata and derived UI counts: when LLM is not configured or the frontend capability request falls back, report `connected=false`, no live capability keys, planned integrations, and neutral summary cards; live mode keeps the existing ready state.

**MES and Rule Context:** MES is still external and unconfigured locally. This change follows the same source-truth rule used by factory-command: fallback/read-model data can keep the UI usable, but it must be labeled as fallback instead of live production capability.

**Tech Stack:** FastAPI service tests, frontend static node tests, Markdown audit ledger.

---

### Task 1: Add Red Tests

**Files:**
- Modify: `backend/tests/test_assistant_routes.py`
- Create: `frontend/tests/assistantFallbackTruthfulness.test.js`

- [x] **Step 1: Backend fallback contract red test**

Update the mock capability test to require:
- `connected is False`
- integrations use `planned`
- no live capability keys are advertised
- summary cards report `0 / 0 / 未联通` instead of `3 / 3 / 在线`

Run:

```powershell
python -m pytest backend/tests/test_assistant_routes.py::test_assistant_capabilities_returns_deterministic_mock_contract -q
```

Expected before implementation: FAIL because backend currently returns `connected=True` and `在线`.

- [x] **Step 2: Frontend fallback red test**

Add a static node test that requires `frontend/src/api/assistant.js` fallback to avoid `mock_ready` integration statuses, live capability keys, and `value: '在线'`.

Run:

```powershell
npm --prefix frontend test -- tests/assistantFallbackTruthfulness.test.js
```

Expected before implementation: FAIL because frontend fallback currently advertises `mock_ready`, capability keys, and `在线`.

### Task 2: Implement Truthful Fallback

**Files:**
- Modify: `backend/app/services/assistant_service.py`
- Modify: `frontend/src/api/assistant.js`
- Modify: `frontend/src/components/review/ReviewAssistantDock.vue`
- Modify: `frontend/src/components/review/ReviewAssistantWorkbench.vue`

- [x] **Step 1: Backend capability metadata**

When `_llm_ready(runtime)` is false:
- set `connected=False`
- set integration status to `planned`
- return an empty capability list
- set summary values to `0`, `0`, and `未联通`

When live mode is ready, preserve the current `live` behavior.

- [x] **Step 2: Frontend fallback metadata**

Mirror the same metadata in `buildAssistantFallback()` so API failures do not show online capability. Keep workbench and dock counts derived from live/connected capability state instead of planned integration length.

### Task 3: Audit And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Add resolved audit row**

Add `R78` describing AI fallback capability truthfulness.

- [x] **Step 2: Run verification**

Run:

```powershell
python -m pytest backend/tests/test_assistant_routes.py -q
npm --prefix frontend test
python -m pytest backend/tests -q
npm --prefix frontend run build
git diff --check
```

Expected: all commands pass. Existing CRLF warnings are acceptable only when exit code is 0.

Actual:
- `python -m pytest backend/tests/test_assistant_routes.py -q` -> `13 passed`
- `npm --prefix frontend test` -> `107 passed`
- `python -m pytest backend/tests -q` -> `646 passed, 119 deselected, 30 warnings`
- `python -m pytest backend/tests -m frontend_contract -q` -> `119 passed, 646 deselected`
- `npm --prefix frontend run build` -> passed
- `git diff --check` -> exit 0 with existing CRLF warnings
