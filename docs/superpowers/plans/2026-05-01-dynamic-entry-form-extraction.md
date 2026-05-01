# DynamicEntryForm 模块提取 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract pure functions and static config from the 2278-line DynamicEntryForm.vue into focused modules, reducing the SFC to ~1600 lines without changing any behavior.

**Architecture:** Move-and-import refactor. Pure functions → `utils/`, static config → `config/`, stateful composables → `composables/`. Each extraction is a standalone commit. No behavior changes, no new features.

**Tech Stack:** Vue 3 `<script setup>`, ES modules

**Invariants:**
- Zero behavior change — every function signature stays identical
- `npm run build` passes after each task
- No new dependencies
- Existing tests continue to pass

---

### Task 1: Extract expression evaluator → `utils/expressionEvaluator.js`

**Files:**
- Create: `frontend/src/utils/expressionEvaluator.js`
- Modify: `frontend/src/views/mobile/DynamicEntryForm.vue`

94 lines of pure math. Zero component state. Cleanest extraction target.

- [ ] **Step 1: Create `frontend/src/utils/expressionEvaluator.js`**

```js
const SAFE_EXPRESSION_PATTERN = /^[A-Za-z0-9_+\-*/().%\s]+$/

function operatorPrecedence(operator) {
  if (operator === '+' || operator === '-') return 1
  if (operator === '*' || operator === '/' || operator === '%') return 2
  return 0
}

function applyMathOperator(values, operator) {
  if (values.length < 2) return false
  const right = Number(values.pop())
  const left = Number(values.pop())
  let result = null

  if (operator === '+') result = left + right
  else if (operator === '-') result = left - right
  else if (operator === '*') result = left * right
  else if (operator === '/') result = right === 0 ? null : left / right
  else if (operator === '%') result = right === 0 ? null : left % right

  if (result === null || !Number.isFinite(result)) return false
  values.push(result)
  return true
}

export function safeEvaluate(expression, variables) {
  const source = String(expression || '').trim()
  if (!source || !SAFE_EXPRESSION_PATTERN.test(source)) return null

  const tokens = source.match(/[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|[()+\-*/%]/g) || []
  if (!tokens.length) return null

  const values = []
  const operators = []
  let previousTokenType = 'start'

  for (const token of tokens) {
    if (/^\d+(?:\.\d+)?$/.test(token)) {
      values.push(Number(token))
      previousTokenType = 'value'
      continue
    }

    if (/^[A-Za-z_][A-Za-z0-9_]*$/.test(token)) {
      values.push(Number(variables[token] ?? 0))
      previousTokenType = 'value'
      continue
    }

    if (token === '(') {
      operators.push(token)
      previousTokenType = '('
      continue
    }

    if (token === ')') {
      while (operators.length && operators[operators.length - 1] !== '(') {
        if (!applyMathOperator(values, operators.pop())) return null
      }
      if (operators.length === 0 || operators.pop() !== '(') return null
      previousTokenType = 'value'
      continue
    }

    if ('+-*/%'.includes(token)) {
      if (token === '-' && (previousTokenType === 'start' || previousTokenType === 'operator' || previousTokenType === '(')) {
        values.push(0)
      }

      while (
        operators.length &&
        operators[operators.length - 1] !== '(' &&
        operatorPrecedence(operators[operators.length - 1]) >= operatorPrecedence(token)
      ) {
        if (!applyMathOperator(values, operators.pop())) return null
      }
      operators.push(token)
      previousTokenType = 'operator'
      continue
    }

    return null
  }

  while (operators.length) {
    const operator = operators.pop()
    if (operator === '(' || operator === ')') return null
    if (!applyMathOperator(values, operator)) return null
  }

  if (values.length !== 1) return null
  const finalValue = Number(values[0])
  return Number.isFinite(finalValue) ? finalValue : null
}
```

- [ ] **Step 2: In DynamicEntryForm.vue, add import and delete extracted code**

Add to imports section (after existing imports, before `const OCR_STORAGE_PREFIX`):
```js
import { safeEvaluate } from '../../utils/expressionEvaluator.js'
```

Delete lines 1452–1545 (from `const SAFE_EXPRESSION_PATTERN` through end of `safeEvaluate` function).

- [ ] **Step 3: Verify**

