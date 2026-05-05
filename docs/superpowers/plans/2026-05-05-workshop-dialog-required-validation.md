# Workshop Dialog Required Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit item F15 by preventing blank workshop code/name submissions from the admin workshop dialog.

**Architecture:** Keep the current master data page and dialog layout. Add Element Plus form rules for `code` and `name`, validate before saving, and normalize the payload by trimming identity fields so workshop records remain usable for QR, machine-line, and owner binding rules.

**Tech Stack:** Vue 3, Element Plus form validation, frontend node tests, existing admin master page.

---

### Task 1: Add Frontend Validation Regression Tests

**Files:**
- Create: `frontend/src/utils/workshopFormValidation.js`
- Create: `frontend/tests/workshopFormValidation.test.js`

- [x] **Step 1: Test blank workshop identity is invalid**

Add node tests asserting empty or whitespace-only `code`/`name` is rejected.

- [x] **Step 2: Test payload normalization trims identity fields**

Assert `normalizeWorkshopPayload({ code: ' ZR2 ', name: ' 铸轧二车间 ' })` returns trimmed identity values and preserves non-identity fields.

- [x] **Step 3: Add source contract checks for the dialog wiring**

Read `frontend/src/views/master/Workshop.vue` and assert it wires `:rules`, `prop="code"`, `prop="name"`, calls `formRef.value.validate()`, and saves `normalizeWorkshopPayload(form)`.

- [x] **Step 4: Run tests and confirm red**

Run:

```bash
cd frontend && npm run test -- tests/workshopFormValidation.test.js
```

Expected before implementation: import/source checks fail because the helper and dialog validation do not exist.
Observed before implementation: FAIL; frontend node run reported `ERR_MODULE_NOT_FOUND` for `frontend/src/utils/workshopFormValidation.js`, while existing tests passed.

### Task 2: Implement Dialog Validation

**Files:**
- Modify: `frontend/src/views/master/Workshop.vue`
- Modify: `frontend/src/utils/workshopFormValidation.js`

- [x] **Step 1: Add pure form helpers**

Implement `normalizeWorkshopPayload(form)` and `hasWorkshopIdentity(form)` in `workshopFormValidation.js`.

- [x] **Step 2: Wire Element Plus form validation**

Add `formRef`, `workshopRules`, `:rules`, `prop="code"`, and `prop="name"` to `Workshop.vue`.

- [x] **Step 3: Validate before saving**

Call `await formRef.value.validate()` before setting `saving=true`, then send the trimmed payload to `createWorkshop` / `updateWorkshop`.

- [x] **Step 4: Clear stale validation state when opening dialogs**

Use `nextTick` and `formRef.value.clearValidate()` after opening create/edit dialogs.

### Task 3: Close Audit Item And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move F15 to fixed list**

Add a fixed row for workshop dialog required validation and remove F15 from the pending table.

- [x] **Step 2: Run focused and full verification**

Run:

```bash
cd frontend && npm run test -- tests/workshopFormValidation.test.js
cd frontend && npm run test
python -m pytest backend/tests/test_mobile_entry_copy_consistency.py backend/tests/test_reference_command_center_spec.py -q
python -m pytest backend/tests -q --durations=10
git diff --check
```

Expected: all commands pass.
Observed:
- `node --test tests/workshopFormValidation.test.js`: PASS, `3 passed`.
- `cd frontend && npm run test`: PASS, `94 passed`.
- `cd frontend && npm run build`: PASS.
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py backend/tests/test_reference_command_center_spec.py -q`: PASS, `106 passed`.
- `python -m pytest backend/tests -q --durations=10`: PASS, `739 passed, 30 warnings`.
- `git diff --check`: PASS, only Windows LF-to-CRLF warnings.

- [x] **Step 3: Review diff and commit**

Review for frontend scope drift and validation behavior, then commit with:

```bash
git add docs/superpowers/plans/2026-05-05-workshop-dialog-required-validation.md frontend/src/views/master/Workshop.vue frontend/src/utils/workshopFormValidation.js frontend/tests/workshopFormValidation.test.js docs/audits/2026-05-02-cleanup-round2-test-audit.md
git commit -m "fix: 校验车间主数据必填项"
```

Review: quick scope, on target. Validation is limited to workshop identity fields and does not change route, API, or page layout behavior.
