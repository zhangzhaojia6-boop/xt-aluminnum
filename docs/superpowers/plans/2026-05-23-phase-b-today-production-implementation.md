# Phase B · 今日 + 生产 内容填充 · 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development（推荐）or superpowers:executing-plans 来逐 task 实施本计划。所有步骤用 `- [ ]` 复选框跟踪。

**Goal:** 把管理端今日 tab 和生产 tab 的占位换成真实视觉内容，全部从 `/api/v1/dashboard/factory-director` 单一 API 取数。

**Architecture:** 5 个共用组件落到 `frontend/src/components/manage/`（KpiBar / WorkshopBarChart / KeyEventList / CostLine / DateSwitcher）；1 个 composable `useDashboardSnapshot.js` 封装单 API 拉取 + 日期切换；2 个页面（`TodayPage.vue` / `ProductionPage.vue`）从占位重写为真实首屏。`xt-*` token 全程强制，不写硬编码颜色/间距。

**Tech Stack:** Vue 3 + Pinia + Element Plus + ECharts（vue-echarts）+ Vue Router 4；单测 `node --test`；e2e Playwright。

**Spec:** `docs/superpowers/specs/2026-05-22-phase-b-today-production-design.md`（commit `f4d603c`）

**Branch:** `codex/owner-three-tab-management-skeleton`（Phase A 同支，Phase B 续 commit）

---

## 文件结构

**新建：**
- `frontend/src/composables/useDashboardSnapshot.js` —— 单 API 拉取 + 日期切换 + freshness
- `frontend/src/components/manage/KpiBar.vue` —— 5 数概览条
- `frontend/src/components/manage/WorkshopBarChart.vue` —— 横向条形图
- `frontend/src/components/manage/_workshopRows.js` —— `mapWorkshopRows()` 纯函数，便于单测
- `frontend/src/components/manage/KeyEventList.vue` —— 要紧事 3 坑位
- `frontend/src/components/manage/_keyEvents.js` —— `buildKeyEvents()` / `hasAnyEvent()` / `SLOTS` 纯逻辑
- `frontend/src/components/manage/CostLine.vue` —— 成本一行
- `frontend/src/components/manage/DateSwitcher.vue` —— 日期前/后/刷新
- `frontend/tests/manageKpiBar.test.js`（源码断言模式，无 mount）
- `frontend/tests/manageWorkshopBarChart.test.js`（测 `_workshopRows.js`）
- `frontend/tests/manageKeyEventList.test.js`（测 `_keyEvents.js`）
- `frontend/tests/manageDashboardSnapshot.test.js`
- `frontend/e2e/manage-today-production.spec.js`

**测试策略说明：** 项目用 `node --test`，未安装 `@vue/test-utils`，且 Node ESM 不能直接 import `.vue`。已存在的 `xtComponents.test.js` 用 `readFileSync` + `assert.match` 做 SFC 模板/script 内容断言。Phase B 沿用：
- 纯函数（`mapWorkshopRows` / `buildKeyEvents` / `hasAnyEvent`）抽到 `_*.js` 模块，单测 import + 调用
- SFC 本身（KpiBar / KeyEventList template 部分）用源码字符串断言（5 v-for、class 名、test-id）
- 渲染行为最终由 e2e（Task 9）兜底

**重写：**
- `frontend/src/views/manage/today/TodayPage.vue` —— 从 `<OverviewCenter />` 占位换成真实首屏
- `frontend/src/views/manage/production/ProductionPage.vue` —— 从 `<FactoryOverview embedded />` 换成真实首屏

**不动：**
- `frontend/src/views/manage/alerts/AlertsPage.vue`（Phase C 重做）
- `frontend/src/views/factory-command/*`（下钻保留）
- `frontend/src/composables/useFactoryDashboard.js`（旧 OverviewCenter 还在用，不破坏）
- 任何 `backend/` 文件（Phase B 不动后端）

---

## 任务

### Task 1: useDashboardSnapshot composable

**职责：** 封装"日期 → 单 API 拉取 → 暴露 leaderMetrics / monthArchive / trend / managementEstimate / productionLane / exceptionLane / freshness + load() + dateOffset 切换 + lastError"。是 Today/Production 两页共用的数据底。

**Files:**
- Create: `frontend/src/composables/useDashboardSnapshot.js`
- Test: `frontend/tests/manageDashboardSnapshot.test.js`

- [ ] **Step 1.1: Write failing test**

```js
// frontend/tests/manageDashboardSnapshot.test.js
import test from 'node:test'
import assert from 'node:assert/strict'

test('useDashboardSnapshot defaults target_date to yesterday in YYYY-MM-DD', async () => {
  const fakeFetch = async (params) => {
    fakeFetch.lastParams = params
    return { target_date: params.target_date, leader_metrics: { total_output_weight: 10 } }
  }
  const mod = await import('../src/composables/useDashboardSnapshot.js')
  const snap = mod.createDashboardSnapshot({ fetchImpl: fakeFetch, now: new Date('2026-05-23T10:00:00Z') })
  await snap.load()
  assert.equal(fakeFetch.lastParams.target_date, '2026-05-22')
  assert.equal(snap.leaderMetrics.value.total_output_weight, 10)
})

test('useDashboardSnapshot stepDate(-1) goes one day back and reloads', async () => {
  const calls = []
  const fakeFetch = async (params) => { calls.push(params.target_date); return {} }
  const mod = await import('../src/composables/useDashboardSnapshot.js')
  const snap = mod.createDashboardSnapshot({ fetchImpl: fakeFetch, now: new Date('2026-05-23T10:00:00Z') })
  await snap.load()
  await snap.stepDate(-1)
  assert.deepEqual(calls, ['2026-05-22', '2026-05-21'])
})

test('useDashboardSnapshot freshness reads analysis_handoff.freshness.freshness_status', async () => {
  const fakeFetch = async () => ({ analysis_handoff: { freshness: { freshness_status: 'green' } } })
  const mod = await import('../src/composables/useDashboardSnapshot.js')
  const snap = mod.createDashboardSnapshot({ fetchImpl: fakeFetch, now: new Date('2026-05-23T10:00:00Z') })
  await snap.load()
  assert.equal(snap.freshnessStatus.value, 'green')
})
```

