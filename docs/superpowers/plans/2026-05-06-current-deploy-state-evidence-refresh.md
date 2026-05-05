# Current Deploy State Evidence Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refresh deployment and audit evidence so readiness documents match the current `main` state after frontend contract marker isolation.

**Architecture:** Keep runtime behavior unchanged. Add static documentation guards first, then update only the verification evidence in `docs/deploy/current-state.md` and the cleanup audit test-record section.

**MES and Rule Context:** This is evidence hygiene only. The local environment still has no usable MES credentials; current-state should continue to treat Vercel as frontend-only evidence and external MES as unconfigured locally.

**Tech Stack:** Markdown docs, pytest static guard.

---

### Task 1: Add Red Evidence Guard

**Files:**
- Modify: `backend/tests/test_quick_cloud_trial_docs_and_ops.py`
- Create: `docs/superpowers/plans/2026-05-06-current-deploy-state-evidence-refresh.md`

- [x] **Step 1: Update expected current-state evidence**

Require `docs/deploy/current-state.md` to include:
- default backend suite: `646 passed, 119 deselected, 30 warnings`
- frontend contract suite: `119 passed, 646 deselected`
- frontend node tests: `106 passed`
- frontend build and diff-check pass

- [x] **Step 2: Require cleanup audit final test evidence**

Require `docs/audits/2026-05-02-cleanup-round2-test-audit.md` to state that the pending table is empty and remove the stale `513 passed / 5 failed` final evidence.

- [x] **Step 3: Run the red guard**

Run:

```powershell
python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py::test_current_deploy_state_tracks_current_head_and_validation_evidence -q
```

Expected before doc updates: FAIL because the docs still list older validation evidence.

Observed before doc updates: FAIL because the current-state document still carried stale validation evidence. During review, the initial hardcoded commit-hash assertion was removed because a self-referential current commit in a tracked document becomes stale immediately after commit.

### Task 2: Refresh Evidence Docs

**Files:**
- Modify: `docs/deploy/current-state.md`
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Update current-state local validation records**

Refresh timestamp, backend default suite, frontend contract suite, frontend node test suite, build, and diff-check evidence. Keep the record anchored to `当前 main HEAD` instead of embedding a self-invalidating commit hash.

- [x] **Step 2: Update cleanup audit test records**

Add the current no-pending-row status and latest validation split, while keeping the original agent baseline as historical context only if clearly labeled.

### Task 3: Verify And Ship

Run:

```powershell
python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py -q
python -m pytest backend/tests -q
python -m pytest backend/tests -m frontend_contract -q
npm --prefix frontend test
npm --prefix frontend run build
git diff --check
```

Expected: all commands pass. Existing CRLF warnings are acceptable only when exit code is 0.

Observed:
- `python -m pytest backend/tests/test_quick_cloud_trial_docs_and_ops.py -q`: 25 passed, 1 deselected.
- `python -m pytest backend/tests -q`: 646 passed, 119 deselected, 30 warnings.
- `python -m pytest backend/tests -m frontend_contract -q`: 119 passed, 646 deselected.
- `npm --prefix frontend test`: 106 passed.
- `npm --prefix frontend run build`: passed.
- `git diff --check`: passed, with expected CRLF warnings only.
