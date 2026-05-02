# Frontend Large File Treatment — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract pure functions, stateful logic, and repeated template patterns from 4 large Vue SFCs into focused modules, reducing total line count by ~1100 lines without changing any behavior. Follows the same pattern proven on DynamicEntryForm.vue (2387 → 1683 lines).

**Architecture:** Move-and-import refactor. Pure functions → `utils/`, stateful logic → `composables/`, repeated template patterns → components. Each file is a standalone commit. No behavior changes, no new features.

**Tech Stack:** Vue 3 `<script setup>`, ES modules

**Invariants:**
- Zero behavior change — all props, events, and data flow stay identical
- `cd frontend && npx vite build` passes after each task
- No new dependencies
- Existing tests continue to pass
- Follow naming conventions from existing `utils/display.js`, `composables/useSubmitCooldown.js`

**Pre-flight checks:**
- `fieldValueHelpers.js` already exports `isEmptyValue`, `toNumber`, `normalizeFieldValue` — UnifiedEntryForm has local duplicates to remove
- `useSubmitCooldown.js` composable already exists — ShiftReportForm has inline cooldown logic that duplicates it
- `display.js` already exports `formatNumber`, `formatStatusLabel`, `formatDeliveryMissingSteps`

---

## File 1: FactoryDirector.vue (1259 lines → ~750 lines)

### Task 1.1: Extract `utils/reportStatus.js` — pure status/classification functions

**Files:**
- Create: `frontend/src/utils/reportStatus.js`
- Modify: `frontend/src/views/dashboard/FactoryDirector.vue`

7 pure functions, zero component state. Lines 370–717 of FactoryDirector.vue.

- [ ] **Step 1: Create `frontend/src/utils/reportStatus.js`**

```js
export function reportStatusLabel(status) {
  const map = {
    submitted: '主操已报',
    reviewed: '系统处理中',
    auto_confirmed: '已入汇总',
    returned: '退回补录',
    draft: '填报中',
    unreported: '待上报',
    late: '迟报'
  }
  return map[status] || status || '待上报'
}

export function reportStatusTagType(status) {
  const map = {
    submitted: 'success',
    reviewed: 'success',
    auto_confirmed: 'success',
    returned: 'danger',
    draft: 'primary',
    unreported: 'warning',
    late: 'danger'
  }
  return map[status] || 'info'
}

export function reportStatusHint(status) {
  const map = {
    submitted: '主操已报',
    reviewed: '系统处理中',
    auto_confirmed: '已入汇总',
    returned: '退回补录',
    draft: '填报中',
    unreported: '待上报',
    late: '迟报'
  }
  return map[status] || '同步中'
}

export function reportingSourceClass(item) {
  const normalized = String(item?.source_variant || '').toLowerCase()
  if (normalized === 'owner') return 'is-owner'
  if (normalized === 'mobile') return 'is-mobile'
  return 'is-import'
}

export function toFactoryStatus(status) {
  const value = String(status || '').toLowerCase()
  if (['danger', 'error', 'failed', 'blocked', 'returned', 'late'].includes(value)) return 'danger'
  if (['warning', 'alert', 'pending', 'fallback', 'mixed', 'unreported'].includes(value)) return 'warning'
  return 'normal'
}

export function workshopTypeFromName(name) {
  const value = String(name || '')
  if (/铸|熔|锭/.test(value)) return 'casting'
  if (/热轧|热/.test(value)) return 'hot_roll'
  if (/冷轧|冷/.test(value)) return 'cold_roll'
  if (/拉矫|矫/.test(value)) return 'leveling'
  if (/退火/.test(value)) return 'online_annealing'
  if (/库|仓|成品/.test(value)) return 'inventory'
  if (/跨|链路|调度/.test(value)) return 'cross_workshop_flow'
  return 'finishing'
}

export function requestErrorMessage(error, fallback = '数据加载失败，请稍后重试') {
  const detail = error?.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || item).join('；')
  }
  if (detail && typeof detail === 'object') {
    return detail.message || detail.msg || fallback
  }
  if (typeof detail === 'string' && detail.trim()) {
    return detail.trim()
  }
  return error?.message || fallback
}
```

- [ ] **Step 2: Update FactoryDirector.vue imports**

Remove the 7 function bodies (lines 370–717) and replace with:

```js
import {
  reportStatusLabel,
  reportStatusTagType,
  reportStatusHint,
  reportingSourceClass,
  toFactoryStatus,
  workshopTypeFromName,
  requestErrorMessage
} from '../../utils/reportStatus'
```

- [ ] **Step 3: Verify** — `cd frontend && npx vite build`

---

### Task 1.2: Extract `composables/useFactoryDashboard.js` — data fetching and state

**Files:**
- Create: `frontend/src/composables/useFactoryDashboard.js`
- Modify: `frontend/src/views/dashboard/FactoryDirector.vue`

Extracts the `load()` function, all dashboard data refs, and derived computeds.

- [ ] **Step 1: Create `frontend/src/composables/useFactoryDashboard.js`**