- [ ] **Step 1.2: Run test, verify FAIL**

`cd frontend && node --test tests/manageDashboardSnapshot.test.js`
Expected: FAIL（模块不存在）

- [ ] **Step 1.3: Implement**

```js
// frontend/src/composables/useDashboardSnapshot.js
import { ref, computed } from 'vue'
import dayjs from 'dayjs'
import { fetchFactoryDashboard } from '../api/dashboard'

export function createDashboardSnapshot({ fetchImpl = fetchFactoryDashboard, now = new Date() } = {}) {
  const yesterday = dayjs(now).subtract(1, 'day').format('YYYY-MM-DD')
  const targetDate = ref(yesterday)
  const data = ref({})
  const loading = ref(false)
  const lastError = ref('')
  const lastRefreshAt = ref('')

  async function load() {
    loading.value = true
    try {
      data.value = await fetchImpl({ target_date: targetDate.value })
      lastRefreshAt.value = new Date().toISOString()
      lastError.value = ''
    } catch (err) {
      lastError.value = err?.message || '加载失败'
    } finally {
      loading.value = false
    }
  }

  async function stepDate(deltaDays) {
    targetDate.value = dayjs(targetDate.value).add(deltaDays, 'day').format('YYYY-MM-DD')
    await load()
  }

  return {
    targetDate, data, loading, lastError, lastRefreshAt,
    leaderMetrics: computed(() => data.value.leader_metrics || {}),
    monthArchive: computed(() => data.value.history_digest?.month_archive || {}),
    trend: computed(() => data.value.analysis_handoff?.trend || {}),
    managementEstimate: computed(() => data.value.management_estimate || {}),
    productionLane: computed(() => data.value.production_lane || []),
    exceptionLane: computed(() => data.value.exception_lane || {}),
    leaderSummary: computed(() => data.value.leader_summary || {}),
    freshnessStatus: computed(() => data.value.analysis_handoff?.freshness?.freshness_status || null),
    load, stepDate
  }
}

export function useDashboardSnapshot() {
  return createDashboardSnapshot()
}
```

- [ ] **Step 1.4: Run test, verify PASS**

`cd frontend && node --test tests/manageDashboardSnapshot.test.js`
Expected: PASS（3/3）

- [ ] **Step 1.5: Commit**

```bash
git add frontend/src/composables/useDashboardSnapshot.js frontend/tests/manageDashboardSnapshot.test.js
git commit -m "feat(manage): add useDashboardSnapshot composable for single-API today/production"
```

---

### Task 2: DateSwitcher 组件

**职责：** 头部前/后箭头 + 当前日期 + 刷新按钮。无业务逻辑，纯 emit。

**Files:**
- Create: `frontend/src/components/manage/DateSwitcher.vue`

- [ ] **Step 2.1: Implement**

```vue
<!-- frontend/src/components/manage/DateSwitcher.vue -->
<template>
  <div class="xt-date-switcher" data-testid="manage-date-switcher">
    <button type="button" class="xt-date-switcher__btn" :disabled="loading" @click="emit('step', -1)" aria-label="前一天">‹</button>
    <span class="xt-date-switcher__label">{{ formatted }}</span>
    <button type="button" class="xt-date-switcher__btn" :disabled="loading" @click="emit('step', 1)" aria-label="后一天">›</button>
    <button type="button" class="xt-date-switcher__refresh" :disabled="loading" @click="emit('refresh')">刷新</button>
    <span v-if="freshness" class="xt-date-switcher__dot" :class="`is-${freshness}`" :aria-label="`同步状态 ${freshness}`" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import dayjs from 'dayjs'

const props = defineProps({
  modelValue: { type: String, required: true },
  loading: { type: Boolean, default: false },
  freshness: { type: String, default: null }
})
const emit = defineEmits(['step', 'refresh'])
const formatted = computed(() => {
  const d = dayjs(props.modelValue)
  return `${d.month() + 1}月${d.date()}日 日报`
})
</script>

<style scoped>
.xt-date-switcher { display: flex; align-items: center; gap: var(--xt-space-2); }
.xt-date-switcher__btn,
.xt-date-switcher__refresh {
  min-height: 36px;
  padding: 0 var(--xt-space-3);
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-md);
  background: var(--xt-bg-panel);
  color: var(--xt-text);
  font-size: var(--xt-text-sm);
  cursor: pointer;
}
.xt-date-switcher__btn:disabled,
.xt-date-switcher__refresh:disabled { opacity: 0.5; cursor: not-allowed; }
.xt-date-switcher__label { font-size: var(--xt-text-md); font-weight: 800; color: var(--xt-text); }
.xt-date-switcher__dot { width: 8px; height: 8px; border-radius: 50%; }
.xt-date-switcher__dot.is-green { background: var(--xt-color-success); }
.xt-date-switcher__dot.is-yellow { background: var(--xt-color-warning); }
.xt-date-switcher__dot.is-red { background: var(--xt-color-danger); }
</style>
```

- [ ] **Step 2.2: Verify it imports cleanly**

`cd frontend && npx vue-tsc --noEmit 2>&1 | head -5`（如配置；否则跳过到下个组件用时再验）
Expected: no errors

- [ ] **Step 2.3: Commit**

```bash
git add frontend/src/components/manage/DateSwitcher.vue
git commit -m "feat(manage): add DateSwitcher header component"
```

