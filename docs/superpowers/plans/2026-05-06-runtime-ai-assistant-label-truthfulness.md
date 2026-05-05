# Runtime AI Assistant Label Truthfulness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove stale `AI 总控中心` naming from active command surface data and the overview page AI entry.

**Architecture:** Keep the compatibility route name `review-brain-center` in router/config only. Runtime-facing module data and overview entry points should use the canonical `AI 助手` label and navigate to `factory-ai-assistant`.

**Tech Stack:** FastAPI service tests, Vue static contract tests, Vue source metadata.

---

### Task 1: Lock Backend Command Surface Label

**Files:**
- Modify: `backend/tests/test_command_routes.py`

- [x] **Step 1: Add review module 11 assertion**

Assert `/api/v1/command/surface/review` returns module `11` with title `AI 助手`, and does not return `AI 总控中心`.

- [x] **Step 2: Run backend red test**

```powershell
python -m pytest backend/tests/test_command_routes.py::test_command_review_surface_is_surface_scoped -q
```

Expected: fail because `backend/app/services/command_service.py` still returns `AI 总控中心`.

Result: failed as expected on module `11` title, returning `AI 总控中心` instead of `AI 助手`.

### Task 2: Lock Overview AI Entry

**Files:**
- Modify: `frontend/tests/aiAssistantUiContract.test.js`

- [x] **Step 1: Add overview source assertion**

Assert `OverviewCenter.vue` uses `AI 助手`, uses `factory-ai-assistant`, and does not contain stale `AI 总控中心`, `review-brain-center`, or AI action-generation copy.

- [x] **Step 2: Run frontend red test**

```powershell
npm --prefix frontend test -- aiAssistantUiContract.test.js
```

Expected: fail because `OverviewCenter.vue` still contains `AI 总控中心` and `review-brain-center` entry points.

Result: failed as expected on missing `AI 助手`, stale overview AI route/copy, and AI action-generation copy.

### Task 3: Update Runtime Sources

**Files:**
- Modify: `backend/app/services/command_service.py`
- Modify: `frontend/src/views/review/OverviewCenter.vue`

- [x] **Step 1: Update backend command module**

Change module `11` title to `AI 助手`, keeping status text limited to assistant guidance and source visibility.

- [x] **Step 2: Update overview AI copy and route target**

Change overview module 11 title/short title and AI quick entry to `AI 助手`; use route name `factory-ai-assistant` for overview entry points that open the canonical AI assistant.

- [x] **Step 3: Run focused green tests**

```powershell
python -m pytest backend/tests/test_command_routes.py::test_command_review_surface_is_surface_scoped -q
npm --prefix frontend test -- aiAssistantUiContract.test.js
```

Expected: pass.

Result:
- `python -m pytest backend/tests/test_command_routes.py::test_command_review_surface_is_surface_scoped -q` -> `1 passed`
- `npm --prefix frontend test -- tests/aiAssistantUiContract.test.js` -> `110 passed` because the package script also expands `tests/*.test.js`

### Task 4: Verify and Close

**Files:**
- Modify: `docs/superpowers/plans/2026-05-06-runtime-ai-assistant-label-truthfulness.md`

- [x] **Step 1: Run verification**

```powershell
python -m pytest backend/tests/test_command_routes.py backend/tests/test_reference_command_center_spec.py -m "not slow" -q
npm --prefix frontend test
npm --prefix frontend run build
git diff --check
```

Expected: all pass.

Result:
- `python -m pytest backend/tests/test_command_routes.py backend/tests/test_reference_command_center_spec.py -m "not slow" -q` -> `40 passed`
- `npm --prefix frontend test` -> `110 passed`
- `npm --prefix frontend run build` -> pass
- `git diff --check` -> pass
- Target runtime stale scan -> no stale `AI 总控中心` or `review-brain-center` in runtime files, only test negative assertions.

- [x] **Step 2: Commit and push**

```powershell
git add backend/tests/test_command_routes.py frontend/tests/aiAssistantUiContract.test.js backend/app/services/command_service.py frontend/src/views/review/OverviewCenter.vue docs/superpowers/plans/2026-05-06-runtime-ai-assistant-label-truthfulness.md
git commit -m "fix: 统一运行链路 AI 助手口径"
git push
```
