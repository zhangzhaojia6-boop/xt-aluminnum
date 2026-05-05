# Reconciliation Disposition Reason Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit item F17 by requiring operator-entered disposition notes for reconciliation confirm, ignore, and correct actions.

**Architecture:** Keep the existing reconciliation center table and status model. Replace hardcoded confirm/ignore notes with prompt-based input, normalize notes before API calls, and require nonblank notes at the backend schema/service boundary.

**MES and Rule Context:** Live MES login page is reachable but no usable local credentials are configured for an inner MES login. Local MES contracts and historical reference files confirm `workshop_code`, `machine_code`, owner/QC fields, and `reason` / `resolve_note` values are traceability inputs for exception and reconciliation closure.

**Tech Stack:** Vue 3, Element Plus prompt validation, frontend node tests, FastAPI/Pydantic schemas, pytest route tests.

---

### Task 1: Add Regression Tests First

**Files:**
- Create: `frontend/src/utils/reconciliationDispositionValidation.js`
- Create: `frontend/tests/reconciliationDispositionValidation.test.js`
- Modify: `backend/tests/test_reconciliation_flow.py`

- [x] **Step 1: Test frontend note normalization and blank rejection**

Add node tests asserting whitespace-only values are invalid and trimmed notes are preserved.

- [x] **Step 2: Test reconciliation center action wiring**

Read `frontend/src/views/reconciliation/ReconciliationCenter.vue` and assert the page imports the helper, wires `inputValidator`, submits normalized notes, and no longer contains hardcoded confirm/ignore reasons.

- [x] **Step 3: Test backend action note validation**

Add route tests asserting confirm, ignore, and correct reject missing/null/blank notes and pass trimmed notes to the service.

- [x] **Step 4: Run tests and confirm red**

Run:

```bash
cd frontend && node --test tests/reconciliationDispositionValidation.test.js
python -m pytest backend/tests/test_reconciliation_flow.py -q
```

Expected before implementation: frontend helper/import checks fail; backend action tests fail because notes are optional or untrimmed.
Observed before implementation:
- `cd frontend && node --test tests/reconciliationDispositionValidation.test.js`: FAIL, `ERR_MODULE_NOT_FOUND` for `frontend/src/utils/reconciliationDispositionValidation.js`.
- `python -m pytest backend/tests/test_reconciliation_flow.py -q`: FAIL, `2 failed / 1 passed`; blank confirm/ignore returned `200`, and padded notes reached the response untrimmed.

### Task 2: Implement Frontend Prompt Guard

**Files:**
- Modify: `frontend/src/views/reconciliation/ReconciliationCenter.vue`
- Modify: `frontend/src/utils/reconciliationDispositionValidation.js`
- Modify: `frontend/src/api/reconciliation.js`

- [x] **Step 1: Add pure frontend helpers**

Implement note normalization and validity checks.

- [x] **Step 2: Prompt for all three actions**

Use Element Plus prompt validation for confirm, ignore, and correct actions without changing table layout.

- [x] **Step 3: Submit normalized notes**

Trim prompt values before calling `confirmReconciliationItem`, `ignoreReconciliationItem`, and `correctReconciliationItem`.

- [x] **Step 4: Remove optional API implication**

Update reconciliation API helper signatures so disposition `note` is no longer represented as optional for confirm/ignore.

### Task 3: Implement Backend Guard

**Files:**
- Modify: `backend/app/schemas/reconciliation.py`
- Modify: `backend/app/routers/reconciliation.py`
- Modify: `backend/app/services/reconciliation_service.py`

- [x] **Step 1: Require nonblank action note in schema**

Use Pydantic validation to reject missing, null, or whitespace-only notes and return a trimmed value.

- [x] **Step 2: Guard service calls too**

Normalize and require notes inside `update_item_status` for confirm, ignore, and correct actions.

- [x] **Step 3: Remove redundant correct-only route check**

Keep validation in the shared request/service path so all actions share the same rule.

### Task 4: Close Audit Item And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move F17 to fixed list**

Add a fixed row for reconciliation disposition note validation and remove F17 from the pending table.

- [x] **Step 2: Run focused and full verification**

Run:

```bash
cd frontend && node --test tests/reconciliationDispositionValidation.test.js
cd frontend && npm run test
cd frontend && npm run build
python -m pytest backend/tests/test_reconciliation_flow.py -q
python -m pytest backend/tests/test_mobile_entry_copy_consistency.py backend/tests/test_reference_command_center_spec.py -q
python -m pytest backend/tests -q --durations=10
git diff --check
```

Expected: all commands pass.
Focused checks so far:
- `cd frontend && node --test tests/reconciliationDispositionValidation.test.js`: PASS, `3 passed`.
- `python -m pytest backend/tests/test_reconciliation_flow.py -q`: PASS, `3 passed`.
Full checks:
- `cd frontend && npm run test`: PASS, `100 passed`.
- `cd frontend && npm run build`: PASS.
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py backend/tests/test_reference_command_center_spec.py -q`: PASS, `106 passed`.
- `python -m pytest backend/tests -q --durations=10`: PASS, `743 passed, 30 warnings`.
- `git diff --check`: PASS, only Windows LF-to-CRLF warnings.

- [x] **Step 3: Review diff, commit, push**

Review for scope drift and audit behavior, then commit with:

```bash
git add docs/superpowers/plans/2026-05-05-reconciliation-disposition-reason-validation.md frontend/src/views/reconciliation/ReconciliationCenter.vue frontend/src/utils/reconciliationDispositionValidation.js frontend/src/api/reconciliation.js frontend/tests/reconciliationDispositionValidation.test.js backend/app/schemas/reconciliation.py backend/app/routers/reconciliation.py backend/app/services/reconciliation_service.py backend/tests/test_reconciliation_flow.py docs/audits/2026-05-02-cleanup-round2-test-audit.md
git commit -m "fix: 校验差异核对处置原因"
git push
```

Review: no scope drift found. Reconciliation callers now pass normalized operator notes, backend route/service rejects blank notes, and audit item F17 is moved to R56.
