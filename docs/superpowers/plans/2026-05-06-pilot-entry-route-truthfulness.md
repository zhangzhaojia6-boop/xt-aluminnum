# Pilot Entry Route Truthfulness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the current pilot SOP and readiness checklist use `/entry` as the formal field entry, with `/mobile` documented only as legacy compatibility.

**Architecture:** Keep backend `/api/v1/mobile/*` APIs and frontend `/mobile/*` redirects unchanged. Add a frontend-contract test for the two pilot docs, then update only doc wording.

**Tech Stack:** Markdown docs and pytest frontend-contract tests.

---

### Task 1: Lock Pilot Entry Route Docs

**Files:**
- Modify: `backend/tests/test_mobile_entry_copy_consistency.py`

- [x] **Step 1: Add failing pilot docs contract**

Require `docs/pilot-sop-minimal.md` and `docs/pilot-readiness-checklist.md` to describe `/entry` as the formal field entry.

- [x] **Step 2: Keep `/mobile` as compatibility only**

Require both docs to mention `/mobile` only as a legacy compatibility redirect, not as the only field entry.

- [x] **Step 3: Run red test**

```powershell
python -m pytest backend/tests/test_mobile_entry_copy_consistency.py::test_pilot_docs_use_entry_as_formal_field_route -m frontend_contract -q
```

Expected: fail because the pilot docs still say `/mobile` is the unique field entry.

Result: failed as expected on the missing `https://localhost/entry` SOP entry.

### Task 2: Update Pilot Docs

**Files:**
- Modify: `docs/pilot-sop-minimal.md`
- Modify: `docs/pilot-readiness-checklist.md`

- [x] **Step 1: Update SOP entry wording**

Use `/entry` as the formal H5 field entry and mention `/mobile` as legacy compatibility.

- [x] **Step 2: Update returned-work guidance**

Tell workers to return through `/entry` for current shift continuation.

- [x] **Step 3: Update readiness and smoke checks**

Use `/entry` as the starting point, with `/mobile` only as compatibility.

- [x] **Step 4: Run focused green test**

```powershell
python -m pytest backend/tests/test_mobile_entry_copy_consistency.py::test_pilot_docs_use_entry_as_formal_field_route -m frontend_contract -q
```

Expected: pass.

Result: `1 passed in 0.11s`.

### Task 3: Verify and Commit

**Files:**
- Modify: `docs/superpowers/plans/2026-05-06-pilot-entry-route-truthfulness.md`

- [x] **Step 1: Run verification**

```powershell
python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -m frontend_contract -q
git diff --check
```

Expected: all pass.

Result:
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -m frontend_contract -q` -> `75 passed`
- `git diff --check` -> pass
- Stale pilot `/mobile` unique-entry scan -> no target matches.

- [x] **Step 2: Commit and push**

```powershell
git add backend/tests/test_mobile_entry_copy_consistency.py docs/pilot-sop-minimal.md docs/pilot-readiness-checklist.md docs/superpowers/plans/2026-05-06-pilot-entry-route-truthfulness.md
git commit -m "docs: 更新试点现场正式填报入口"
git push
```
