# Reference Canonical Manage Route Truthfulness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align reference specs and audit docs with the current canonical `/manage/*` runtime routes.

**Architecture:** Keep production router unchanged. `docs/current-route-map.md` already documents `/review/*` and `/admin/*` as compatibility entrances; this plan makes `frontend/src/reference-command/data/moduleCatalog.js`, `docs/ui-replica-spec.md`, `docs/ui-reference/REFERENCE_MANIFEST.md`, and `docs/CODEBASE_AUDIT.md` stop presenting those legacy paths as formal center routes.

**Tech Stack:** Markdown docs and pytest frontend-contract tests.

---

### Task 1: Lock UI Replica Spec Canonical Routes

**Files:**
- Modify: `backend/tests/test_reference_command_center_spec.py`

- [x] **Step 1: Update module matrix expectations**

Require module rows 01, 05-10, and 12-14 in `docs/ui-replica-spec.md` to use the canonical `/manage/*` paths from `docs/current-route-map.md`.

- [x] **Step 1a: Update reference catalog expectations**

Require module `routePath` values in `frontend/src/reference-command/data/moduleCatalog.js` to use the same canonical `/manage/*` paths, while keeping route names unchanged.

- [x] **Step 2: Reject stale formal route rows**

Reject the old formal rows that use `/review/overview`, `/review/factory`, `/review/tasks`, `/review/reports`, `/review/quality`, `/review/cost-accounting`, `/admin/ingestion`, `/admin/ops`, `/admin/governance`, and `/admin/master`.

- [x] **Step 3: Run red test**

```powershell
python -m pytest backend/tests/test_reference_command_center_spec.py::test_ui_replica_spec_locks_reference_module_granularity -m frontend_contract -q
```

Expected: fail because the spec and reference catalog still present legacy routes as formal center paths.

Result: failed as expected on the first stale matrix row, with remaining stale formal rows covered by negative assertions.

Catalog result: failed as expected on `routePath: '/manage/overview'` before updating `moduleCatalog.js`.

### Task 2: Lock Reference Manifest and Audit Route Wording

**Files:**
- Modify: `backend/tests/test_reference_command_center_spec.py`

- [x] **Step 1: Add manifest canonical route assertions**

Require `docs/ui-reference/REFERENCE_MANIFEST.md` to name `/manage/master`, `/manage/admin/settings`, and `/manage/admin/governance` for formal admin surfaces.

- [x] **Step 2: Add audit stale wording rejection**

Reject `数据接入中心归属 /admin/ingestion` in `docs/CODEBASE_AUDIT.md`.

- [x] **Step 3: Run red tests**

```powershell
python -m pytest backend/tests/test_reference_command_center_spec.py::test_highres_reference_images_keep_size_budget_and_dimensions backend/tests/test_reference_command_center_spec.py::test_route_docs_match_live_centers_not_legacy_center_mocks -m frontend_contract -q
```

Expected: fail because manifest and audit docs still describe formal admin surfaces with legacy `/admin/*` paths.

Result: failed as expected on manifest current priority page and `CODEBASE_AUDIT.md` data ingestion wording.

### Task 3: Update Docs

**Files:**
- Modify: `frontend/src/reference-command/data/moduleCatalog.js`
- Modify: `docs/ui-replica-spec.md`
- Modify: `docs/ui-reference/REFERENCE_MANIFEST.md`
- Modify: `docs/CODEBASE_AUDIT.md`

- [x] **Step 1: Update reference catalog and UI replica module matrix**

Change formal center paths to `/manage/overview`, `/manage/factory`, `/manage/ingestion`, `/manage/entry-center`, `/manage/reports`, `/manage/quality`, `/manage/factory/cost`, `/manage/admin/settings`, `/manage/admin/governance`, and `/manage/master` plus `/manage/admin/templates`.

- [x] **Step 2: Update UI replica route boundary lists**

Use `/manage/*` in the review/admin route lists, and keep `/review/*` and `/admin/*` only in the compatibility rules.

- [x] **Step 3: Update reference manifest and audit wording**

Change the manifest current priority page and admin surface boundary bullets to canonical `/manage/*` paths. Update `CODEBASE_AUDIT.md` so data ingestion is formal `/manage/ingestion` while `/admin/ingestion` is compatibility.

- [x] **Step 4: Run focused green tests**

```powershell
python -m pytest backend/tests/test_reference_command_center_spec.py::test_ui_replica_spec_locks_reference_module_granularity backend/tests/test_reference_command_center_spec.py::test_highres_reference_images_keep_size_budget_and_dimensions backend/tests/test_reference_command_center_spec.py::test_route_docs_match_live_centers_not_legacy_center_mocks -m frontend_contract -q
```

Expected: pass.

Result: `3 passed in 0.14s`.

Catalog result:
- `python -m pytest backend/tests/test_reference_command_center_spec.py::test_reference_command_catalog_declares_15_target_modules_without_roadmap_page -m frontend_contract -q` -> `1 passed`

### Task 4: Verify and Close

**Files:**
- Modify: `docs/superpowers/plans/2026-05-06-reference-canonical-manage-route-truthfulness.md`

- [x] **Step 1: Run verification**

```powershell
python -m pytest backend/tests/test_reference_command_center_spec.py -m frontend_contract -q
python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py -q
npm --prefix frontend test
npm --prefix frontend run build
git diff --check
```

Expected: all pass.

Result:
- `python -m pytest backend/tests/test_reference_command_center_spec.py -m frontend_contract -q` -> `36 passed`
- `python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py -q` -> `28 passed, 1 deselected`
- `npm --prefix frontend test` -> `110 passed`
- `npm --prefix frontend run build` -> pass
- `git diff --check` -> pass
- Catalog stale `routePath` scan -> no stale `/review/*` or `/admin/*` formal catalog path matches.
- Stale formal route scan -> no target matrix/manifest/audit stale formal route matches; remaining `/admin/master` text outside target docs is compatibility/API context.

- [x] **Step 2: Commit and push**

```powershell
git add frontend/src/reference-command/data/moduleCatalog.js backend/tests/test_reference_command_center_spec.py docs/ui-replica-spec.md docs/ui-reference/REFERENCE_MANIFEST.md docs/CODEBASE_AUDIT.md docs/superpowers/plans/2026-05-06-reference-canonical-manage-route-truthfulness.md
git commit -m "docs: 统一参考规范正式管理路由"
git push
```