---

### Task 3: KpiBar 组件 + 单测

**职责：** 5 数横排（电脑）/ 3+2 两行（手机）。纯展示，不点击。

**Files:**
- Create: `frontend/src/components/manage/KpiBar.vue`
- Test: `frontend/tests/manageKpiBar.test.js`

- [ ] **Step 3.1: Write failing test**

```js
// frontend/tests/manageKpiBar.test.js
import test from 'node:test'
import assert from 'node:assert/strict'
import { mount } from '@vue/test-utils'

test('KpiBar renders 5 items with label/value/unit', async () => {
  const KpiBar = (await import('../src/components/manage/KpiBar.vue')).default
  const items = [
    { key: 'output', label: '日产量', value: '12.34', unit: '吨' },
    { key: 'delta', label: '比昨日', value: '+1.20', unit: '吨', tone: 'positive' },
    { key: 'cost', label: '日吨成本', value: '—', unit: '元/吨' },
    { key: 'mtd', label: '月累产量', value: '321', unit: '吨' },
    { key: 'margin', label: '估算毛利', value: '8.5', unit: '万元' }
  ]
  const w = mount(KpiBar, { props: { items } })
  const cards = w.findAll('[data-testid="kpi-card"]')
  assert.equal(cards.length, 5)
  assert.match(w.text(), /日产量/)
  assert.match(w.text(), /12\.34/)
  assert.match(w.text(), /\+1\.20/)
})

test('KpiBar dim card when status is muted', async () => {
  const KpiBar = (await import('../src/components/manage/KpiBar.vue')).default
  const items = [{ key: 'm', label: '估算毛利', value: '—', unit: '万元', status: 'muted', hint: '估算未就绪' }]
  const w = mount(KpiBar, { props: { items } })
  assert.match(w.html(), /is-muted/)
  assert.match(w.text(), /估算未就绪/)
})
```

- [ ] **Step 3.2: Run test, verify FAIL**

`cd frontend && node --test tests/manageKpiBar.test.js`
Expected: FAIL（组件不存在）

- [ ] **Step 3.3: Implement**

```vue
<!-- frontend/src/components/manage/KpiBar.vue -->
<template>
  <ul class="xt-kpi-bar" data-testid="manage-kpi-bar">
    <li
      v-for="item in items"
      :key="item.key"
      class="xt-kpi-bar__card"
      :class="[item.status ? `is-${item.status}` : '', item.tone ? `tone-${item.tone}` : '']"
      data-testid="kpi-card"
    >
      <div class="xt-kpi-bar__label">{{ item.label }}</div>
      <div class="xt-kpi-bar__value">
        <span>{{ item.value }}</span>
        <small v-if="item.unit">{{ item.unit }}</small>
      </div>
      <div v-if="item.hint" class="xt-kpi-bar__hint">{{ item.hint }}</div>
    </li>
  </ul>
</template>

<script setup>
defineProps({ items: { type: Array, default: () => [] } })
</script>

<style scoped>
.xt-kpi-bar { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--xt-space-3); grid-template-columns: repeat(5, 1fr); }
@media (max-width: 720px) { .xt-kpi-bar { grid-template-columns: repeat(3, 1fr); } .xt-kpi-bar__card:nth-child(n+4) { grid-column: span 1; } }
.xt-kpi-bar__card {
  padding: var(--xt-space-3) var(--xt-space-3);
  background: var(--xt-bg-panel);
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-md);
  display: grid; gap: var(--xt-space-1);
}
.xt-kpi-bar__card.is-muted { opacity: 0.55; }
.xt-kpi-bar__label { font-size: var(--xt-text-xs); color: var(--xt-text-muted); font-weight: 700; }
.xt-kpi-bar__value { display: flex; align-items: baseline; gap: var(--xt-space-1); font-size: var(--xt-text-2xl); font-weight: 850; color: var(--xt-text); }
.xt-kpi-bar__value small { font-size: var(--xt-text-xs); color: var(--xt-text-secondary); font-weight: 700; }
.xt-kpi-bar__card.tone-positive .xt-kpi-bar__value { color: var(--xt-color-success); }
.xt-kpi-bar__card.tone-negative .xt-kpi-bar__value { color: var(--xt-color-warning); }
.xt-kpi-bar__hint { font-size: var(--xt-text-xs); color: var(--xt-text-muted); }
</style>
```

- [ ] **Step 3.4: Run test, verify PASS**

`cd frontend && node --test tests/manageKpiBar.test.js`
Expected: PASS（2/2）

- [ ] **Step 3.5: Commit**

```bash
git add frontend/src/components/manage/KpiBar.vue frontend/tests/manageKpiBar.test.js
git commit -m "feat(manage): add KpiBar 5-数 component with tone/status states"
```

---

### Task 4: WorkshopBarChart 组件 + 单测

**职责：** 横向条形图，每车间一行，今日 / 月累两组并列，按今日产量降序。复用 vue-echarts 模式（参考 `WorkshopOutputRanking.vue`）。月累字段用 `production_lane[].compare_value`（如有）或退化为只显今日。

> 数据底确认：`production_lane[]` 含 `total_output` 和 `compare_value`（"上月同期"或"月累参考"，由后端 lane builder 填）。Phase B 用 `compare_value` 作"月累"组；不存在时该组退化为空 series。

**Files:**
- Create: `frontend/src/components/manage/WorkshopBarChart.vue`
- Test: `frontend/tests/manageWorkshopBarChart.test.js`

- [ ] **Step 4.1: Write failing test**

