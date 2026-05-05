# Known Gaps Current State Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep `docs/known-gaps-and-todos.md` aligned with the current verified E2E and master-data runtime state.

**Architecture:** This is a documentation truthfulness pass with static tests. Do not change runtime code. Use backend doc-contract tests to prevent stale E2E counts and overbroad master-center wording from returning.

**Tech Stack:** pytest doc-contract tests, Markdown docs.

---

### Task 1: Lock Known-Gaps Current-State Claims

**Files:**
- Modify: `backend/tests/test_quick_cloud_trial_docs_and_ops.py`

- [x] **Step 1: Add E2E baseline doc-contract test**

Assert `docs/known-gaps-and-todos.md` no longer contains the stale `13 条前端 e2e` text and does mention the current Playwright spec file baseline.

- [x] **Step 2: Add master runtime scope doc-contract test**

Assert known-gaps says `/manage/master` is currently labeled as `车间主数据`, while one-stop master/template coverage remains future scope.

- [x] **Step 3: Run red test**

```powershell
python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_known_gaps_e2e_baseline_reflects_current_playwright_specs backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_known_gaps_master_runtime_scope_matches_workshop_page -q
```

Expected: fail against the stale known-gaps document.

Result before implementation: FAIL, stale `13 条前端 e2e` text remained and `/manage/master` was not documented as `车间主数据`.

### Task 2: Refresh Known-Gaps Document

**Files:**
- Modify: `docs/known-gaps-and-todos.md`

- [x] **Step 1: Update E2E gap wording**

Replace the old `13 条前端 e2e` sentence with the current `20 个 Playwright spec 文件` baseline and note that new E2E work should keep using existing mock helpers.

- [x] **Step 2: Update master gap wording**

Add that `/manage/master` now labels the runtime surface as `车间主数据`; one-stop master/template coverage remains future scope.

- [x] **Step 3: Run green target test**

```powershell
python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_known_gaps_e2e_baseline_reflects_current_playwright_specs backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_known_gaps_master_runtime_scope_matches_workshop_page -q
```

Expected: pass.

Result after implementation: PASS, `2 passed`.

### Task 3: Verify and Close

**Files:**
- Modify: `docs/superpowers/plans/2026-05-06-known-gaps-current-state-refresh.md`

- [x] **Step 1: Run verification**

```powershell
python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py -q
python -m pytest backend/tests -q --durations=10
git diff --check
```

Expected: all pass.

Verification results:

- `python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py -q`: PASS, `27 passed, 1 deselected`.
- `python -m pytest backend/tests -q --durations=10`: PASS, `648 passed, 119 deselected, 30 warnings`.
- `git diff --check`: PASS.

- [x] **Step 2: Commit and push**

```powershell
git add backend/tests/test_quick_cloud_trial_docs_and_ops.py docs/known-gaps-and-todos.md docs/superpowers/plans/2026-05-06-known-gaps-current-state-refresh.md
git commit -m "docs: 刷新已知缺口当前状态"
git push
```