Run: `cd frontend && npm run build`
Expected: clean build, zero errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/utils/expressionEvaluator.js frontend/src/views/mobile/DynamicEntryForm.vue
git commit -m "refactor: extract expression evaluator from DynamicEntryForm"
```

---

### Task 2: Extract owner mode config → `config/ownerModeConfig.js`

**Files:**
- Create: `frontend/src/config/ownerModeConfig.js`
- Modify: `frontend/src/views/mobile/DynamicEntryForm.vue`

170 lines of static config objects. No component state.

- [ ] **Step 1: Create `frontend/src/config/` directory and `ownerModeConfig.js`**

```js
export const OWNER_MODE_CONFIG = {
  inventory_keeper: {
    title: '填出入库',
    coreCardTitle: '今日进出',
    coreStepTitle: '进出',
    supplementalCardTitle: '结存复核',
    supplementalStepTitle: '结存',
    coreSections: [
      {
        title: '今日入库',
        fieldNames: [
          'storage_inbound_weight',
          'storage_inbound_area',
          'plant_to_park_inbound_weight',
          'park_to_storage_inbound_weight',
        ],
      },
      {
        title: '今日发货',
        fieldNames: [
          'shipment_weight',
          'shipment_area',
          'month_to_date_shipment_weight',
          'month_to_date_shipment_area',
        ],
      },
    ],
    supplementalSections: [
      {
        title: '结存与备料',
        fieldNames: [
          'month_to_date_inbound_weight',
          'month_to_date_inbound_area',
          'consignment_weight',
          'finished_inventory_weight',
          'shearing_prepared_weight',
        ],
      },
    ],
  },
  utility_manager: {
    title: '填水电气',
    coreCardTitle: '介质录入',
    coreStepTitle: '介质',
    supplementalCardTitle: '水量补录',
    supplementalStepTitle: '用水',
    coreSections: [
      {
        title: '用电',
        fieldNames: [
          'total_electricity_kwh',
          'new_plant_electricity_kwh',
          'park_electricity_kwh',
        ],
      },
      {
        title: '天然气',
        fieldNames: [
          'cast_roll_gas_m3',
          'smelting_gas_m3',
          'heating_furnace_gas_m3',
          'boiler_gas_m3',
          'total_gas_m3',
        ],
      },
    ],
    supplementalSections: [
      {
        title: '用水',
        fieldNames: ['groundwater_ton', 'tap_water_ton'],
      },
    ],
  },
  contracts: {
    title: '填合同',
    coreCardTitle: '合同进度',
    coreStepTitle: '合同',
    supplementalCardTitle: '投料补录',
    supplementalStepTitle: '投料',
    coreSections: [
      {
        title: '当日合同',
        fieldNames: ['daily_contract_weight', 'daily_hot_roll_contract_weight'],
      },
      {
        title: '月累计与余合同',
        fieldNames: [
          'month_to_date_contract_weight',
          'month_to_date_hot_roll_contract_weight',
          'remaining_contract_weight',
          'remaining_hot_roll_contract_weight',
          'remaining_contract_delta_weight',
        ],
      },
    ],
    supplementalSections: [
      {
        title: '投料与坯料',
        fieldNames: [
          'billet_inventory_weight',
          'daily_input_weight',
          'month_to_date_input_weight',
        ],
      },
    ],
  },
  energy_stat: {
    title: '填能耗',
    coreCardTitle: '能耗录入',
    coreStepTitle: '能耗',
    supplementalCardTitle: '补充',
    supplementalStepTitle: '补充',
    coreSections: [
      { title: '电耗与气耗', fieldNames: ['energy_kwh', 'gas_m3'] },
    ],
    supplementalSections: [],
  },
  maintenance_lead: {
    title: '报停机',
    coreCardTitle: '停机录入',
    coreStepTitle: '停机',
    supplementalCardTitle: '补充',
    supplementalStepTitle: '补充',
    coreSections: [
      { title: '停机记录', fieldNames: ['downtime_minutes', 'downtime_reason'] },
    ],
    supplementalSections: [],
  },
  hydraulic_lead: {
    title: '报油耗',
    coreCardTitle: '耗油录入',
    coreStepTitle: '耗油',
    supplementalCardTitle: '补充',
    supplementalStepTitle: '补充',
    coreSections: [
      { title: '液压油与齿轮油', fieldNames: ['hydraulic_oil_32', 'hydraulic_oil_46', 'gear_oil'] },
    ],
    supplementalSections: [],
  },
  consumable_stat: {
    title: '报辅材',
    coreCardTitle: '辅材录入',
    coreStepTitle: '辅材',
    supplementalCardTitle: '补充',
    supplementalStepTitle: '补充',
    coreSections: [],
    supplementalSections: [],
  },
  qc: {
    title: '填质检',
    coreCardTitle: '质检录入',
    coreStepTitle: '质检',
    supplementalCardTitle: '补充',
    supplementalStepTitle: '补充',
    coreSections: [
      { title: '质检结论', fieldNames: ['qc_grade', 'qc_notes'] },
    ],
    supplementalSections: [],
  },
  weigher: {
    title: '核重量',
    coreCardTitle: '核实重量',
    coreStepTitle: '称重',
    supplementalCardTitle: '补充',
    supplementalStepTitle: '补充',
    coreSections: [
      { title: '核实重量', fieldNames: ['verified_input_weight', 'verified_output_weight'] },
    ],
    supplementalSections: [],
  },
}