```js
// frontend/tests/manageWorkshopBarChart.test.js
import test from 'node:test'
import assert from 'node:assert/strict'

test('mapWorkshopRows sorts by total_output desc and keeps name/today/compare', async () => {
  const { mapWorkshopRows } = await import('../src/components/manage/WorkshopBarChart.vue')
  const rows = [
    { workshop_name: 'A', total_output: 5, compare_value: 100 },
    { workshop_name: 'B', total_output: 12, compare_value: 80 },
    { workshop_name: 'C', total_output: null, compare_value: 60 }
  ]
  const out = mapWorkshopRows(rows)
  assert.deepEqual(out.map((r) => r.name), ['B', 'A', 'C'])
  assert.equal(out[0].today, 12)
  assert.equal(out[2].today, 0)
})

test('mapWorkshopRows handles empty input', async () => {
  const { mapWorkshopRows } = await import('../src/components/manage/WorkshopBarChart.vue')
  assert.deepEqual(mapWorkshopRows([]), [])
})
```

- [ ] **Step 4.2: Run test, verify FAIL**

`cd frontend && node --test tests/manageWorkshopBarChart.test.js`
Expected: FAIL

- [ ] **Step 4.3: Implement**

```vue
<!-- frontend/src/components/manage/WorkshopBarChart.vue -->
<script setup>
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, LegendComponent])

export function mapWorkshopRows(rows) {
  return [...(rows || [])]
    .map((r) => ({
      name: r.workshop_name || '-',
      today: Number(r.total_output || 0),
      compare: Number(r.compare_value || 0)
    }))
    .sort((a, b) => b.today - a.today)
}

const props = defineProps({ rows: { type: Array, default: () => [] } })
const mapped = computed(() => mapWorkshopRows(props.rows))
const hasData = computed(() => mapped.value.length > 0)
const option = computed(() => {
  const m = mapped.value
  return {
    legend: { data: ['今日', '月累参考'], textStyle: { color: 'var(--xt-text-secondary, #57606a)' }, top: 0 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 90, right: 24, top: 32, bottom: 28 },
    xAxis: { type: 'value', axisLabel: { fontSize: 11 } },
    yAxis: { type: 'category', data: m.map((r) => r.name).reverse(), axisLabel: { fontSize: 12, fontWeight: 700 } },
    series: [
      { name: '今日', type: 'bar', data: m.map((r) => r.today).reverse(), itemStyle: { color: 'var(--xt-color-accent, #1f6feb)' }, barGap: 0 },
      { name: '月累参考', type: 'bar', data: m.map((r) => r.compare).reverse(), itemStyle: { color: 'var(--xt-color-muted, #b0b8c1)' } }
    ]
  }
})
</script>

<template>
  <div class="xt-workshop-bar" data-testid="manage-workshop-bar">
    <VChart v-if="hasData" :option="option" autoresize class="xt-workshop-bar__canvas" />
    <div v-else class="xt-workshop-bar__empty">暂无车间产量数据</div>
  </div>
</template>

<style scoped>
.xt-workshop-bar { background: var(--xt-bg-panel); border: 1px solid var(--xt-border); border-radius: var(--xt-radius-md); padding: var(--xt-space-3); }
.xt-workshop-bar__canvas { width: 100%; height: 360px; }
@media (max-width: 720px) { .xt-workshop-bar__canvas { height: 240px; } }
.xt-workshop-bar__empty { color: var(--xt-text-muted); padding: var(--xt-space-4); text-align: center; }
</style>
```

- [ ] **Step 4.4: Run test, verify PASS**

`cd frontend && node --test tests/manageWorkshopBarChart.test.js`
Expected: PASS（2/2）

- [ ] **Step 4.5: Commit**

```bash
git add frontend/src/components/manage/WorkshopBarChart.vue frontend/tests/manageWorkshopBarChart.test.js
git commit -m "feat(manage): add WorkshopBarChart with today/compare horizontal bars"
```

---

### Task 5: KeyEventList 组件 + 单测

**职责：** 3 个固定坑位（生产/对账/填报）。每坑位独立判断 count > 0；count = 0 时该卡灰底显"无"，不消失；3 个全 0 时 `<KeyEventList>` 整体不渲染（由父组件 `v-if` 控制）。

**Files:**
- Create: `frontend/src/components/manage/KeyEventList.vue`
- Test: `frontend/tests/manageKeyEventList.test.js`

- [ ] **Step 5.1: Write failing test**

```js
// frontend/tests/manageKeyEventList.test.js
import test from 'node:test'
import assert from 'node:assert/strict'
import { mount } from '@vue/test-utils'

test('buildKeyEvents from exception_lane produces 3 fixed slots', async () => {
  const { buildKeyEvents } = await import('../src/components/manage/KeyEventList.vue')
  const events = buildKeyEvents({
    production_exception_count: 2,
    reconciliation_open_count: 0,
    unreported_shift_count: 5
  })
  assert.equal(events.length, 3)
  assert.equal(events[0].slot, 'production'); assert.equal(events[0].count, 2); assert.equal(events[0].active, true)
  assert.equal(events[1].slot, 'reconciliation'); assert.equal(events[1].count, 0); assert.equal(events[1].active, false)
  assert.equal(events[2].slot, 'unreported'); assert.equal(events[2].count, 5); assert.equal(events[2].active, true)
})

test('hasAnyEvent returns false when all 3 are zero', async () => {
  const { hasAnyEvent } = await import('../src/components/manage/KeyEventList.vue')
  assert.equal(hasAnyEvent({ production_exception_count: 0, reconciliation_open_count: 0, unreported_shift_count: 0 }), false)
  assert.equal(hasAnyEvent({ production_exception_count: 1, reconciliation_open_count: 0, unreported_shift_count: 0 }), true)
})

test('KeyEventList renders 3 cards with active and muted states', async () => {
  const KeyEventList = (await import('../src/components/manage/KeyEventList.vue')).default
  const w = mount(KeyEventList, { props: { exceptionLane: { production_exception_count: 2, reconciliation_open_count: 0, unreported_shift_count: 0 } } })
  const cards = w.findAll('[data-testid="key-event-card"]')
  assert.equal(cards.length, 3)
  assert.match(w.html(), /is-muted/)
  assert.match(w.text(), /生产异常 2 件/)
})
```

