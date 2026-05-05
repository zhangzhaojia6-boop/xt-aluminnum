# Assistant Workbench Hero Truthfulness Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the AI workbench hero from saying production context is already connected when the assistant capability state is still fallback / unconnected.

**Architecture:** Keep the existing drawer, actions, status cards, and live copy. Replace the static hero paragraph with a computed copy derived from `capabilityState.connected`. Connected mode keeps the current short copy; fallback mode shows a short unconnected state.

**Scope:** Frontend copy state only. Do not change assistant routes, quick actions, query/image behavior, schemas, or external MES integration.

**Tech Stack:** Vue component static contract tests, frontend node tests, frontend build.

---

### Task 1: Add Red Tests

**Files:**
- Modify: `backend/tests/test_mobile_entry_copy_consistency.py`
- Modify: `frontend/tests/assistantFallbackTruthfulness.test.js`

- [x] **Step 1: Backend frontend-contract red test**

Update the workbench copy contract to require:
- `assistantHeroCopy`
- connected copy keeps `已接生产上下文，可直接用于审阅与交付。`
- fallback copy includes `生产上下文未联通`
- template renders `{{ assistantHeroCopy }}`

Run:

```powershell
python -m pytest backend/tests/test_mobile_entry_copy_consistency.py::test_review_layout_and_workbench_share_short_copy_language -m frontend_contract -q
```

Expected before implementation: FAIL because the component still renders the connected copy as static text.

- [x] **Step 2: Frontend fallback red test**

Extend `assistantFallbackTruthfulness.test.js` to require dynamic hero copy and reject the static paragraph.

Run:

```powershell
npm --prefix frontend test -- tests/assistantFallbackTruthfulness.test.js
```

Expected before implementation: FAIL because `assistantHeroCopy` does not exist yet.

### Task 2: Implement Dynamic Hero Copy

**Files:**
- Modify: `frontend/src/components/review/ReviewAssistantWorkbench.vue`

- [x] **Step 1: Replace static hero paragraph**

Render `{{ assistantHeroCopy }}` in the hero paragraph.

- [x] **Step 2: Add computed copy**

Add a computed `assistantHeroCopy`:
- connected: `已接生产上下文，可直接用于审阅与交付。`
- fallback: `生产上下文未联通`

### Task 3: Audit And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Add resolved audit row**

Add `R79` describing AI workbench hero copy truthfulness.

- [x] **Step 2: Run verification**

Run:

```powershell
python -m pytest backend/tests/test_mobile_entry_copy_consistency.py::test_review_layout_and_workbench_share_short_copy_language -m frontend_contract -q
python -m pytest backend/tests -m frontend_contract -q
npm --prefix frontend test
npm --prefix frontend run build
git diff --check
```

Expected: all commands pass. Existing CRLF warnings are acceptable only when exit code is 0.

Actual:
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py::test_review_layout_and_workbench_share_short_copy_language -m frontend_contract -q` -> `1 passed`
- `python -m pytest backend/tests -m frontend_contract -q` -> `119 passed, 646 deselected`
- `python -m pytest backend/tests -q` -> `646 passed, 119 deselected, 30 warnings`
- `npm --prefix frontend test` -> `107 passed`
- `npm --prefix frontend run build` -> passed
- `git diff --check` -> exit 0 with existing CRLF warnings
