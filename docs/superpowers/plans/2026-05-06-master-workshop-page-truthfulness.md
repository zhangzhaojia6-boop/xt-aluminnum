# Master Workshop Page Truthfulness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `/manage/master` truthfully present the current runtime surface as workshop master data, while keeping the broader master/template center and routes unchanged.

**Architecture:** Keep `Workshop.vue` on the existing `/api/v1/master/workshops` CRUD path. Adjust only the visible page title/tags and route documentation so the page no longer implies 班组、员工、机台和模板 are all handled in this runtime view. Existing navigation can remain broad because it groups related master/template surfaces.

**Tech Stack:** Vue 3, Element Plus, node source-contract tests, pytest frontend-contract tests, Markdown docs.

---

### Task 1: Lock the Current Runtime Page Scope

**Files:**
- Modify: `frontend/tests/workshopFormValidation.test.js`
- Modify: `backend/tests/test_reference_command_center_spec.py`

- [x] **Step 1: Add frontend source-contract red test**

Add a node test that reads `frontend/src/views/master/Workshop.vue` and asserts:

```js
assert.match(workshopPageSource, /title="车间主数据"/)
assert.match(workshopPageSource, /:tags="\['车间清单', '新增编辑删除', '主数据治理'\]"/)
assert.doesNotMatch(workshopPageSource, /title="主数据与模板中心"/)
assert.doesNotMatch(workshopPageSource, /班组员工/)
assert.doesNotMatch(workshopPageSource, /机台班次/)
```

- [x] **Step 2: Add backend frontend-contract red test**

Extend `test_master_route_docs_match_live_workshop_center()` to assert `Workshop.vue` uses `title="车间主数据"` and does not advertise `班组员工` or `机台班次`.

- [x] **Step 3: Run red tests**

Run:

```powershell
npm --prefix frontend test -- tests/workshopFormValidation.test.js
python -m pytest backend/tests/test_reference_command_center_spec.py::test_master_route_docs_match_live_workshop_center -m frontend_contract -q
```

Expected: both fail because `Workshop.vue` still says `主数据与模板中心` and broad tags.

Result before implementation:

- `npm --prefix frontend test -- tests/workshopFormValidation.test.js`: FAIL, `Workshop page labels the runtime surface as workshop master data`.
- `python -m pytest backend/tests/test_reference_command_center_spec.py::test_master_route_docs_match_live_workshop_center -m frontend_contract -q`: FAIL, `title="车间主数据"` missing.

### Task 2: Correct the Visible Page Contract

**Files:**
- Modify: `frontend/src/views/master/Workshop.vue`
- Modify: `docs/current-route-map.md`

- [x] **Step 1: Update `Workshop.vue` title and tags**

Change the page frame to:

```vue
title="车间主数据"
:tags="['车间清单', '新增编辑删除', '主数据治理']"
```

- [x] **Step 2: Update route map wording**

Keep `/manage/master` and route names unchanged, but update the `/admin/master` line to say the runtime page is the workshop master-data surface under the broader master/template center.

- [x] **Step 3: Run focused green tests**

Run:

```powershell
npm --prefix frontend test -- tests/workshopFormValidation.test.js
python -m pytest backend/tests/test_reference_command_center_spec.py::test_master_route_docs_match_live_workshop_center -m frontend_contract -q
```

Expected: both pass.

Result after implementation:

- `npm --prefix frontend test -- tests/workshopFormValidation.test.js`: PASS, `109 passed`.
- `python -m pytest backend/tests/test_reference_command_center_spec.py::test_master_route_docs_match_live_workshop_center -m frontend_contract -q`: PASS, `1 passed`.

### Task 3: Verify and Close

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`
- Modify: `docs/superpowers/plans/2026-05-06-master-workshop-page-truthfulness.md`

- [x] **Step 1: Add audit row**

Add a fixed row documenting that `/manage/master` no longer overpromises the whole master/template center in the runtime page header.

- [x] **Step 2: Run full relevant verification**

Run:

```powershell
python -m pytest backend/tests/test_reference_command_center_spec.py -m frontend_contract -q
npm --prefix frontend test
npm --prefix frontend run build
python -m pytest backend/tests -q --durations=10
git diff --check
```

Expected: all pass.

Verification results:

- `python -m pytest backend/tests/test_reference_command_center_spec.py -m frontend_contract -q`: PASS, `36 passed`.
- `npm --prefix frontend test`: PASS, `109 passed`.
- `npm --prefix frontend run build`: PASS.
- `python -m pytest backend/tests -q --durations=10`: PASS, `646 passed, 119 deselected, 30 warnings`.
- `git diff --check`: PASS.

- [x] **Step 3: Commit and push**

Run:

```powershell
git add frontend/src/views/master/Workshop.vue frontend/tests/workshopFormValidation.test.js backend/tests/test_reference_command_center_spec.py docs/current-route-map.md docs/audits/2026-05-02-cleanup-round2-test-audit.md docs/superpowers/plans/2026-05-06-master-workshop-page-truthfulness.md
git commit -m "fix: 标清车间主数据页面口径"
git push
```
