# Quality Disposition Reason Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit item F16 by preventing blank quality issue disposition notes from entering the audit chain.

**Architecture:** Keep the existing quality center table and action flow. Add frontend prompt validation and normalization so operators cannot submit blank notes accidentally, and add backend request/service guards so direct API calls cannot write empty `resolve_note` / audit `reason`.

**MES and Rule Context:** Live MES login page is reachable but no usable local credentials are configured for an inner MES login. Local MES contracts and historical reference files keep `workshop_code`, `machine_code`, and `qc` owner fields as traceability inputs; quality disposition notes are audit-chain data and must be complete.

**Tech Stack:** Vue 3, Element Plus prompt validation, frontend node tests, FastAPI/Pydantic schemas, pytest route tests.

---

### Task 1: Add Regression Tests First

**Files:**
- Create: `frontend/src/utils/qualityDispositionValidation.js`
- Create: `frontend/tests/qualityDispositionValidation.test.js`
- Modify: `backend/tests/test_quality_checks.py`

- [x] **Step 1: Test frontend note normalization and blank rejection**

Add node tests asserting whitespace-only values are invalid and trimmed notes are preserved.

- [x] **Step 2: Test quality center prompt wiring**

Read `frontend/src/views/quality/QualityCenter.vue` and assert the page imports the helper, wires `inputValidator`, and submits `normalizeQualityDispositionNote(value)` rather than raw `value`.

- [x] **Step 3: Test backend action note validation**

Add route tests asserting blank `note` is rejected and trimmed notes reach the quality service.

- [x] **Step 4: Run tests and confirm red**

Run:

```bash
cd frontend && node --test tests/qualityDispositionValidation.test.js
python -m pytest backend/tests/test_quality_checks.py -q
```

Expected before implementation: frontend helper/import checks fail; backend blank-note validation fails because schema/service currently accept empty notes.
Observed before implementation:
- `cd frontend && node --test tests/qualityDispositionValidation.test.js`: FAIL, `ERR_MODULE_NOT_FOUND` for `frontend/src/utils/qualityDispositionValidation.js`.
- `python -m pytest backend/tests/test_quality_checks.py -q`: FAIL, `2 failed / 1 passed`; blank note returned `200`, and padded note reached the response untrimmed.

### Task 2: Implement Frontend Prompt Guard

**Files:**
- Modify: `frontend/src/views/quality/QualityCenter.vue`
- Modify: `frontend/src/utils/qualityDispositionValidation.js`
- Modify: `frontend/src/api/quality.js`

- [x] **Step 1: Add pure frontend helpers**

Implement note normalization and boolean validity checks without changing page layout or route behavior.

- [x] **Step 2: Wire Element Plus prompt validation**

Use the helper as `inputValidator` for both resolve and ignore prompts, with one concise validation message.

- [x] **Step 3: Submit normalized notes**

Trim the prompt value before calling `resolveQualityIssue` / `ignoreQualityIssue`.

- [x] **Step 4: Remove optional API implication**

Update quality API helper signatures so disposition `note` is no longer represented as optional in frontend code.

### Task 3: Implement Backend Guard

**Files:**
- Modify: `backend/app/schemas/quality.py`
- Modify: `backend/app/services/quality_service.py`

- [x] **Step 1: Require nonblank action note in schema**

Use Pydantic validation to reject missing, null, or whitespace-only notes and return a trimmed value.

- [x] **Step 2: Guard service calls too**

Normalize and require notes inside `resolve_issue` / `ignore_issue` so internal service calls cannot bypass the audit rule.

### Task 4: Close Audit Item And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move F16 to fixed list**

Add a fixed row for quality disposition note validation and remove F16 from the pending table.

- [x] **Step 2: Run focused and full verification**

Run:

```bash
cd frontend && node --test tests/qualityDispositionValidation.test.js
cd frontend && npm run test
cd frontend && npm run build
python -m pytest backend/tests/test_quality_checks.py -q
python -m pytest backend/tests/test_mobile_entry_copy_consistency.py backend/tests/test_reference_command_center_spec.py -q
python -m pytest backend/tests -q --durations=10
git diff --check
```

Expected: all commands pass.
Focused checks so far:
- `cd frontend && node --test tests/qualityDispositionValidation.test.js`: PASS, `3 passed`.
- `python -m pytest backend/tests/test_quality_checks.py -q`: PASS, `3 passed`.
Full checks:
- `cd frontend && npm run test`: PASS, `97 passed`.
- `cd frontend && npm run build`: PASS.
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py backend/tests/test_reference_command_center_spec.py -q`: PASS, `106 passed`.
- `python -m pytest backend/tests -q --durations=10`: PASS, `741 passed, 30 warnings`.
- `git diff --check`: PASS, only Windows LF-to-CRLF warnings.

- [x] **Step 3: Review diff, commit, push**

Review for scope drift and audit behavior, then commit with:

```bash
git add docs/superpowers/plans/2026-05-05-quality-disposition-reason-validation.md frontend/src/views/quality/QualityCenter.vue frontend/src/utils/qualityDispositionValidation.js frontend/src/api/quality.js frontend/tests/qualityDispositionValidation.test.js backend/app/schemas/quality.py backend/app/services/quality_service.py backend/tests/test_quality_checks.py docs/audits/2026-05-02-cleanup-round2-test-audit.md
git commit -m "fix: 校验质量处置原因"
git push
```

Review: no scope drift found. Frontend callers now pass normalized notes, backend route/service rejects blank notes, and audit item F16 is moved to R55.
