# Refactor Blueprint Route Truthfulness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `docs/REFACTOR_BLUEPRINT.md` describe the current canonical `/manage/*` route architecture instead of stale `/review/*` and `/admin/*` formal center paths.

**Architecture:** Keep production router, navigation, and runtime pages unchanged. Add a frontend-contract test that locks the blueprint to the current route map, then update only the blueprint wording.

**Tech Stack:** Markdown docs and pytest frontend-contract tests.

---

### Task 1: Lock Blueprint Route Facts

**Files:**
- Modify: `backend/tests/test_frontend_refactor_blueprint.py`

- [x] **Step 1: Add failing blueprint contract**

Add a test that requires `docs/REFACTOR_BLUEPRINT.md` to list `/manage/overview`, `/manage/factory`, `/manage/ingestion`, `/manage/entry-center`, `/manage/reports`, `/manage/quality`, `/manage/factory/cost`, `/manage/ai-assistant`, `/manage/admin/settings`, `/manage/admin/governance`, and `/manage/master` as formal routes.

- [x] **Step 2: Reject stale formal paths and title**

The same test must reject stale formal blueprint rows that present `/review/overview`, `/review/factory`, `/review/tasks`, `/review/reports`, `/review/quality`, `/review/cost-accounting`, `/review/brain`, `/admin/ingestion`, `/admin/ops`, `/admin/governance`, or `/admin/master` as center paths. It should still allow those legacy paths inside compatibility redirects.

- [x] **Step 3: Run red test**

```powershell
python -m pytest backend/tests/test_frontend_refactor_blueprint.py::test_refactor_blueprint_documents_canonical_manage_routes -m frontend_contract -q
```

Expected: fail because `docs/REFACTOR_BLUEPRINT.md` still presents legacy paths as formal routes.

Result: failed as expected on the missing `/manage/overview` route row.

### Task 2: Update Blueprint

**Files:**
- Modify: `docs/REFACTOR_BLUEPRINT.md`

- [x] **Step 1: Update information architecture sections**

Change the review and admin formal route lists to canonical `/manage/*` routes while preserving entry and login routes.

- [x] **Step 2: Update center list**

Change centers 01, 05-14 to current names and `/manage/*` paths, including `AI 助手` and `/manage/ai-assistant`.

- [x] **Step 3: Update compatibility section**

Keep legacy paths only as redirects to `/manage/*`, including `/dashboard/*` -> `/manage/*`, `/master/*` -> `/manage/*`, `/review/*` -> `/manage/*`, and `/admin/*` -> `/manage/*`.

- [x] **Step 4: Run focused green test**

```powershell
python -m pytest backend/tests/test_frontend_refactor_blueprint.py::test_refactor_blueprint_documents_canonical_manage_routes -m frontend_contract -q
```

Expected: pass.

Result: `1 passed in 0.13s`.

### Task 3: Verify and Commit

**Files:**
- Modify: `docs/superpowers/plans/2026-05-06-refactor-blueprint-route-truthfulness.md`

- [x] **Step 1: Run verification**

```powershell
python -m pytest backend/tests/test_frontend_refactor_blueprint.py -m frontend_contract -q
git diff --check
```

Expected: all pass.

Result:
- `python -m pytest backend/tests/test_frontend_refactor_blueprint.py -m frontend_contract -q` -> `8 passed`
- `git diff --check` -> pass
- Stale formal route scan -> no old blueprint formal route or redirect matches.

- [x] **Step 2: Commit and push**

```powershell
git add backend/tests/test_frontend_refactor_blueprint.py docs/REFACTOR_BLUEPRINT.md docs/superpowers/plans/2026-05-06-refactor-blueprint-route-truthfulness.md
git commit -m "docs: 更新前端重构蓝图正式路由"
git push
```
