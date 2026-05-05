# Preview WIP Route Truthfulness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep current preview and WIP audit docs from sending testers to stale `/review/*` and `/admin/*` formal routes.

**Architecture:** Do not change runtime routes. Add narrow tests for `docs/VERCEL_PREVIEW.md` and `docs/MES_WIP_DATA_AUDIT.md`, then update only those docs to use canonical `/manage/*` paths and current branch wording.

**Tech Stack:** Markdown docs and pytest contract tests.

---

### Task 1: Lock Vercel Preview Smoke Paths

**Files:**
- Modify: `backend/tests/test_quick_cloud_trial_docs_and_ops.py`

- [x] **Step 1: Add failing preview path contract**

Require `docs/VERCEL_PREVIEW.md` to identify `main` as the current branch and list current smoke paths: `/login`, `/entry`, `/manage/overview`, `/manage/ai-assistant`, `/manage/reports`, `/manage/quality`, `/manage/factory/cost`, `/manage/ingestion`, `/manage/admin/settings`, `/manage/admin/governance`, and `/manage/master`.

- [x] **Step 2: Reject stale preview paths**

Reject stale preview smoke paths `/review/brain`, `/review/cost-accounting`, `/admin/ingestion`, `/admin/ops`, `/admin/governance`, and `/admin/master`.

- [x] **Step 3: Run red test**

```powershell
python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_vercel_preview_uses_current_manage_smoke_paths -q
```

Expected: fail because the preview checklist still lists legacy paths and `ui重构`.

Result: failed as expected on the missing `main` branch line.

### Task 2: Lock WIP Audit Display Paths

**Files:**
- Modify: `backend/tests/test_reference_command_center_spec.py`

- [x] **Step 1: Add failing WIP audit path contract**

Require `docs/MES_WIP_DATA_AUDIT.md` to show WIP snapshot frontend positions as `/manage/factory`, `/manage/overview`, and `/manage/ingestion`.

- [x] **Step 2: Reject stale WIP display paths**

Reject the old exact line `前端展示位置：`/review/factory`、`/review/overview`、`/admin/ingestion``.

- [x] **Step 3: Run red test**

```powershell
python -m pytest backend/tests/test_reference_command_center_spec.py::test_mes_wip_data_audit_points_to_current_manage_surfaces -m frontend_contract -q
```

Expected: fail because the WIP audit still names legacy display paths.

Result: failed as expected on the missing `/manage/factory` display position.

### Task 3: Update Docs

**Files:**
- Modify: `docs/VERCEL_PREVIEW.md`
- Modify: `docs/MES_WIP_DATA_AUDIT.md`

- [x] **Step 1: Update preview branch and merge wording**

Change `docs/VERCEL_PREVIEW.md` to describe `main` and remove stale `ui重构` / "暂不 merge main" wording.

- [x] **Step 2: Update preview smoke paths**

Replace the legacy smoke path list with canonical `/manage/*` paths.

- [x] **Step 3: Update WIP display positions**

Replace the WIP audit frontend positions with `/manage/factory`, `/manage/overview`, and `/manage/ingestion`.

- [x] **Step 4: Run focused green tests**

```powershell
python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_vercel_preview_uses_current_manage_smoke_paths -q
python -m pytest backend/tests/test_reference_command_center_spec.py::test_mes_wip_data_audit_points_to_current_manage_surfaces -m frontend_contract -q
```

Expected: both pass.

Result: both focused tests passed.

### Task 4: Verify and Commit

**Files:**
- Modify: `docs/superpowers/plans/2026-05-06-preview-wip-route-truthfulness.md`

- [x] **Step 1: Run verification**

```powershell
python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py -q
python -m pytest backend/tests/test_reference_command_center_spec.py -m frontend_contract -q
git diff --check
```

Expected: all pass.

Result:
- `python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py -q` -> `29 passed, 1 deselected`
- `python -m pytest backend/tests/test_reference_command_center_spec.py -m frontend_contract -q` -> `37 passed`
- `git diff --check` -> pass
- Stale preview/WIP route scan -> no target legacy route matches.

- [x] **Step 2: Commit and push**

```powershell
git add backend/tests/test_quick_cloud_trial_docs_and_ops.py backend/tests/test_reference_command_center_spec.py docs/VERCEL_PREVIEW.md docs/MES_WIP_DATA_AUDIT.md docs/superpowers/plans/2026-05-06-preview-wip-route-truthfulness.md
git commit -m "docs: 更新预览与在制料审计路由"
git push
```