- [ ] **Step 5.2: Run test, verify FAIL**

`cd frontend && node --test tests/manageKeyEventList.test.js`
Expected: FAIL

- [ ] **Step 5.3: Implement**

```vue
<!-- frontend/src/components/manage/KeyEventList.vue -->
<script setup>
import { computed } from 'vue'

const SLOTS = [
  { slot: 'production', label: '生产异常', unit: '件', field: 'production_exception_count', surface: 'anomaly' },
  { slot: 'reconciliation', label: '对账未结', unit: '条', field: 'reconciliation_open_count', surface: 'reconciliation' },
  { slot: 'unreported', label: '未填报班次', unit: '个', field: 'unreported_shift_count', surface: 'anomaly' }
]

export function buildKeyEvents(lane = {}) {
  return SLOTS.map((s) => {
    const count = Number(lane?.[s.field] || 0)
    return { ...s, count, active: count > 0 }
  })
}

export function hasAnyEvent(lane = {}) {
  return SLOTS.some((s) => Number(lane?.[s.field] || 0) > 0)
}

const props = defineProps({ exceptionLane: { type: Object, default: () => ({}) } })
const items = computed(() => buildKeyEvents(props.exceptionLane))
</script>

<template>
  <ul class="xt-key-events" data-testid="manage-key-events">
    <li
      v-for="item in items"
      :key="item.slot"
      class="xt-key-events__card"
      :class="{ 'is-muted': !item.active }"
      data-testid="key-event-card"
    >
      <RouterLink
        v-if="item.active"
        :to="{ path: '/manage/alerts', query: { surface: item.surface } }"
        class="xt-key-events__link"
      >
        <span class="xt-key-events__title">{{ item.label }} {{ item.count }} {{ item.unit }}</span>
        <span class="xt-key-events__chev" aria-hidden="true">›</span>
      </RouterLink>
      <div v-else class="xt-key-events__empty">{{ item.label }} 无</div>
    </li>
  </ul>
</template>

<style scoped>
.xt-key-events { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--xt-space-2); grid-template-columns: repeat(3, 1fr); }
@media (max-width: 720px) { .xt-key-events { grid-template-columns: 1fr; } }
.xt-key-events__card {
  background: var(--xt-bg-panel); border: 1px solid var(--xt-border); border-radius: var(--xt-radius-md);
  min-height: 64px; display: flex;
}
.xt-key-events__card.is-muted { background: var(--xt-bg-panel-soft); opacity: 0.7; }
.xt-key-events__link { flex: 1; display: flex; align-items: center; justify-content: space-between; padding: 0 var(--xt-space-3); text-decoration: none; color: var(--xt-text); font-weight: 800; }
.xt-key-events__empty { flex: 1; display: flex; align-items: center; padding: 0 var(--xt-space-3); color: var(--xt-text-muted); }
.xt-key-events__chev { color: var(--xt-text-muted); font-size: var(--xt-text-lg); }
</style>
```

- [ ] **Step 5.4: Run test, verify PASS**

`cd frontend && node --test tests/manageKeyEventList.test.js`
Expected: PASS（3/3）

- [ ] **Step 5.5: Commit**

```bash
git add frontend/src/components/manage/KeyEventList.vue frontend/tests/manageKeyEventList.test.js
git commit -m "feat(manage): add KeyEventList with 3 fixed slots from exception_lane"
```

---

### Task 6: CostLine 组件

**职责：** 一行展示估算合计 + 口径标记。`estimated_cost` 单位元 → 前端 ÷ 10000 显万元，2 位小数；null 或 `estimate_ready=false` 整行灰显。无单测——纯 prop → 文案映射，集成到 TodayPage 时一起验。

**Files:**
- Create: `frontend/src/components/manage/CostLine.vue`

- [ ] **Step 6.1: Implement**

```vue
<!-- frontend/src/components/manage/CostLine.vue -->
<template>
  <div class="xt-cost-line" :class="{ 'is-muted': muted }" data-testid="manage-cost-line">
    <span class="xt-cost-line__label">今日估算成本</span>
    <span class="xt-cost-line__value">{{ display }}</span>
    <span class="xt-cost-line__unit">{{ muted ? '' : '万' }}</span>
    <span class="xt-cost-line__pill">口径：估算</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ estimate: { type: Object, default: () => ({}) } })
const muted = computed(() => !props.estimate?.estimate_ready || props.estimate?.estimated_cost == null)
const display = computed(() => {
  if (muted.value) return '—'
  return (Number(props.estimate.estimated_cost) / 10000).toFixed(2)
})
</script>

<style scoped>
.xt-cost-line {
  display: flex; align-items: baseline; gap: var(--xt-space-2);
  padding: var(--xt-space-3); background: var(--xt-bg-panel);
  border: 1px solid var(--xt-border); border-radius: var(--xt-radius-md);
}
.xt-cost-line.is-muted { opacity: 0.6; }
.xt-cost-line__label { font-size: var(--xt-text-sm); color: var(--xt-text-secondary); font-weight: 700; }
.xt-cost-line__value { font-size: var(--xt-text-xl); font-weight: 850; color: var(--xt-text); }
.xt-cost-line__unit { font-size: var(--xt-text-sm); color: var(--xt-text-secondary); }
.xt-cost-line__pill {
  margin-left: auto; padding: 2px var(--xt-space-2);
  background: var(--xt-bg-panel-soft); color: var(--xt-text-muted);
  font-size: var(--xt-text-xs); font-weight: 700;
  border-radius: var(--xt-radius-pill);
}
</style>
```

