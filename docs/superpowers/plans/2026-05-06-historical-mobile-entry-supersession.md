# Historical Mobile Entry Supersession Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prevent historical workflow records that mention `/mobile` as the only field entry from being mistaken for current operating guidance.

**Architecture:** Do not rewrite historical April 8 facts. Add explicit supersession wording that points to the current `/entry` formal route and documents `/mobile` as compatibility.

**Tech Stack:** Markdown docs and pytest frontend-contract tests.

---

### Task 1: Lock Historical Supersession Notes

**Files:**
- Modify: `backend/tests/test_mobile_entry_copy_consistency.py`

- [x] **Step 1: Add failing supersession contract**

Require `docs/wecom-single-entry-review-2026-04-08.md` to contain a top note saying the April 8 `/mobile` entry decision is superseded and the current formal entry is `/entry`.

- [x] **Step 2: Add workflow rollout current step contract**

Require `docs/workflow-rollout.md` to contain a new Step 9 that records `/entry` as the current formal field entry and `/mobile` as legacy compatibility.

- [x] **Step 3: Run red test**

```powershell
python -m pytest backend/tests/test_mobile_entry_copy_consistency.py::test_historical_mobile_entry_docs_are_marked_superseded -m frontend_contract -q
```

Expected: fail because the historical files do not yet point readers to the current `/entry` route.

Result: failed as expected on missing `2026-05-06 更新`.

### Task 2: Update Historical Docs

**Files:**
- Modify: `docs/wecom-single-entry-review-2026-04-08.md`
- Modify: `docs/workflow-rollout.md`

- [x] **Step 1: Add supersession note to review record**

Add a short top note that preserves the historical record but points current readers to `/entry`.

- [x] **Step 2: Append workflow rollout Step 9**

Add a dated Step 9 summarizing the `/entry` formal route refresh and the updated pilot docs.

- [x] **Step 3: Run focused green test**

```powershell
python -m pytest backend/tests/test_mobile_entry_copy_consistency.py::test_historical_mobile_entry_docs_are_marked_superseded -m frontend_contract -q
```

Expected: pass.

Result: `1 passed in 0.14s`.

### Task 3: Verify and Commit

**Files:**
- Modify: `docs/superpowers/plans/2026-05-06-historical-mobile-entry-supersession.md`

- [x] **Step 1: Run verification**

```powershell
python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -m frontend_contract -q
git diff --check
```

Expected: all pass.

Result:
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -m frontend_contract -q` -> `76 passed`
- `git diff --check` -> pass

- [x] **Step 2: Commit and push**

```powershell
git add backend/tests/test_mobile_entry_copy_consistency.py docs/wecom-single-entry-review-2026-04-08.md docs/workflow-rollout.md docs/superpowers/plans/2026-05-06-historical-mobile-entry-supersession.md
git commit -m "docs: 标记历史移动入口口径已覆盖"
git push
```