```js
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { fetchDeliveryStatus, fetchFactoryDashboard } from '../api/dashboard'
import { formatDeliveryMissingSteps, formatNumber } from '../utils/display'
import { requestErrorMessage } from '../utils/reportStatus'

export function useFactoryDashboard(targetDate) {
  const loading = ref(false)
  const data = ref({})
  const delivery = ref({})
  const lastRefreshAt = ref('')
  const lastLoadErrorMessage = ref('')
  let refreshTimer = null

  const leaderMetrics = computed(() => data.value.leader_metrics || {})
  const historyDigest = computed(() => data.value.history_digest || {})
  const runtimeTrace = computed(() => data.value.runtime_trace || {})
  const dailySnapshots = computed(() => historyDigest.value.daily_snapshots || [])
  const monthArchive = computed(() => historyDigest.value.month_archive || {})
  const yearArchive = computed(() => historyDigest.value.year_archive || {})
  const monthToDateOutput = computed(() =>
    data.value.month_to_date_output ?? data.value.leader_metrics?.month_to_date_output ?? null
  )
  const lastRefreshLabel = computed(() =>
    lastRefreshAt.value ? dayjs(lastRefreshAt.value).format('HH:mm:ss') : '--:--:--'
  )
  const retentionSummary = computed(() =>
    `${monthArchive.value.reported_days ?? 0} 天归档`
  )

  async function load() {
    loading.value = true
    try {
      const [dashboardPayload, deliveryPayload] = await Promise.all([
        fetchFactoryDashboard({ target_date: targetDate.value }),
        fetchDeliveryStatus({ target_date: targetDate.value })
      ])
      data.value = dashboardPayload
      delivery.value = deliveryPayload
      lastRefreshAt.value = new Date().toISOString()
      lastLoadErrorMessage.value = ''
    } catch (error) {
      const message = requestErrorMessage(error, '数据加载失败，请稍后重试')
      if (message !== lastLoadErrorMessage.value) {
        ElMessage.error(message)
        lastLoadErrorMessage.value = message
      }
    } finally {
      loading.value = false
    }
  }

  watch(targetDate, () => load())

  onMounted(() => {
    load()
    refreshTimer = setInterval(load, 30000)
  })

  onUnmounted(() => {
    if (refreshTimer) {
      clearInterval(refreshTimer)
      refreshTimer = null
    }
  })

  return {
    loading, data, delivery, lastRefreshAt,
    leaderMetrics, historyDigest, runtimeTrace,
    dailySnapshots, monthArchive, yearArchive,
    monthToDateOutput, lastRefreshLabel, retentionSummary,
    load
  }
}
```

- [ ] **Step 2: Update FactoryDirector.vue** — remove `load()`, all data refs (`loading`, `data`, `delivery`, `lastRefreshAt`, `lastLoadErrorMessage`), all derived computeds (`leaderMetrics`, `historyDigest`, `runtimeTrace`, `dailySnapshots`, `monthArchive`, `yearArchive`, `monthToDateOutput`, `lastRefreshLabel`, `retentionSummary`), the `refreshTimer`, and the `watch`/`onMounted`/`onUnmounted` lifecycle hooks. Replace with:

```js
import { useFactoryDashboard } from '../../composables/useFactoryDashboard'

const {
  loading, data, delivery,
  leaderMetrics, runtimeTrace,
  dailySnapshots, monthArchive, yearArchive,
  monthToDateOutput, lastRefreshLabel, retentionSummary,
  load
} = useFactoryDashboard(targetDate)
```

Keep `onMounted(() => { loadAssistant() })` — only the dashboard load moves into the composable.

- [ ] **Step 3: Verify** — `cd frontend && npx vite build`

---

### Task 1.3: Extract `composables/useAssistantIntegration.js` — assistant dock state

**Files:**
- Create: `frontend/src/composables/useAssistantIntegration.js`
- Modify: `frontend/src/views/dashboard/FactoryDirector.vue`

Extracts assistant-related refs and functions.

- [ ] **Step 1: Create `frontend/src/composables/useAssistantIntegration.js`**

```js
import { computed, ref } from 'vue'
import { buildAssistantFallback, fetchAssistantCapabilities } from '../api/assistant'

export function useAssistantIntegration() {
  const assistantOpen = ref(false)
  const assistantLoading = ref(false)
  const assistantSeedQuery = ref('')
  const assistantShortcutSeed = ref(null)
  const assistantCapabilities = ref(buildAssistantFallback())
  let assistantShortcutSequence = 0

  const assistantQuickActions = computed(() =>
    assistantCapabilities.value.quick_actions || buildAssistantFallback().quick_actions
  )

  function mergeAssistantCapabilities(payload = {}) {
    return {
      ...buildAssistantFallback(),
      ...payload,
      groups: payload.groups || buildAssistantFallback().groups
    }
  }

  function handleAssistantOpen() {
    assistantSeedQuery.value = ''
    assistantShortcutSeed.value = null
    assistantOpen.value = true
  }

  function handleAssistantShortcut(action) {
    const query = action?.query || action?.label || ''
    assistantShortcutSequence += 1
    assistantSeedQuery.value = query
    assistantShortcutSeed.value = {
      key: action?.key || `assistant-shortcut-${assistantShortcutSequence}`,
      mode: action?.mode || 'answer',
      query,
      token: `assistant-shortcut-${assistantShortcutSequence}`
    }
    assistantOpen.value = true
  }

  async function loadAssistant() {
    assistantLoading.value = true
    try {
      const payload = await fetchAssistantCapabilities()
      assistantCapabilities.value = mergeAssistantCapabilities(payload)
    } catch {
      assistantCapabilities.value = buildAssistantFallback()
    } finally {
      assistantLoading.value = false
    }
  }

  return {
    assistantOpen, assistantLoading, assistantSeedQuery,
    assistantShortcutSeed, assistantCapabilities, assistantQuickActions,
    handleAssistantOpen, handleAssistantShortcut, loadAssistant
  }
}
```

- [ ] **Step 2: Update FactoryDirector.vue** — remove all assistant refs (`assistantOpen`, `assistantLoading`, `assistantSeedQuery`, `assistantShortcutSeed`, `assistantCapabilities`, `assistantShortcutSequence`), the `assistantQuickActions` computed, and the functions `mergeAssistantCapabilities`, `handleAssistantOpen`, `handleAssistantShortcut`, `loadAssistant`. Replace with:

```js
import { useAssistantIntegration } from '../../composables/useAssistantIntegration'

const {
  assistantOpen, assistantLoading, assistantSeedQuery,
  assistantShortcutSeed, assistantCapabilities, assistantQuickActions,
  handleAssistantOpen, handleAssistantShortcut, loadAssistant
} = useAssistantIntegration()
```

- [ ] **Step 3: Verify** — `cd frontend && npx vite build`

### Task 1.4: Stat-card + source-tag pattern analysis

The stat-card pattern with source tags repeats 7 times (lines 101–178). Each instance follows:

```html
<div class="stat-card">
  <div class="stat-label">{{ label }}</div>
  <div v-if="sourceTagsFor(target).length" class="stat-source-tags">
    <span v-for="lane in sourceTagsFor(target)" :key="..." :class="[...]">{{ sourceTagText(lane) }}</span>
  </div>
  <div class="stat-value">{{ formatNumber(value) }}</div>
</div>
```