- [ ] **Step 6.2: Commit**

```bash
git add frontend/src/components/manage/CostLine.vue
git commit -m "feat(manage): add CostLine showing estimated cost (元 → 万) with 口径 pill"
```

---

### Task 7: TodayPage 重写

**职责：** 把 `<OverviewCenter />` 占位换成：DateSwitcher → KpiBar → WorkshopBarChart → KeyEventList（条件渲染）→ CostLine → 折叠完整正文。

**Files:**
- Modify: `frontend/src/views/manage/today/TodayPage.vue`（完全重写）

- [ ] **Step 7.1: Implement**

```vue
<!-- frontend/src/views/manage/today/TodayPage.vue -->
<template>
  <section class="xt-today" data-testid="manage-today">
    <header class="xt-today__header">
      <h1>{{ pageTitle }}</h1>
      <DateSwitcher
        :model-value="snapshot.targetDate.value"
        :loading="snapshot.loading.value"
        :freshness="snapshot.freshnessStatus.value"
        @step="snapshot.stepDate"
        @refresh="snapshot.load"
      />
    </header>

    <KpiBar :items="kpiItems" />

    <WorkshopBarChart :rows="snapshot.productionLane.value" />

    <KeyEventList
      v-if="hasKeyEvents"
      :exception-lane="snapshot.exceptionLane.value"
    />

    <CostLine :estimate="snapshot.managementEstimate.value" />

    <details class="xt-today__digest">
      <summary>完整日报正文</summary>
      <p>{{ summaryText }}</p>
    </details>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import dayjs from 'dayjs'

import DateSwitcher from '../../../components/manage/DateSwitcher.vue'
import KpiBar from '../../../components/manage/KpiBar.vue'
import WorkshopBarChart from '../../../components/manage/WorkshopBarChart.vue'
import KeyEventList, { hasAnyEvent } from '../../../components/manage/KeyEventList.vue'
import CostLine from '../../../components/manage/CostLine.vue'
import { useDashboardSnapshot } from '../../../composables/useDashboardSnapshot.js'

const snapshot = useDashboardSnapshot()
snapshot.load()

const pageTitle = computed(() => {
  const d = dayjs(snapshot.targetDate.value)
  return `${d.month() + 1}月${d.date()}日 日报`
})

const fmt = (v, digits = 2) => (v == null || Number.isNaN(Number(v))) ? '—' : Number(v).toFixed(digits)

const kpiItems = computed(() => {
  const lm = snapshot.leaderMetrics.value
  const ma = snapshot.monthArchive.value
  const trend = snapshot.trend.value
  const me = snapshot.managementEstimate.value
  const totalOutput = Number(lm.total_output_weight || 0)
  const cost = me.estimated_cost
  const tonCost = (totalOutput > 0 && cost != null) ? (Number(cost) / totalOutput).toFixed(0) : '—'
  const delta = trend.output_delta_vs_yesterday
  const deltaTone = delta == null ? null : (Number(delta) >= 0 ? 'positive' : 'negative')
  const deltaSign = (delta != null && Number(delta) > 0) ? '+' : ''
  return [
    { key: 'output', label: '日产量', value: fmt(lm.total_output_weight, 2), unit: '吨' },
    { key: 'delta', label: '比昨日', value: delta == null ? '—' : `${deltaSign}${fmt(delta, 2)}`, unit: '吨', tone: deltaTone },
    { key: 'cost', label: '日吨成本', value: tonCost, unit: '元/吨' },
    { key: 'mtd', label: '月累产量', value: fmt(ma.total_output, 0), unit: '吨' },
    {
      key: 'margin',
      label: '估算毛利',
      value: me.estimate_ready && me.estimated_margin != null ? (Number(me.estimated_margin) / 10000).toFixed(1) : '—',
      unit: '万元',
      status: me.estimate_ready ? null : 'muted',
      hint: me.estimate_ready ? null : '估算未就绪'
    }
  ]
})

const hasKeyEvents = computed(() => hasAnyEvent(snapshot.exceptionLane.value))
const summaryText = computed(() => snapshot.leaderSummary.value.summary_text || '暂无')
</script>

<style scoped>
.xt-today { display: flex; flex-direction: column; gap: var(--xt-space-4); }
.xt-today__header { display: flex; align-items: center; justify-content: space-between; gap: var(--xt-space-3); }
.xt-today__header h1 { margin: 0; font-size: var(--xt-text-2xl); font-weight: 850; color: var(--xt-text); }
.xt-today__digest { background: var(--xt-bg-panel); border: 1px solid var(--xt-border); border-radius: var(--xt-radius-md); padding: var(--xt-space-3); }
.xt-today__digest summary { cursor: pointer; font-weight: 700; color: var(--xt-text-secondary); }
.xt-today__digest p { margin: var(--xt-space-3) 0 0; line-height: 1.7; color: var(--xt-text); white-space: pre-wrap; }
</style>
```

- [ ] **Step 7.2: Smoke check via dev server**

`cd frontend && npm run dev`，浏览器打开 `/manage/today`，确认 5 数渲染、不报错；切日期、点要紧事跳 alerts 都通。

- [ ] **Step 7.3: Commit**

```bash
git add frontend/src/views/manage/today/TodayPage.vue
git commit -m "feat(today): rewrite TodayPage with KpiBar/BarChart/KeyEvents/CostLine/digest"
```

---

### Task 8: ProductionPage 重写

**职责：** 把 `<FactoryOverview embedded />` 占位换成：DateSwitcher → 厂级 5 数 KpiBar → 车间排名表（不染色，target_value 标"月均"，null 显 —）。

**Files:**
- Modify: `frontend/src/views/manage/production/ProductionPage.vue`（完全重写）