export const CONSUMABLE_SECTIONS_BY_WORKSHOP = {
  casting: [
    { title: '铸轧辅材', fieldNames: ['liquefied_gas_per_ton', 'titanium_wire_per_ton', 'steel_strip_per_ton', 'magnesium_per_ton', 'manganese_per_ton', 'iron_per_ton', 'copper_per_ton'] },
  ],
  hot_roll: [
    { title: '热轧辅材', fieldNames: ['hot_roll_emulsion_per_ton'] },
  ],
  cold_roll: [
    { title: '冷轧辅材', fieldNames: ['rolling_oil_per_ton', 'filter_agent_per_ton', 'diatomite_per_ton', 'white_earth_per_ton', 'filter_cloth_daily', 'high_temp_tape_daily', 'regen_oil_out', 'regen_oil_in'] },
  ],
  finishing: [
    { title: '精整辅材', fieldNames: ['rolling_oil_per_ton', 'd40_per_ton', 'steel_plate_per_ton', 'steel_strip_per_ton', 'steel_buckle_per_ton', 'high_temp_tape_daily'] },
  ],
}
```

- [ ] **Step 2: In DynamicEntryForm.vue, add import and delete extracted code**

Add to imports:
```js
import { OWNER_MODE_CONFIG, CONSUMABLE_SECTIONS_BY_WORKSHOP } from '../../config/ownerModeConfig.js'
```

Delete lines 794–987 (from `const OWNER_MODE_CONFIG = {` through end of `CONSUMABLE_SECTIONS_BY_WORKSHOP`).

Keep `defaultOwnerModeConfig` (line 965–973) and `ownerModeConfig` computed (line 988–999) in the component — they depend on reactive state (`roleBucketMeta`, `currentShift`, `transitionMapping`).

- [ ] **Step 3: Verify**

Run: `cd frontend && npm run build`
Expected: clean build.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/config/ownerModeConfig.js frontend/src/views/mobile/DynamicEntryForm.vue
git commit -m "refactor: extract owner mode config from DynamicEntryForm"
```

---

### Task 3: Extract field value helpers → `utils/fieldValueHelpers.js`

**Files:**
- Create: `frontend/src/utils/fieldValueHelpers.js`
- Modify: `frontend/src/views/mobile/DynamicEntryForm.vue`

Pure functions that normalize, format, and display field values. No component state.

- [ ] **Step 1: Create `frontend/src/utils/fieldValueHelpers.js`**

```js
import { formatNumber } from './display.js'

export function toNumber(value) {
  if (value === '' || value === null || value === undefined) return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

export function isEmptyValue(value) {
  if (value === null || value === undefined) return true
  if (typeof value === 'string') return value.trim() === ''
  if (Array.isArray(value)) return value.length === 0
  if (typeof value === 'object') return Object.keys(value).length === 0
  return false
}

export function emptyFieldValue(field) {
  if (field.type === 'number') return null
  return ''
}

export function normalizeFieldValue(field, rawValue) {
  if (rawValue === null || rawValue === undefined || rawValue === '') return null
  if (field.type === 'number') return toNumber(rawValue)
  if (field.type === 'time') {
    const text = String(rawValue)
    if (!text.trim()) return null
    return text.length === 5 ? `${text}:00` : text
  }
  return String(rawValue).trim()
}

export function formatFieldValue(field, rawValue) {
  if (rawValue === null || rawValue === undefined) return emptyFieldValue(field)
  if (field.type === 'time') return String(rawValue).slice(0, 8)
  return rawValue
}

export function formatFieldValueForDisplay(field, rawValue) {
  if (rawValue === null || rawValue === undefined || rawValue === '') return '-'
  if (field.type === 'number') {
    const digits = Number.isInteger(Number(rawValue)) ? 0 : 2
    const formatted = formatNumber(rawValue, digits)
    return field.unit ? `${formatted} ${field.unit}` : formatted
  }
  if (field.type === 'time') return String(rawValue).slice(0, 5)
  return String(rawValue)
}

export function displayFieldLabel(field) {
  if (!field) return ''
  if (field.name === 'operator_notes') return '备注'
  return field.label || field.name || ''
}

export function fieldPlaceholder(field) {
  const label = displayFieldLabel(field)
  if (field.type === 'number') return '数字'
  if (field.type === 'time') return '时间'
  return label || '填写'
}

export function resolvePersistedFieldValue(field, workOrder, entry) {
  if (field.target === 'work_order') return workOrder?.[field.name] ?? null
  if (field.target === 'entry') return entry?.[field.name] ?? null
  if (field.target === 'extra') return entry?.extra_payload?.[field.name] ?? null
  if (field.target === 'qc') return entry?.qc_payload?.[field.name] ?? null
  return null
}
```

Note: `resolvePersistedFieldValue` is extracted WITHOUT default parameters. The component will pass `currentWorkOrder.value` and `currentEntry.value` explicitly at each call site.

- [ ] **Step 2: In DynamicEntryForm.vue, add import and delete extracted code**

Add to imports:
```js
import {
  toNumber,
  isEmptyValue,
  emptyFieldValue,
  normalizeFieldValue,
  formatFieldValue,
  formatFieldValueForDisplay,
  displayFieldLabel,
  fieldPlaceholder,
  resolvePersistedFieldValue
} from '../../utils/fieldValueHelpers.js'
```

Delete these function definitions from the component:
- `emptyFieldValue` (lines 1379–1382)
- `toNumber` (lines 1438–1442)
- `isEmptyValue` (lines 1444–1450)
- `normalizeFieldValue` (lines 1547–1556)
- `formatFieldValue` (lines 1558–1562)
- `formatFieldValueForDisplay` (lines 1564–1573)
- `displayFieldLabel` (lines 1575–1579)
- `fieldPlaceholder` (lines 1581–1586)
- `resolvePersistedFieldValue` (lines 1588–1594)

**Important:** Update all call sites of `resolvePersistedFieldValue` that relied on default parameters:

1. `resolveFieldValueByName` (line ~1601, 1607): change `resolvePersistedFieldValue(editableField)` → `resolvePersistedFieldValue(editableField, currentWorkOrder.value, currentEntry.value)`
2. `resolveReadonlyFieldValue` (line ~1643): change `resolvePersistedFieldValue(field)` → `resolvePersistedFieldValue(field, currentWorkOrder.value, currentEntry.value)`
3. `hydrateFormFromWorkOrder` (line ~1667): already passes explicit args — no change needed.

- [ ] **Step 3: Verify**

Run: `cd frontend && npm run build`
Expected: clean build.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/utils/fieldValueHelpers.js frontend/src/views/mobile/DynamicEntryForm.vue
git commit -m "refactor: extract field value helpers from DynamicEntryForm"
```

---

### Task 4: Extract OCR state → `composables/useOcrState.js`

**Files:**
- Create: `frontend/src/composables/useOcrState.js`
- Modify: `frontend/src/views/mobile/DynamicEntryForm.vue`

OCR state management as a Vue composable. Returns reactive state and methods.

- [ ] **Step 1: Create `frontend/src/composables/useOcrState.js`**

```js
import { reactive } from 'vue'

const OCR_STORAGE_PREFIX = 'aluminum-ocr-submission:'

function ocrStorageKey(submissionId) {
  return `${OCR_STORAGE_PREFIX}${submissionId}`
}

export function confidenceTone(confidence) {
  if (confidence === null || confidence === undefined) return 'warn'
  if (confidence >= 0.85) return 'good'
  if (confidence >= 0.6) return 'warn'
  return 'danger'
}

export function confidenceLabel(confidence) {
  if (confidence === null || confidence === undefined) return '待核对'
  return `${Math.round(confidence * 100)}%`
}

export function useOcrState() {
  const ocrState = reactive({
    submissionId: null,
    imageUrl: '',
    rawText: '',
    fields: {},
    verified: false
  })

  function ocrMetaForField(fieldName) {
    return ocrState.fields?.[fieldName] || null
  }

  function clearOcrState({ clearStorage = false } = {}) {
    if (clearStorage && ocrState.submissionId) {
      sessionStorage.removeItem(ocrStorageKey(ocrState.submissionId))
    }
    ocrState.submissionId = null
    ocrState.imageUrl = ''
    ocrState.rawText = ''
    ocrState.fields = {}
    ocrState.verified = false
  }

  function loadOcrFromStorage({ submissionId, editableFields, formValues, formatFieldValue, isEmptyValue }) {
    clearOcrState()
    if (!submissionId) return
    const raw = sessionStorage.getItem(ocrStorageKey(submissionId))
    if (!raw) return

    try {
      const payload = JSON.parse(raw)
      ocrState.submissionId = submissionId
      ocrState.imageUrl = payload.image_url || ''
      ocrState.rawText = payload.raw_text || ''
      ocrState.fields = payload.fields || {}
      ocrState.verified = Boolean(payload.status === 'verified' || payload.verified)

      editableFields.forEach((field) => {
        const meta = payload.fields?.[field.name]
        if (!meta || meta.value === null || meta.value === undefined || meta.value === '') return
        if (isEmptyValue(formValues[field.name])) {
          formValues[field.name] = formatFieldValue(field, meta.value)
        }
      })
    } catch {
      clearOcrState({ clearStorage: true })
    }
  }

  function saveOcrVerification(status) {
    ocrState.verified = status === 'verified'
    sessionStorage.setItem(
      ocrStorageKey(ocrState.submissionId),
      JSON.stringify({
        ocr_submission_id: ocrState.submissionId,
        image_url: ocrState.imageUrl,
        raw_text: ocrState.rawText,
        fields: ocrState.fields,
        status,
        verified: ocrState.verified
      })
    )
  }

  function removeOcrStorage() {
    if (ocrState.submissionId) {
      sessionStorage.removeItem(ocrStorageKey(ocrState.submissionId))
    }
  }

  return {
    ocrState,
    ocrMetaForField,
    clearOcrState,
    loadOcrFromStorage,
    saveOcrVerification,
    removeOcrStorage,
    confidenceTone,
    confidenceLabel
  }
}
```

- [ ] **Step 2: In DynamicEntryForm.vue, replace OCR code with composable**

Add to imports:
```js
import { useOcrState, confidenceTone, confidenceLabel } from '../../composables/useOcrState.js'
```

Add after existing composable calls (near line 651):
```js
const {
  ocrState,
  ocrMetaForField,
  clearOcrState,
  loadOcrFromStorage: loadOcrFromStorageRaw,
  saveOcrVerification,
  removeOcrStorage
} = useOcrState()
```

Delete from the component:
- `const OCR_STORAGE_PREFIX` (line 646)
- `ocrState` reactive declaration (lines 666–672)
- `ocrStorageKey` function (lines 1240–1242)
- `ocrMetaForField` function (lines 1258–1260)
- `confidenceTone` function (lines 1262–1267)
- `confidenceLabel` function (lines 1269–1272)
- `clearOcrState` function (lines 1274–1283)
- `loadOcrFromStorage` function (lines 1411–1436)

Replace the `loadOcrFromStorage()` call in `loadPage()` (around line 2136) with:
```js
loadOcrFromStorageRaw({
  submissionId: Number(route.query.ocr_submission_id || 0),
  editableFields: editableFields.value,
  formValues,
  formatFieldValue,
  isEmptyValue
})
```

Replace `verifyOcrIfNeeded` function body (lines 1793–1825) — keep the function in the component but use `saveOcrVerification`:
```js
async function verifyOcrIfNeeded(requestConfig = {}) {
  if (!ocrState.submissionId || ocrState.verified) return

  const correctedFields = {}
  editableFields.value.forEach((field) => {
    const value = normalizeFieldValue(field, formValues[field.name])
    if (value !== null) {
      correctedFields[field.name] = value
    }
  })

  const payload = await verifyOcrFields(
    {
      ocr_submission_id: ocrState.submissionId,
      corrected_fields: correctedFields,
      rejected: false
    },
    requestConfig
  )

  saveOcrVerification(payload.status)
}
```

Replace `sessionStorage.removeItem(ocrStorageKey(ocrState.submissionId))` in `persistEntry` (line ~1902) with `removeOcrStorage()`.

- [ ] **Step 3: Verify**

Run: `cd frontend && npm run build`
Expected: clean build.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/composables/useOcrState.js frontend/src/views/mobile/DynamicEntryForm.vue
git commit -m "refactor: extract OCR state composable from DynamicEntryForm"
```

---

### Task 5: Extract submit cooldown → `composables/useSubmitCooldown.js`

**Files:**
- Create: `frontend/src/composables/useSubmitCooldown.js`
- Modify: `frontend/src/views/mobile/DynamicEntryForm.vue`

Timer-based cooldown logic as a composable.

- [ ] **Step 1: Create `frontend/src/composables/useSubmitCooldown.js`**

```js
import { onBeforeUnmount, ref } from 'vue'
import { SUBMIT_COOLDOWN_MS } from '../utils/submitGuard.js'

export function useSubmitCooldown() {
  const lastSubmitTime = ref(0)
  const submitCooldownActive = ref(false)
  let timer = null

  function clearCooldownTimer() {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }

  function startCooldown() {
    lastSubmitTime.value = Date.now()
    submitCooldownActive.value = true
    clearCooldownTimer()
    timer = setTimeout(() => {
      submitCooldownActive.value = false
      timer = null
    }, SUBMIT_COOLDOWN_MS)
  }

  onBeforeUnmount(() => clearCooldownTimer())

  return {
    lastSubmitTime,
    submitCooldownActive,
    startCooldown
  }
}
```

- [ ] **Step 2: In DynamicEntryForm.vue, replace cooldown code with composable**

Add to imports:
```js
import { useSubmitCooldown } from '../../composables/useSubmitCooldown.js'
```

Add after existing composable calls:
```js
const { lastSubmitTime, submitCooldownActive, startCooldown: startSubmitCooldown } = useSubmitCooldown()
```

Delete from the component:
- `lastSubmitTime` ref (line 699)
- `submitCooldownActive` ref (line 700)
- `let submitCooldownTimer = null` (line 702)
- `clearSubmitCooldownTimer` function (lines 1285–1290)
- `startSubmitCooldown` function (lines 1292–1299)
- The `onBeforeUnmount(() => clearSubmitCooldownTimer())` call (lines 2152–2154)

Remove the `SUBMIT_COOLDOWN_MS` import from DynamicEntryForm.vue (line 643) — it's no longer used directly. Keep `isWithinSubmitCooldown` if still referenced.

- [ ] **Step 3: Verify**

Run: `cd frontend && npm run build`
Expected: clean build.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/composables/useSubmitCooldown.js frontend/src/views/mobile/DynamicEntryForm.vue
git commit -m "refactor: extract submit cooldown composable from DynamicEntryForm"
```

---

### Task 6: Final verification and line count

- [ ] **Step 1: Run full build**

Run: `cd frontend && npm run build`
Expected: clean build.

- [ ] **Step 2: Run backend tests**

Run: `cd backend && python -m pytest -q`
Expected: 502 passed, 0 failed.

- [ ] **Step 3: Count lines**

Run: `wc -l frontend/src/views/mobile/DynamicEntryForm.vue`
Expected: ~1600 lines (down from 2278).

- [ ] **Step 4: Verify no broken imports**

Run: `grep -rn "from.*expressionEvaluator" frontend/src/`
Run: `grep -rn "from.*ownerModeConfig" frontend/src/`
Run: `grep -rn "from.*fieldValueHelpers" frontend/src/`
Run: `grep -rn "from.*useOcrState" frontend/src/`
Run: `grep -rn "from.*useSubmitCooldown" frontend/src/`
Expected: each file imported exactly once, from DynamicEntryForm.vue.

- [ ] **Step 5: Commit (if any cleanup needed)**

```bash
git add -A
git commit -m "refactor: DynamicEntryForm extraction round 2 complete"
```
