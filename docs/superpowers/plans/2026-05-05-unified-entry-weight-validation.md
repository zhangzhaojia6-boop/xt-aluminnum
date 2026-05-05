# Unified Entry Weight Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit item F14 by blocking invalid unified mobile entry weights before either coil-entry or shift-report submission.

**Architecture:** Add one pure frontend helper for weight validation and call it from `UnifiedEntryForm.vue` after required-field checks. Keep the helper independent of Vue and Element Plus so `node --test` can verify the business rules directly.

**Tech Stack:** Vue 3, Element Plus, native Node.js test runner.

---

### Task 1: Add Red Tests For Weight Rules

**Files:**
- Create: `frontend/tests/entryWeightValidation.test.js`
- Create: `frontend/src/utils/entryWeightValidation.js`

- [x] **Step 1: Write the failing test**

```js
import test from 'node:test'
import assert from 'node:assert/strict'

import { validateEntryWeights } from '../src/utils/entryWeightValidation.js'

test('validateEntryWeights rejects negative visible weight values', () => {
  const fields = [{ name: 'input_weight', label: '投入重量', type: 'number' }]
  assert.equal(
    validateEntryWeights({ input_weight: -1 }, fields),
    '投入重量不能为负数'
  )
})

test('validateEntryWeights rejects output greater than input', () => {
  const fields = [
    { name: 'input_weight', label: '投入重量', type: 'number' },
    { name: 'output_weight', label: '产出重量', type: 'number' }
  ]
  assert.equal(
    validateEntryWeights({ input_weight: 90, output_weight: 96 }, fields),
    '产出重量不能大于投入重量'
  )
})

test('validateEntryWeights rejects output plus scrap greater than input when scrap is visible', () => {
  const fields = [
    { name: 'input_weight', label: '投入重量', type: 'number' },
    { name: 'output_weight', label: '产出重量', type: 'number' },
    { name: 'scrap_weight', label: '废料重量', type: 'number' }
  ]
  assert.equal(
    validateEntryWeights({ input_weight: 100, output_weight: 96, scrap_weight: 8 }, fields),
    '产出重量和废料重量合计不能大于投入重量'
  )
})

test('validateEntryWeights accepts empty optional weights and valid material balance', () => {
  const fields = [
    { name: 'input_weight', label: '投入重量', type: 'number' },
    { name: 'output_weight', label: '产出重量', type: 'number' },
    { name: 'scrap_weight', label: '废料重量', type: 'number' }
  ]
  assert.equal(validateEntryWeights({ input_weight: '', output_weight: null }, fields), null)
  assert.equal(validateEntryWeights({ input_weight: 100, output_weight: 96, scrap_weight: 4 }, fields), null)
})
```

- [x] **Step 2: Run test to verify it fails**

Run: `cd frontend; node --test tests/entryWeightValidation.test.js`

Expected: FAIL because `entryWeightValidation.js` does not export `validateEntryWeights` yet.

### Task 2: Implement Helper And Wire Unified Form

**Files:**
- Modify: `frontend/src/utils/entryWeightValidation.js`
- Modify: `frontend/src/views/mobile/UnifiedEntryForm.vue`

- [x] **Step 1: Add minimal helper implementation**

Implement `validateEntryWeights(form, fields)` to:
- ignore absent or empty optional weight fields;
- reject visible `input_weight`, `output_weight`, or `scrap_weight` values below zero;
- reject `output_weight > input_weight` when both visible values are numeric;
- reject `output_weight + scrap_weight > input_weight` when all three visible values are numeric.

- [x] **Step 2: Call helper from `UnifiedEntryForm.vue`**

Flatten `groups.value` into visible fields inside a new `validateBusinessRules()` function. In `handleSubmit()`, run it immediately after `validateVisibleRequiredFields()` and show the returned message with `ElMessage.warning`.

- [x] **Step 3: Run unit tests**

Run: `cd frontend; node --test tests/entryWeightValidation.test.js`

Expected: PASS.

### Task 3: Close Audit Item And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move F14 to fixed list**

Add `R26` describing the helper, component guard, and node unit test. Remove F14 from the pending table.

- [x] **Step 2: Run focused and regression checks**

Run:
- `npm --prefix frontend run test:unit`
- `npm --prefix frontend run build`
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`
- `git diff --check`

Expected: all commands pass.

Verification note: `npm --prefix frontend run test:unit` initially exposed two stale redirect-copy assertions still expecting string redirects after the existing `preserveRouteState(...)` route contract. Those assertions were updated and the suite then passed. A longer backend full run also passed with `680 passed`.

- [x] **Step 3: Review diff and commit**

Review `git diff`, ensure the diff is on target, then commit with:

```bash
git add docs/superpowers/plans/2026-05-05-unified-entry-weight-validation.md frontend/tests/entryWeightValidation.test.js frontend/src/utils/entryWeightValidation.js frontend/src/views/mobile/UnifiedEntryForm.vue docs/audits/2026-05-02-cleanup-round2-test-audit.md
git commit -m "fix: 校验统一填报重量关系"
```