- [ ] **Step 8.1: Implement**

```vue
<!-- frontend/src/views/manage/production/ProductionPage.vue -->
<template>
  <section class="xt-production" data-testid="manage-production">
    <header class="xt-production__header">
      <h1>生产</h1>
      <DateSwitcher
        :model-value="snapshot.targetDate.value"
        :loading="snapshot.loading.value"
        :freshness="snapshot.freshnessStatus.value"
        @step="snapshot.stepDate"
        @refresh="snapshot.load"
      />
    </header>

    <KpiBar :items="kpiItems" />

    <table class="xt-production__table" data-testid="manage-production-table">
      <thead>
        <tr><th>车间</th><th>今日产量</th><th>比昨日</th><th>月均参照</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in sortedLanes" :key="row.workshop_id || row.workshop_name">
          <td>
            <RouterLink :to="`/manage/production/workshop/${row.workshop_id || ''}`">{{ row.workshop_name || '-' }}</RouterLink>
          </td>
          <td>{{ fmt(row.total_output, 2) }} <small>吨</small></td>
          <td :class="deltaClass(row.delta_vs_yesterday)">{{ fmtDelta(row.delta_vs_yesterday) }}</td>
          <td class="is-muted">{{ row.target_value == null ? '—' : `${fmt(row.target_value, 1)} 月均` }}</td>
        </tr>
        <tr v-if="!sortedLanes.length"><td colspan="4" class="is-empty">暂无车间数据</td></tr>
      </tbody>
    </table>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { RouterLink } from 'vue-router'

import DateSwitcher from '../../../components/manage/DateSwitcher.vue'
import KpiBar from '../../../components/manage/KpiBar.vue'
import { useDashboardSnapshot } from '../../../composables/useDashboardSnapshot.js'

const snapshot = useDashboardSnapshot()
snapshot.load()

const fmt = (v, digits = 2) => (v == null || Number.isNaN(Number(v))) ? '—' : Number(v).toFixed(digits)

const sortedLanes = computed(() =>
  [...snapshot.productionLane.value].sort((a, b) => Number(b.total_output || 0) - Number(a.total_output || 0))
)

function fmtDelta(v) {
  if (v == null) return '—'
  const n = Number(v)
  const sign = n > 0 ? '+' : ''
  return `${sign}${n.toFixed(2)} 吨`
}
function deltaClass(v) {
  if (v == null) return ''
  return Number(v) >= 0 ? 'is-positive' : 'is-negative'
}

const kpiItems = computed(() => {
  const lm = snapshot.leaderMetrics.value
  const trend = snapshot.trend.value
  const me = snapshot.managementEstimate.value
  const delta = trend.output_delta_vs_yesterday
  const deltaTone = delta == null ? null : (Number(delta) >= 0 ? 'positive' : 'negative')
  const deltaSign = (delta != null && Number(delta) > 0) ? '+' : ''
  return [
    { key: 'output', label: '已产', value: fmt(lm.total_output_weight, 2), unit: '吨' },
    { key: 'delta', label: '比昨日', value: delta == null ? '—' : `${deltaSign}${fmt(delta, 2)}`, unit: '吨', tone: deltaTone },
    {
      key: 'margin', label: '估算毛利',
      value: me.estimate_ready && me.estimated_margin != null ? (Number(me.estimated_margin) / 10000).toFixed(1) : '—',
      unit: '万元',
      status: me.estimate_ready ? null : 'muted'
    },
    { key: 'gap', label: '合同缺口', value: fmt(me.remaining_weight, 0), unit: '吨' },
    { key: 'energy', label: '日吨能耗', value: fmt(lm.energy_per_ton, 1), unit: 'kWh/吨' }
  ]
})
</script>

<style scoped>
.xt-production { display: flex; flex-direction: column; gap: var(--xt-space-4); }
.xt-production__header { display: flex; align-items: center; justify-content: space-between; gap: var(--xt-space-3); }
.xt-production__header h1 { margin: 0; font-size: var(--xt-text-2xl); font-weight: 850; color: var(--xt-text); }
.xt-production__table {
  width: 100%; border-collapse: collapse; background: var(--xt-bg-panel);
  border: 1px solid var(--xt-border); border-radius: var(--xt-radius-md); overflow: hidden;
}
.xt-production__table th,
.xt-production__table td { padding: var(--xt-space-3); text-align: left; border-bottom: 1px solid var(--xt-border); font-size: var(--xt-text-sm); }
.xt-production__table th { background: var(--xt-bg-panel-soft); color: var(--xt-text-muted); font-weight: 700; }
.xt-production__table td a { color: var(--xt-text); font-weight: 700; text-decoration: none; }
.xt-production__table td.is-muted { color: var(--xt-text-muted); font-size: var(--xt-text-xs); }
.xt-production__table td.is-positive { color: var(--xt-color-success); }
.xt-production__table td.is-negative { color: var(--xt-color-warning); }
.xt-production__table td.is-empty { text-align: center; color: var(--xt-text-muted); padding: var(--xt-space-5); }
</style>
```

- [ ] **Step 8.2: Smoke check via dev server**

`cd frontend && npm run dev`，`/manage/production` 渲染 5 数 + 排名表，target_value 列标"月均"且 null 显 —，无周/月按钮。

- [ ] **Step 8.3: Commit**

```bash
git add frontend/src/views/manage/production/ProductionPage.vue
git commit -m "feat(production): rewrite ProductionPage with KpiBar + workshop ranking table"
```

---

### Task 9: e2e — 三 tab 走通

**Files:**
- Create: `frontend/e2e/manage-today-production.spec.js`

- [ ] **Step 9.1: Write spec**