**Decision:** 7 repetitions exceeds the 6+ threshold. However, these cards are inside a `v-show="detailExpanded"` section that is secondary to the hero section. The stat-card markup is simple (6 lines each) and the section is already visually grouped. Extracting a component would add prop overhead without meaningful readability gain. **Skip component extraction** — the utils + composables extractions already bring the file well under 750 lines.

- [ ] **Step 4: Commit** — `git add frontend/src/utils/reportStatus.js frontend/src/composables/useFactoryDashboard.js frontend/src/composables/useAssistantIntegration.js frontend/src/views/dashboard/FactoryDirector.vue && git commit -m "refactor(FactoryDirector): extract utils and composables"`

---

## File 2: ShiftReportForm.vue (877 lines → ~550 lines)

### Task 2.1: Extract `utils/shiftReportHelpers.js` — pure validation/payload logic

**Files:**
- Create: `frontend/src/utils/shiftReportHelpers.js`
- Modify: `frontend/src/views/mobile/ShiftReportForm.vue`

4 pure functions from ShiftReportForm.vue.

- [ ] **Step 1: Create `frontend/src/utils/shiftReportHelpers.js`**

```js
export function statusTagType(status) {
  if (status === 'submitted' || status === 'approved' || status === 'auto_confirmed') return 'success'
  if (status === 'returned') return 'danger'
  if (status === 'draft') return 'warning'
  return 'info'
}

export function isMeaningfulLocalDraft(snapshot) {
  if (!snapshot?.form) return false
  return [
    'attendance_count',
    'input_weight',
    'output_weight',
    'scrap_weight',
    'storage_prepared',
    'storage_finished',
    'shipment_weight',
    'contract_received',
    'electricity_daily',
    'gas_daily',
    'exception_type',
    'note',
    'optional_photo_url'
  ].some((field) => {
    const value = snapshot.form[field]
    if (value === null || value === undefined) return false
    if (typeof value === 'string') return value.trim() !== ''
    return true
  })
}

export function requestErrorMessage(error, fallback = '操作失败') {
  const detail = error?.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || item).join('; ')
  }
  if (detail && typeof detail === 'object') {
    return detail.message || detail.msg || fallback
  }
  return detail || error?.message || fallback
}

export function buildPayload(form) {
  return {
    business_date: form.business_date,
    shift_id: Number(form.shift_id),
    attendance_count: form.attendance_count,
    input_weight: form.input_weight,
    output_weight: form.output_weight,
    scrap_weight: form.scrap_weight,
    storage_prepared: form.storage_prepared,
    storage_finished: form.storage_finished,
    shipment_weight: form.shipment_weight,
    contract_received: form.contract_received,
    electricity_daily: form.electricity_daily,
    gas_daily: form.gas_daily,
    has_exception: form.has_exception,
    exception_type: form.exception_type || null,
    note: form.note || null,
    optional_photo_url: form.optional_photo_url || null
  }
}
```

Note: `requestErrorMessage` here has a slightly different separator (`'; '` vs `'；'`) from the one in `reportStatus.js`. Keep both — they serve different UI contexts (mobile vs desktop).

- [ ] **Step 2: Update ShiftReportForm.vue** — remove the 4 function bodies and import from the new file. The `buildPayload()` call sites change from `buildPayload()` to `buildPayload(form)` since `form` is no longer in closure scope.

```js
import { statusTagType, isMeaningfulLocalDraft, requestErrorMessage, buildPayload } from '../../utils/shiftReportHelpers'
```

- [ ] **Step 3: Verify** — `cd frontend && npx vite build`

---

### Task 2.2: Extract `composables/useShiftReportForm.js` — form lifecycle

**Files:**
- Create: `frontend/src/composables/useShiftReportForm.js`
- Modify: `frontend/src/views/mobile/ShiftReportForm.vue`

Extracts `assignForm`, `load`, `saveDraft`, `submitFinal`, `validateBeforeSubmit`, `queueMobileReport`.

**Important:** ShiftReportForm.vue already has inline submit cooldown logic (lines 518–533) that duplicates `useSubmitCooldown.js`. This extraction replaces the inline logic with the existing composable.

- [ ] **Step 1: Create `frontend/src/composables/useShiftReportForm.js`**

