# Reference AI Assistant Catalog Truthfulness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align reference module 11 with the current AI assistant runtime route and name.

**Architecture:** Keep production router unchanged. Update the reference catalog and supporting reference docs so module 11 uses `AI 助手` and `/manage/ai-assistant`, while `/review/brain` remains only a compatibility redirect described in the current route map.

**Tech Stack:** Vue reference metadata, Markdown docs, pytest frontend-contract tests.

---

### Task 1: Lock Reference Module 11 Current Contract

**Files:**
- Modify: `backend/tests/test_reference_command_center_spec.py`

- [x] **Step 1: Update catalog title expectation**

Require `AI 助手` in `frontend/src/reference-command/data/moduleCatalog.js` and reject `AI 总控中心`.

- [x] **Step 2: Update route expectation**

Require module 11 to use `routeName: 'factory-ai-assistant'` and `routePath: '/manage/ai-assistant'`.

- [x] **Step 3: Update UI spec and manifest expectations**

Require `docs/ui-replica-spec.md` row 11 and `docs/ui-reference/REFERENCE_MANIFEST.md` module 11 to say `AI 助手`.

- [x] **Step 4: Run red tests**

```powershell
python -m pytest backend/tests/test_reference_command_center_spec.py::test_reference_command_catalog_declares_15_target_modules_without_roadmap_page backend/tests/test_reference_command_center_spec.py::test_ui_replica_spec_locks_reference_module_granularity backend/tests/test_reference_command_center_spec.py::test_highres_reference_images_keep_size_budget_and_dimensions -m frontend_contract -q
```

Expected: fail because catalog/docs still say `AI 总控中心` and `/review/brain`.

Result: failed as expected with 3 failing assertions for catalog title, UI spec row 11, and reference manifest title.

### Task 2: Update Reference AI Assistant Facts

**Files:**
- Modify: `frontend/src/reference-command/data/moduleCatalog.js`
- Modify: `docs/ui-replica-spec.md`
- Modify: `docs/ui-reference/REFERENCE_MANIFEST.md`

- [x] **Step 1: Update module catalog**

Change module 11 title to `AI 助手`, routeName to `factory-ai-assistant`, routePath to `/manage/ai-assistant`, and keep the AI assistant layout/source semantics concise.

- [x] **Step 2: Update UI replica spec**

Change row 11 and route boundary wording from `/review/brain` / `AI 总控中心` to `/manage/ai-assistant` / `AI 助手`.

- [x] **Step 3: Update reference manifest**

Keep image filename `11-ai-control.png`, but label the center as `AI 助手` and update the boundary text to `/manage/ai-assistant`.

- [x] **Step 4: Run focused green tests**

```powershell
python -m pytest backend/tests/test_reference_command_center_spec.py::test_reference_command_catalog_declares_15_target_modules_without_roadmap_page backend/tests/test_reference_command_center_spec.py::test_ui_replica_spec_locks_reference_module_granularity backend/tests/test_reference_command_center_spec.py::test_highres_reference_images_keep_size_budget_and_dimensions -m frontend_contract -q
```

Expected: pass.

Result: `3 passed in 0.12s`.

### Task 3: Verify and Close

**Files:**
- Modify: `docs/superpowers/plans/2026-05-06-reference-ai-assistant-catalog-truthfulness.md`

- [x] **Step 1: Run verification**

```powershell
python -m pytest backend/tests/test_reference_command_center_spec.py -m frontend_contract -q
npm --prefix frontend test
npm --prefix frontend run build
python -m pytest backend/tests -q --durations=10
git diff --check
```

Expected: all pass.

Result:
- `python -m pytest backend/tests/test_reference_command_center_spec.py -m frontend_contract -q` -> `36 passed`
- `npm --prefix frontend test` -> `109 passed`
- `npm --prefix frontend run build` -> pass
- `python -m pytest backend/tests -q --durations=10` -> first run hit the 303s tool timeout; rerun with longer timeout passed with `649 passed, 119 deselected, 30 warnings`
- `git diff --check` -> pass
- Target source/doc stale scan -> no matches for old module 11 `AI 总控中心` / `/review/brain` reference facts.

- [x] **Step 2: Commit and push**

```powershell
git add frontend/src/reference-command/data/moduleCatalog.js docs/ui-replica-spec.md docs/ui-reference/REFERENCE_MANIFEST.md backend/tests/test_reference_command_center_spec.py docs/superpowers/plans/2026-05-06-reference-ai-assistant-catalog-truthfulness.md
git commit -m "docs: 标清参考目录 AI 助手口径"
git push
```
