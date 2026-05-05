# Operational Docs Route Truthfulness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Align current operational docs with the canonical `/entry` and `/manage/*` route surfaces.

**Architecture:** Keep runtime routing unchanged. Add a narrow pytest contract for the three current operational docs, then update only route wording and compatibility notes.

**Tech Stack:** Markdown docs and pytest contract tests.

---

### Task 1: Lock Operational Route Docs

**Files:**
- Modify: `backend/tests/test_quick_cloud_trial_docs_and_ops.py`

- [x] **Step 1: Add failing docs route contract**

Require:
- `docs/launch-readiness-checklist.md` to list `/manage/overview`, `/manage/factory`, and `/manage/workshop`.
- `docs/企业微信生产入口准备清单.md` to use `/entry` and `/manage/factory` as formal browser entries.
- `docs/供应商对接手册-前端重构版.md` to use `/manage/overview`, `/manage/factory`, and `/manage/workshop` as formal review/operations entries.

- [x] **Step 2: Reject stale formal route lines**

Reject exact old lines that present `/review/overview`, `/review/factory`, `/review/workshop`, or `/mobile` as formal operational entry points.

- [x] **Step 3: Run red test**

```powershell
python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_operational_docs_use_current_entry_and_manage_routes -q
```

Expected: fail because the current docs still list stale formal entries.

Result: failed as expected on the missing `/manage/overview` readiness row.

### Task 2: Update Operational Docs

**Files:**
- Modify: `docs/launch-readiness-checklist.md`
- Modify: `docs/企业微信生产入口准备清单.md`
- Modify: `docs/供应商对接手册-前端重构版.md`

- [x] **Step 1: Update launch readiness paths**

Replace review center readiness lines with `/manage/overview`, `/manage/factory`, and `/manage/workshop`; keep legacy paths only in compatibility wording.

- [x] **Step 2: Update formal identity entry paths**

Use `/entry` and `/manage/factory` as formal browser entries, and mention `/mobile` only as legacy compatibility if needed.

- [x] **Step 3: Update supplier handoff paths**

Use `/manage/overview`, `/manage/factory`, and `/manage/workshop` as formal review/operations entries; update compatibility and joint-debug suggestions.

- [x] **Step 4: Run focused green test**

```powershell
python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_operational_docs_use_current_entry_and_manage_routes -q
```

Expected: pass.

Result: `1 passed in 0.11s`.

### Task 3: Verify and Commit

**Files:**
- Modify: `docs/superpowers/plans/2026-05-06-operational-docs-route-truthfulness.md`

- [x] **Step 1: Run verification**

```powershell
python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py -q
git diff --check
```

Expected: all pass.

Result:
- `python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py -q` -> `30 passed, 1 deselected`
- `git diff --check` -> pass
- Stale operational route scan -> no target legacy formal route matches.

- [x] **Step 2: Commit and push**

```powershell
git add backend/tests/test_quick_cloud_trial_docs_and_ops.py docs/launch-readiness-checklist.md docs/企业微信生产入口准备清单.md docs/供应商对接手册-前端重构版.md docs/superpowers/plans/2026-05-06-operational-docs-route-truthfulness.md
git commit -m "docs: 更新运营入口文档正式路由"
git push
```