```js
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import {
  fetchMobileReport,
  saveMobileReport,
  submitMobileReport
} from '../api/mobile'
import { isRetryableNetworkError } from './useRetryQueue'
import { useSubmitCooldown } from './useSubmitCooldown'
import { isWithinSubmitCooldown } from '../utils/submitGuard'
import { requestErrorMessage, buildPayload } from '../utils/shiftReportHelpers'

export function useShiftReportForm({ route, enqueuePendingRequest, clearDraft, currentDraftKey }) {
  const saving = ref(false)
  const submitting = ref(false)
  const loading = ref(false)
  const loadError = ref('')
  const showExtendedProduction = ref(false)
  const report = reactive({})
  const form = reactive({
    business_date: '',
    shift_id: null,
    attendance_count: null,
    input_weight: null,
    output_weight: null,
    scrap_weight: null,
    storage_prepared: null,
    storage_finished: null,
    shipment_weight: null,
    contract_received: null,
    electricity_daily: null,
    gas_daily: null,
    has_exception: false,
    exception_type: '',
    note: '',
    optional_photo_url: ''
  })

  const { lastSubmitTime, submitCooldownActive, startCooldown } = useSubmitCooldown()
  const canEdit = computed(() =>
    !['submitted', 'approved', 'auto_confirmed', 'locked'].includes(report.report_status)
  )
  const submitDisabled = computed(() =>
    Boolean(loadError.value) || !canEdit.value || submitting.value || submitCooldownActive.value
  )

  function assignForm(data) {
    Object.assign(report, data)
    form.business_date = data.business_date
    form.shift_id = Number(data.shift_id)
    form.attendance_count = data.attendance_count
    form.input_weight = data.input_weight
    form.output_weight = data.output_weight
    form.scrap_weight = data.scrap_weight
    form.storage_prepared = data.storage_prepared
    form.storage_finished = data.storage_finished
    form.shipment_weight = data.shipment_weight
    form.contract_received = data.contract_received
    form.electricity_daily = data.electricity_daily
    form.gas_daily = data.gas_daily
    form.has_exception = Boolean(data.has_exception)
    form.exception_type = data.exception_type || ''
    form.note = data.note || ''
    form.optional_photo_url = data.optional_photo_url || ''
    showExtendedProduction.value = [
      data.storage_prepared, data.storage_finished,
      data.shipment_weight, data.contract_received,
    ].some((v) => v !== null && v !== undefined && v !== '')
  }

  async function load() {
    loading.value = true
    loadError.value = ''
    try {
      const data = await fetchMobileReport(route.params.businessDate, route.params.shiftId)
      assignForm(data)
    } catch (error) {
      loadError.value = requestErrorMessage(error, '加载班次填报失败，请返回入口后重试。')
      throw error
    } finally {
      loading.value = false
    }
  }

  function validateBeforeSubmit() {
    const requiredFields = [
      ['attendance_count', '出勤人数'],
      ['input_weight', '投入量'],
      ['output_weight', '产出量']
    ]
    const missing = requiredFields.find(([field]) => form[field] === null || form[field] === '')
    if (missing) {
      ElMessage.warning(`请先填写：${missing[1]}`)
      return false
    }
    return true
  }

  async function queueMobileReport({ action, url, payload, clearDraftOnReplay = false }) {
    await enqueuePendingRequest({
      type: 'http-request',
      dedupeKey: `mobile-report:${action}:${payload.business_date}:${payload.shift_id}`,
      method: 'post',
      url,
      body: payload,
      clearDraftKey: clearDraftOnReplay ? currentDraftKey.value : undefined
    })
  }

  async function saveDraft() {
    saving.value = true
    try {
      const data = await saveMobileReport(buildPayload(form))
      assignForm(data)
      ElMessage.success('已暂存')
    } catch (error) {
      if (isRetryableNetworkError(error)) {
        await queueMobileReport({ action: 'save', url: '/mobile/report/save', payload: buildPayload(form) })
        ElMessage.warning('网络不可用，已加入待同步队列并保留本机草稿')
        return
      }
      ElMessage.error(requestErrorMessage(error, '暂存失败'))
    } finally {
      saving.value = false
    }
  }

  async function submitFinal() {
    if (isWithinSubmitCooldown(lastSubmitTime.value)) return
    if (!validateBeforeSubmit()) return
    submitting.value = true
    try {
      const data = await submitMobileReport(buildPayload(form))
      assignForm(data)
      clearDraft(currentDraftKey.value)
      startCooldown()
      ElMessage.success('提交成功，系统会自动处理')
    } catch (error) {
      if (isRetryableNetworkError(error)) {
        await queueMobileReport({
          action: 'submit', url: '/mobile/report/submit',
          payload: buildPayload(form), clearDraftOnReplay: true
        })
        clearDraft(currentDraftKey.value)
        startCooldown()
        ElMessage.success('网络不可用，已加入待同步队列，联网后自动提交')
        return
      }
      ElMessage.error(requestErrorMessage(error, '提交失败'))
    } finally {
      submitting.value = false
    }
  }

  return {
    saving, submitting, loading, loadError, showExtendedProduction,
    report, form, canEdit, submitDisabled,
    lastSubmitTime, submitCooldownActive,
    assignForm, load, saveDraft, submitFinal, validateBeforeSubmit
  }
}
```

- [ ] **Step 2: Update ShiftReportForm.vue** — remove all extracted refs, functions, and the inline cooldown logic (`clearSubmitCooldownTimer`, `startSubmitCooldown`, `lastSubmitTime`, `submitCooldownActive`, `submitCooldownTimer`). Replace with composable import. Remove `onBeforeUnmount` for cooldown timer (handled by `useSubmitCooldown` internally).

- [ ] **Step 3: Verify** — `cd frontend && npx vite build`

- [ ] **Step 4: Commit** — `git add frontend/src/utils/shiftReportHelpers.js frontend/src/composables/useShiftReportForm.js frontend/src/views/mobile/ShiftReportForm.vue && git commit -m "refactor(ShiftReportForm): extract utils and composables, adopt useSubmitCooldown"`

---

## File 3: LiveDashboard.vue (831 lines → ~480 lines)

### Task 3.1: Extract `utils/liveDashboardFormatters.js` — pure formatting

**Files:**
- Create: `frontend/src/utils/liveDashboardFormatters.js`
- Modify: `frontend/src/views/reports/LiveDashboard.vue`

10 pure functions, zero component state.

- [ ] **Step 1: Create `frontend/src/utils/liveDashboardFormatters.js`**

```js
import { formatNumber } from './display'

export function numberValue(value) {
  const num = Number(value ?? 0)
  return Number.isFinite(num) ? num : 0
}

export function formatWeight(value) {
  return formatNumber(value ?? 0, 2)
}

export function formatPercent(value) {
  if (value === null || value === undefined || value === '') return '--'
  return `${formatNumber(value, 2)}%`
}

export function yieldToneClass(value) {
  const num = Number(value)
  if (!Number.isFinite(num)) return 'is-yield-neutral'
  if (num >= 97) return 'is-yield-good'
  if (num >= 94) return 'is-yield-warn'
  return 'is-yield-danger'
}

export function submissionSymbol(status) {
  if (status === 'not_applicable') return '—'
  if (status === 'all_submitted') return '✓'
  if (status === 'in_progress') return '⏳'
  return '○'
}

export function formatAttendance(shift) {
  if (!shift.is_applicable || shift.attendance_status === 'not_applicable') return '—'
  const exceptionCount = numberValue(shift.attendance_exception_count)
  if (shift.attendance_status === 'confirmed' && exceptionCount === 0) return '✓ 已确认'
  if (exceptionCount > 0) return `⚠ ${exceptionCount} 人异常`
  if (shift.attendance_status === 'pending') return '⏳ 待确认'
  return '○ 未开始'
}

export function formatEntryStatus(status) {
  if (status === 'submitted') return '已提交'
  if (status === 'verified') return '已核对'
  if (status === 'approved') return '已通过系统校验'
  if (status === 'synced') return 'MES 已同步'
  return '草稿'
}

export function formatEntryType(type) {
  if (type === 'mes_projection') return 'MES 投影'
  return type === 'completed' ? '本班完工' : '接续生产'
}

export function cellKey(workshopId, machineId, shiftId) {
  return `${workshopId}-${machineId}-${shiftId}`
}

export function attendanceKey(workshopId, shiftId) {
  return `attendance-${workshopId}-${shiftId}`
}
```