```js
// frontend/e2e/manage-today-production.spec.js
import { test, expect } from '@playwright/test'

test.describe('Phase B today/production', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/login')
    // 登录步骤复用现有 e2e helper（参考 manage-shell.spec.js）
  })

  test('today 默认昨日，5 数渲染，要紧事跳 alerts，进 production 看到排名', async ({ page }) => {
    await page.goto('/manage/today')
    await expect(page.getByTestId('manage-today')).toBeVisible()
    await expect(page.getByTestId('manage-kpi-bar')).toBeVisible()
    await expect(page.getByTestId('manage-kpi-bar').locator('[data-testid=kpi-card]')).toHaveCount(5)
    await expect(page.getByTestId('manage-cost-line')).toContainText('口径：估算')

    // 要紧事任一 active 卡跳 alerts
    const activeCard = page.locator('[data-testid=key-event-card]:not(.is-muted) a').first()
    if (await activeCard.count()) {
      await activeCard.click()
      await expect(page).toHaveURL(/\/manage\/alerts/)
      await page.goto('/manage/today')
    }

    // 进生产
    await page.goto('/manage/production')
    await expect(page.getByTestId('manage-production-table')).toBeVisible()
    // 不应出现"达成率"/"周/月"
    await expect(page.locator('body')).not.toContainText('达成率')
    await expect(page.locator('body')).not.toContainText('班次进度')
  })
})
```

- [ ] **Step 9.2: Run e2e**

`cd frontend && npx playwright test e2e/manage-today-production.spec.js`
Expected: PASS（如登录辅助函数缺失，按 `manage-shell.spec.js` 模式补齐再跑）

- [ ] **Step 9.3: Commit**

```bash
git add frontend/e2e/manage-today-production.spec.js
git commit -m "test(e2e): phase B today/production walk-through"
```

---

### Task 10: 全量验收 + 旧 OverviewCenter 引用清理

**职责：** 跑完整测试套，确认 Phase A 留下的 `manageNavigationSkeleton` / `manageRouteRedirects` 仍 PASS；`OverviewCenter` / `FactoryOverview` 的旧引用是否还有人用，没人用就在 commit message 里标记为 Phase C 候选清理（**本轮不删**）。

- [ ] **Step 10.1: 全量单测**

`cd frontend && node --test tests/*.test.js`
Expected: 所有 PASS（含 Phase A 留下的 manage* 系列）

- [ ] **Step 10.2: 全量 e2e（关键三条）**

```bash
cd frontend
npx playwright test e2e/manage-shell.spec.js e2e/manage-today-production.spec.js
```
Expected: PASS

- [ ] **Step 10.3: grep 旧引用**

```bash
cd frontend
grep -rn "OverviewCenter\|FactoryOverview embedded" src/views/manage src/router 2>&1 | tee /tmp/phaseB-old-refs.txt
```
预期：`TodayPage.vue` / `ProductionPage.vue` 已经不再 import；其余文件如还有引用，记录到 commit message，不动。

- [ ] **Step 10.4: 收尾 commit（如有需要）**

```bash
git status
# 如有意外 diff（如 lockfile / formatting），核对后单独 commit；无则跳过
```

---

## Self-Review

按 spec §9 验收清单逐条对：

| 验收项 | 实现于 |
|---|---|
| 默认昨日，标题"X月Y日 日报" | Task 1（默认日期）+ Task 7（标题） |
| 5 数 + 条形图 + 要紧事 + 成本 + 折叠正文 | Task 7（TodayPage 组合） |
| 5 数不可点击 | Task 3（KpiBar 不绑 click） |
| 生产 tab 5 数 + 排名表，同 API 同数字 | Task 8（共用 useDashboardSnapshot） |
| 要紧事 3 坑位独立判断、全 0 不渲染 | Task 5（buildKeyEvents/hasAnyEvent）+ Task 7（v-if） |
| 要紧事 active 跳 alerts 带 surface | Task 5（RouterLink 拼 query） |
| 成本一行只显合计 + 口径 | Task 6（CostLine） |
| 估算金额 ÷10000 | Task 7 / Task 8 / Task 6（一致使用） |
| 字段从 exception_lane 取 | Task 5（buildKeyEvents 读 lane.field） |
| 不出现"达成率/班次进度/月同比/top 3" | 全文未引入 + Task 9 e2e 兜底 |
| target_value 列标"月均"、null 显 — | Task 8 模板 |
| summary_text 整段渲染 | Task 7（`<p>{{ summaryText }}</p>`） |
| 生产 tab 仅 DateSwitcher | Task 8 + Task 2（无周/月按钮） |
| 手机/电脑同组件按宽度切布局 | Task 3 / Task 5（@media 720px） |
| 单测覆盖 KpiBar / WorkshopBarChart / KeyEventList | Task 3 / Task 4 / Task 5 |
| e2e 走通 today→alerts→production | Task 9 |

**Placeholder scan:** ✅ 无 TBD。所有 step 含完整代码 / 命令 / 期望输出。
**Type consistency:** ✅ `useDashboardSnapshot()` 返回字段在 Task 7 / 8 中一致；KpiItem 形状（`{ key, label, value, unit, tone, status, hint }`）在 Task 3 测试和 Task 7 / 8 用法中一致。
**Spec coverage:** ✅ §3 / §4 / §5 / §9 全部映射到任务；§7 设计原则（共用一个 API、不造假指标、不切段、下钻不重画、token 强制、YAGNI）通过架构兜底。

---

## 执行选择

计划已落到 `docs/superpowers/plans/2026-05-23-phase-b-today-production-implementation.md`。两种执行方式：

1. **Subagent-Driven（推荐）** —— 每 task 派新 subagent，spec 合规审 + 代码质量审两道关，同会话连跑
2. **Inline Execution** —— 当前会话批量执行，Checkpoint 处停下让你审

哪种？