- [ ] **Step 2: Update LiveDashboard.vue** — remove the 10 function bodies and import from the new file.

- [ ] **Step 3: Verify** — `cd frontend && npx vite build`

---

### Task 3.2: Extract `composables/useLiveAggregation.js` — data layer

**Files:**
- Create: `frontend/src/composables/useLiveAggregation.js`
- Modify: `frontend/src/views/reports/LiveDashboard.vue`

Extracts `loadAggregation`, `loadOpsSnapshot`, `loadDashboardSurface`, `createEmptyAggregation`, and all aggregation state refs.

- [ ] **Step 1: Create `frontend/src/composables/useLiveAggregation.js`**

```js
import { ref } from 'vue'
import { fetchAssistantLiveProbe } from '../api/assistant'
import { fetchLiveAggregation } from '../api/realtime'

export function createEmptyAggregation(businessDate) {
  return {
    business_date: businessDate,
    overall_progress: { submitted_cells: 0, total_cells: 0 },
    workshops: [],
    yield_matrix_lane: {},
    mes_sync_status: {},
    data_source: 'work_order_runtime',
    factory_total: { input: 0, output: 0, scrap: 0, yield_rate: null }
  }
}

export function useLiveAggregation({ targetDate, streamScope }) {
  const loading = ref(false)
  const activePanels = ref([])
  const aggregation = ref(createEmptyAggregation(targetDate.value))
  const opsSnapshot = ref({
    healthStatus: '未知',
    pipelineStatus: '未检测',
    probeStatus: '未检测',
    probeHint: 'text=- / image=-',
    appVersion: import.meta.env.VITE_APP_VERSION || 'dev',
    responseMs: '--'
  })

  async function parseResponseJson(response) {
    if (!response?.ok) return null
    try { return await response.json() } catch { return null }
  }

  async function loadAggregation({ silent = false } = {}) {
    if (!silent) loading.value = true
    try {
      const data = await fetchLiveAggregation({
        business_date: targetDate.value,
        workshop_id: streamScope.value === 'all' ? undefined : Number(streamScope.value)
      })
      aggregation.value = data
      activePanels.value = data.workshops.map((item) => String(item.workshop_id))
    } finally {
      loading.value = false
    }
  }

  async function loadOpsSnapshot() {
    const startedAt = Date.now()
    try {
      const [healthResponse, readyResponse, probePayload] = await Promise.all([
        fetch('/healthz'), fetch('/readyz'), fetchAssistantLiveProbe()
      ])
      const [healthPayload, readyPayload] = await Promise.all([
        parseResponseJson(healthResponse), parseResponseJson(readyResponse)
      ])
      const healthStatus = healthPayload?.status === 'ok' ? '健康' : '异常'
      const pipelineReady = Boolean(readyPayload?.details?.pipeline?.hard_gate_passed)
      const pipelineStatus = pipelineReady ? '管道就绪' : '管道阻塞'
      const probeStatus = probePayload?.overall_ok ? '就绪' : '阻塞'
      const probeHint = probePayload
        ? `text=${probePayload.text_probe_ok ? 'ok' : 'fail'} / image=${probePayload.image_probe_ok ? 'ok' : 'fail'}`
        : 'text=- / image=-'
      opsSnapshot.value = {
        ...opsSnapshot.value, healthStatus, pipelineStatus,
        probeStatus, probeHint, responseMs: `${Date.now() - startedAt}ms`
      }
    } catch {
      opsSnapshot.value = {
        ...opsSnapshot.value, healthStatus: '异常', pipelineStatus: '未检测',
        probeStatus: '未检测', probeHint: 'text=- / image=-',
        responseMs: `${Date.now() - startedAt}ms`
      }
    }
  }

  async function loadDashboardSurface() {
    await Promise.all([loadAggregation(), loadOpsSnapshot()])
  }

  return {
    loading, activePanels, aggregation, opsSnapshot,
    loadAggregation, loadOpsSnapshot, loadDashboardSurface
  }
}
```

- [ ] **Step 2: Update LiveDashboard.vue** — replace inline state and functions with composable.

- [ ] **Step 3: Verify** — `cd frontend && npx vite build`

---

### Task 3.3: Extract `composables/useLiveDrawer.js` — drawer management

**Files:**
- Create: `frontend/src/composables/useLiveDrawer.js`
- Modify: `frontend/src/views/reports/LiveDashboard.vue`

- [ ] **Step 1: Create `frontend/src/composables/useLiveDrawer.js`**

```js
import { computed, ref } from 'vue'
import { fetchLiveCellDetail } from '../api/realtime'

export function useLiveDrawer({ targetDate }) {
  const drawerVisible = ref(false)
  const drawerLoading = ref(false)
  const activeCell = ref(null)
  const drawerData = ref({ items: [] })

  const drawerTitle = computed(() => {
    if (!activeCell.value) return '批次详情'
    return `${activeCell.value.machine_name} ${activeCell.value.shift_name} 批次详情`
  })

  async function loadDrawer(cell, options = {}) {
    const preserveOpen = options.preserveOpen === true
    activeCell.value = cell
    drawerLoading.value = true
    if (!preserveOpen) drawerVisible.value = true
    try {
      drawerData.value = await fetchLiveCellDetail({
        business_date: targetDate.value,
        workshop_id: cell.workshop_id,
        machine_id: cell.machine_id,
        shift_id: cell.shift_id
      })
    } finally {
      drawerLoading.value = false
    }
  }

  async function openDrawer(workshop, machine, shift) {
    await loadDrawer({
      workshop_id: workshop.workshop_id,
      workshop_name: workshop.workshop_name,
      machine_id: machine.machine_id,
      machine_name: machine.machine_name,
      shift_id: shift.shift_id,
      shift_name: shift.shift_name
    })
  }

  function syncDrawerWithSubmission(payload) {
    if (!drawerVisible.value || !activeCell.value) return
    if (
      activeCell.value.workshop_id !== payload.workshop_id ||
      activeCell.value.machine_id !== payload.machine_id ||
      activeCell.value.shift_id !== payload.shift_id
    ) return
    drawerData.value.items = [
      {
        tracking_card_no: payload.tracking_card_no,
        entry_id: payload.entry_id,
        work_order_id: payload.work_order_id,
        entry_status: payload.entry_status,
        entry_type: payload.entry_type,
        input_weight: payload.input_weight,
        output_weight: payload.output_weight,
        scrap_weight: payload.scrap_weight,
        yield_rate: payload.yield_rate,
        machine_id: payload.machine_id,
        shift_id: payload.shift_id
      },
      ...drawerData.value.items.filter((item) => item.entry_id !== payload.entry_id)
    ]
  }

  function syncDrawerWithVerification(payload) {
    if (!drawerVisible.value) return
    const match = drawerData.value.items.find((item) => item.entry_id === payload.entry_id)
    if (!match) return
    match.entry_status = payload.entry_status || match.entry_status
    match.input_weight = payload.input_weight ?? match.input_weight
    match.output_weight = payload.output_weight ?? match.output_weight
    match.scrap_weight = payload.scrap_weight ?? match.scrap_weight
    match.yield_rate = payload.yield_rate ?? match.yield_rate
  }

  function resetDrawer() {
    drawerVisible.value = false
    activeCell.value = null
    drawerData.value = { items: [] }
  }

  return {
    drawerVisible, drawerLoading, activeCell, drawerData, drawerTitle,
    loadDrawer, openDrawer, syncDrawerWithSubmission, syncDrawerWithVerification, resetDrawer
  }
}
```

- [ ] **Step 2: Update LiveDashboard.vue** — replace drawer state and functions with composable.

- [ ] **Step 3: Verify** — `cd frontend && npx vite build`

---

### Task 3.4: Extract `composables/useLiveRealtime.js` — realtime event processing

**Files:**
- Create: `frontend/src/composables/useLiveRealtime.js`
- Modify: `frontend/src/views/reports/LiveDashboard.vue`

- [ ] **Step 1: Create `frontend/src/composables/useLiveRealtime.js`**

```js
import { ref } from 'vue'
import { cellKey, attendanceKey, numberValue } from '../utils/liveDashboardFormatters'

export function useLiveRealtime({ aggregation, targetDate, loadAggregation, loadDrawer, drawerVisible, activeCell, syncDrawerWithSubmission, syncDrawerWithVerification }) {
  const updatedKeys = ref({})
  const handledEventIds = new Set()
  let reloadTimer = null

  function isUpdated(key) {
    return Boolean(updatedKeys.value[key])
  }

  function markUpdated(key) {
    updatedKeys.value = { ...updatedKeys.value, [key]: Date.now() }
    window.setTimeout(() => {
      const next = { ...updatedKeys.value }
      delete next[key]
      updatedKeys.value = next
    }, 1800)
  }

  function clearHandledEvents() {
    if (handledEventIds.size < 500) return
    handledEventIds.clear()
  }

  function scheduleReload() {
    if (reloadTimer) return
    reloadTimer = window.setTimeout(async () => {
      reloadTimer = null
      await loadAggregation({ silent: true })
    }, 400)
  }

  function findCell(payload) {
    const workshop = aggregation.value.workshops.find((i) => i.workshop_id === payload.workshop_id)
    if (!workshop) return null
    const machine = workshop.machines.find((i) => i.machine_id === payload.machine_id)
    if (!machine) return null
    const shift = machine.shifts.find((i) => i.shift_id === payload.shift_id)
    if (!shift) return null
    return { workshop, machine, shift }
  }

  function applyEntrySubmitted(payload) {
    if (payload.business_date && payload.business_date !== targetDate.value) return
    const match = findCell(payload)
    if (!match) { scheduleReload(); return }
    syncDrawerWithSubmission(payload)
    markUpdated(cellKey(payload.workshop_id, payload.machine_id, payload.shift_id))
    scheduleReload()
  }

  function applyAttendanceConfirmed(payload) {
    if (payload.business_date && payload.business_date !== targetDate.value) return
    const workshop = aggregation.value.workshops.find((i) => i.workshop_id === payload.workshop_id)
    if (!workshop) { scheduleReload(); return }
    workshop.machines.forEach((machine) => {
      const shift = machine.shifts.find((i) => i.shift_id === payload.shift_id)
      if (!shift) return
      shift.attendance_exception_count = numberValue(payload.exception_count)
      shift.attendance_status = numberValue(payload.exception_count) > 0 ? 'pending' : 'confirmed'
    })
    markUpdated(attendanceKey(payload.workshop_id, payload.shift_id))
  }

  function handleRealtimeEvent(type, payload, meta = {}) {
    if (meta.eventId && handledEventIds.has(meta.eventId)) return
    if (meta.eventId) { handledEventIds.add(meta.eventId); clearHandledEvents() }
    if (type === 'entry_submitted') { applyEntrySubmitted(payload); return }
    if (type === 'entry_verified') {
      syncDrawerWithVerification(payload)
      if (payload.workshop_id && payload.machine_id && payload.shift_id) {
        markUpdated(cellKey(payload.workshop_id, payload.machine_id, payload.shift_id))
      }
      scheduleReload()
      return
    }
    if (type === 'attendance_confirmed') applyAttendanceConfirmed(payload)
  }

  function cleanup() {
    if (reloadTimer) { window.clearTimeout(reloadTimer); reloadTimer = null }
  }

  return { updatedKeys, isUpdated, markUpdated, handleRealtimeEvent, cleanup }
}
```

- [ ] **Step 2: Update LiveDashboard.vue** — replace realtime state and functions with composable. Wire `handleRealtimeEvent` into `useRealtimeStream`'s `onEvent`. Move `cleanup()` into `onBeforeUnmount`.

- [ ] **Step 3: Verify** — `cd frontend && npx vite build`

- [ ] **Step 4: Commit** — `git add frontend/src/utils/liveDashboardFormatters.js frontend/src/composables/useLiveAggregation.js frontend/src/composables/useLiveDrawer.js frontend/src/composables/useLiveRealtime.js frontend/src/views/reports/LiveDashboard.vue && git commit -m "refactor(LiveDashboard): extract formatters, aggregation, drawer, and realtime composables"`

---

## File 4: UnifiedEntryForm.vue (705 lines → ~480 lines)

### Task 4.1: Extract `utils/unifiedEntryHelpers.js` — pure value processing

**Files:**
- Create: `frontend/src/utils/unifiedEntryHelpers.js`
- Modify: `frontend/src/views/mobile/UnifiedEntryForm.vue`

**Important check:** `fieldValueHelpers.js` already exports `isEmptyValue` (line 9) and `toNumber` (line 3). UnifiedEntryForm.vue has local `isEmptyValue` (line 230) and `normalizeNumberValue` (line 234) that are near-duplicates.

- `isEmptyValue` in fieldValueHelpers checks arrays and objects too; the local one only checks strings. The local one is used only for form field validation where values are strings or numbers — the simpler version is fine, but the broader one from fieldValueHelpers also works. **Use the existing `isEmptyValue` from fieldValueHelpers.**
- `normalizeNumberValue` is equivalent to `toNumber` from fieldValueHelpers. **Use the existing `toNumber`.**
- `computeReadonly` is unique to this file and uses `Function()` eval — extract it.

- [ ] **Step 1: Create `frontend/src/utils/unifiedEntryHelpers.js`**

```js
export function computeReadonly(rf, formValues) {
  if (!rf.compute) return '—'
  try {
    const expr = rf.compute.replace(/[a-z_]+/g, (m) => {
      const v = Number(formValues[m])
      return isNaN(v) ? '0' : String(v)
    })
    const val = Function(`"use strict"; return (${expr})`)()
    if (!isFinite(val)) return '—'
    return rf.unit === '%' ? val.toFixed(1) + '%' : val.toFixed(1) + (rf.unit ? ' ' + rf.unit : '')
  } catch {
    return '—'
  }
}
```

- [ ] **Step 2: Update UnifiedEntryForm.vue** — remove local `isEmptyValue`, `normalizeNumberValue`, `computeReadonly`. Import:

```js
import { isEmptyValue, toNumber } from '../../utils/fieldValueHelpers'
import { computeReadonly } from '../../utils/unifiedEntryHelpers'
```

Replace `normalizeNumberValue(value)` calls with `toNumber(value)`. Update `computeReadonly(rf)` calls in template to `computeReadonly(rf, form)`.

- [ ] **Step 3: Verify** — `cd frontend && npx vite build`

---

### Task 4.2: Extract `composables/useUnifiedEntryForm.js` — form lifecycle

**Files:**
- Create: `frontend/src/composables/useUnifiedEntryForm.js`
- Modify: `frontend/src/views/mobile/UnifiedEntryForm.vue`

Extracts `loadData`, `handleSubmit`, `initSpecParts`, `syncSpec`, `buildCoilEntryPayload`, `buildMobileReportPayload`, and form state.

- [ ] **Step 1: Create `frontend/src/composables/useUnifiedEntryForm.js`**

```js
import { reactive, ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth.js'
import { isEmptyValue, toNumber } from '../utils/fieldValueHelpers'
import {
  fetchCurrentShift, fetchEntryFields, saveMobileReport,
  submitMobileReport, fetchMobileReport, fetchCoilList, createCoilEntry
} from '../api/mobile.js'

export function useUnifiedEntryForm() {
  const auth = useAuthStore()
  const loading = ref(true)
  const error = ref('')
  const submitting = ref(false)
  const form = reactive({})
  const specParts = reactive({})
  const groups = ref([])
  const readonlyFields = ref([])
  const mode = ref('per_shift')
  const submitTarget = ref('shift_report')
  const identityField = ref(null)
  const history = ref([])
  const coilSeq = ref(1)
  const lastCoilData = ref(null)
  const shiftContext = ref(null)

  const workshopName = computed(() => shiftContext.value?.workshop_name || '')
  const shiftName = computed(() => shiftContext.value?.shift_name || '')
  const businessDate = computed(() => shiftContext.value?.business_date || '')

  function initSpecParts(fieldName, value, suffix) {
    const parts = (value || '').split(/[×xX*]/)
    specParts[fieldName + '_0'] = parts[0] || ''
    specParts[fieldName + '_1'] = parts[1] || ''
    if (!suffix) specParts[fieldName + '_2'] = parts[2] || ''
  }

  function syncSpec(field) {
    const p0 = specParts[field.name + '_0'] || ''
    const p1 = specParts[field.name + '_1'] || ''
    const p2 = field.spec_suffix || specParts[field.name + '_2'] || ''
    form[field.name] = [p0, p1, p2].filter(Boolean).join('×')
  }

  function normalizedFormValues() {
    const values = {}
    for (const group of groups.value) {
      for (const field of group.fields) {
        const value = form[field.name]
        values[field.name] = field.type === 'number' ? toNumber(value) : value
      }
    }
    return values
  }

  function validateVisibleRequiredFields() {
    for (const group of groups.value) {
      for (const field of group.fields) {
        if (field.required && isEmptyValue(form[field.name])) {
          ElMessage.warning(`请先填写：${field.label}`)
          return false
        }
      }
    }
    return true
  }

  function buildCoilEntryPayload(sc) {
    const values = normalizedFormValues()
    const trackingKey = identityField.value || 'tracking_card_no'
    const trackingCardNo = String(values[trackingKey] || '').trim()
    return {
      tracking_card_no: trackingCardNo,
      alloy_grade: values.alloy_grade || null,
      input_spec: values.input_spec || null,
      output_spec: values.output_spec || null,
      on_machine_time: values.on_machine_time || null,
      off_machine_time: values.off_machine_time || null,
      input_weight: values.input_weight,
      output_weight: values.output_weight,
      scrap_weight: values.scrap_weight,
      operator_name: values.operator_name || auth.displayName || '',
      operator_notes: values.operator_notes || '',
      business_date: sc.business_date,
      shift_id: sc.shift_id,
    }
  }

  function buildMobileReportPayload(sc) {
    const values = normalizedFormValues()
    return {
      business_date: sc.business_date,
      shift_id: sc.shift_id,
      attendance_count: toNumber(values.attendance_count),
      input_weight: toNumber(values.input_weight),
      output_weight: toNumber(values.output_weight),
      scrap_weight: toNumber(values.scrap_weight),
      storage_prepared: toNumber(values.storage_prepared),
      storage_finished: toNumber(values.storage_finished),
      shipment_weight: toNumber(values.shipment_weight),
      contract_received: toNumber(values.contract_received),
      electricity_daily: toNumber(values.electricity_daily),
      gas_daily: toNumber(values.gas_daily),
      has_exception: Boolean(values.has_exception),
      exception_type: values.exception_type || null,
      note: values.operator_notes || values.note || null,
    }
  }

  async function loadData() {
    loading.value = true
    error.value = ''
    try {
      const [shift, fields] = await Promise.all([fetchCurrentShift(), fetchEntryFields()])
      shiftContext.value = shift
      if (!shift.shift_id) { error.value = '未找到当前班次，请联系管理员配置班次。'; return }
      if (fields.error) { error.value = fields.error; return }
      groups.value = fields.groups || []
      readonlyFields.value = fields.readonly_fields || []
      mode.value = fields.mode || 'per_shift'
      submitTarget.value = fields.submit_target || (fields.mode === 'per_coil' ? 'coil_entry' : 'shift_report')
      identityField.value = fields.identity_field || null
      for (const g of groups.value) {
        for (const f of g.fields) {
          if (!(f.name in form)) form[f.name] = f.type === 'number' ? null : ''
          if (f.type === 'spec') initSpecParts(f.name, form[f.name], f.spec_suffix)
        }
      }
      if (shift.report_id && mode.value === 'per_shift') {
        try {
          const report = await fetchMobileReport(shift.business_date, shift.shift_id)
          if (report?.data) {
            for (const [k, v] of Object.entries(report.data)) {
              if (k in form && v != null) form[k] = v
            }
          }
        } catch { /* first time, no report yet */ }
      }
      if (mode.value === 'per_coil') {
        try {
          const coils = await fetchCoilList(shift.business_date, shift.shift_id)
          history.value = coils || []
          coilSeq.value = history.value.length + 1
        } catch { /* no coils yet */ }
      }
    } catch (e) {
      error.value = e?.response?.data?.detail || '加载失败'
    } finally {
      loading.value = false
    }
  }

  async function handleSubmit() {
    if (submitting.value) return
    const sc = shiftContext.value
    if (!sc?.shift_id) return
    if (!validateVisibleRequiredFields()) return
    submitting.value = true
    try {
      if (submitTarget.value === 'coil_entry') {
        const saved = await createCoilEntry(buildCoilEntryPayload(sc))
        ElMessage.success(`第${coilSeq.value}卷 录入成功`)
        lastCoilData.value = { ...form }
        history.value.unshift(saved?.data ? saved : { seq: coilSeq.value, ...form })
        coilSeq.value++
        for (const key of Object.keys(form)) { form[key] = typeof form[key] === 'number' ? null : '' }
      } else {
        const payload = buildMobileReportPayload(sc)
        await saveMobileReport(payload)
        await submitMobileReport(payload)
        ElMessage.success('提交成功')
      }
    } catch (e) {
      ElMessage.error(e?.response?.data?.detail || '提交失败')
    } finally {
      submitting.value = false
    }
  }

  return {
    loading, error, submitting, form, specParts,
    groups, readonlyFields, mode, submitTarget,
    history, coilSeq, lastCoilData,
    workshopName, shiftName, businessDate,
    initSpecParts, syncSpec, loadData, handleSubmit
  }
}
```

- [ ] **Step 2: Update UnifiedEntryForm.vue** — remove all extracted state and functions. Replace with:

```js
import { useUnifiedEntryForm } from '../../composables/useUnifiedEntryForm'
import { computeReadonly } from '../../utils/unifiedEntryHelpers'

const {
  loading, error, submitting, form, specParts,
  groups, readonlyFields, mode, submitTarget,
  history, coilSeq, lastCoilData,
  workshopName, shiftName, businessDate,
  initSpecParts, syncSpec, loadData, handleSubmit
} = useUnifiedEntryForm()
```

Keep in the SFC: `roleLabel`, `roleColor`, `ROLE_COLORS` (UI-only), `summarize` (template helper), `handleSplitCoil` (uses `form`, `groups`, `lastCoilData`, `initSpecParts` from composable).

Update template: `computeReadonly(rf)` → `computeReadonly(rf, form)`.

- [ ] **Step 3: Verify** — `cd frontend && npx vite build`

- [ ] **Step 4: Commit** — `git add frontend/src/utils/unifiedEntryHelpers.js frontend/src/composables/useUnifiedEntryForm.js frontend/src/views/mobile/UnifiedEntryForm.vue && git commit -m "refactor(UnifiedEntryForm): extract helpers and composable, reuse fieldValueHelpers"`

---

## Final Verification

- [ ] **Step 1:** `cd frontend && npx vite build` — clean build, zero warnings
- [ ] **Step 2:** Line count check:

| File | Before | After | Reduction |
|------|--------|-------|-----------|
| FactoryDirector.vue | 1259 | ~750 | ~509 |
| ShiftReportForm.vue | 877 | ~550 | ~327 |
| LiveDashboard.vue | 831 | ~480 | ~351 |
| UnifiedEntryForm.vue | 705 | ~480 | ~225 |
| **Total** | **3672** | **~2260** | **~1412** |

- [ ] **Step 3:** Verify no duplicate function names across new utils files
- [ ] **Step 4:** Verify all new files follow existing naming conventions (`camelCase` for utils, `use` prefix for composables)
