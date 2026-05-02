# Management Overview Clarity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework the management home and cost center so a manager can scan production, loss, operating estimate, and blockers without reading implementation details.

**Architecture:** Keep the existing Vue 3 / Element Plus frontend and existing dashboard APIs. Add one small pure utility to normalize management overview numbers, then use it in `LiveDashboard.vue`; expose the existing cost route in navigation and simplify `CostAccountingCenter.vue` first-screen layout while moving strategy JSON/table snapshots into an advanced section.

**Tech Stack:** Vue 3 Composition API, Element Plus, Node test runner (`node --test`), Playwright, existing backend dashboard payloads.

---

## Scope

This plan changes frontend information architecture only. It does not add backend tables, pricing services, accounting workflows, or official finance settlement logic. "毛利估算" remains an operating estimate derived from existing `management_estimate` or local cost strategy inputs.

## File Structure

- Modify: `frontend/src/config/manage-navigation.js`
  - Add a visible `经营效益` navigation group with `/manage/cost`.
  - Keep manager/admin visibility consistent with existing review surfaces.

- Create: `frontend/src/utils/managementOverview.js`
  - Normalize production, loss, margin estimate, and blocker counts from existing dashboard/live aggregation payloads.
  - Keep logic pure for direct unit tests.

- Modify: `frontend/src/views/reports/LiveDashboard.vue`
  - Load factory dashboard and delivery status together with live aggregation.
  - Replace the first-screen KPI strip with standard management metrics:
    `今日产量`, `损耗重量`, `成材率`, `毛利估算`, `待处理`.
  - Add a compact `经营链路` row:
    `投入 -> 生产 -> 损耗 -> 入库/发货 -> 成本/毛利 -> 日报交付`.
  - Keep the existing machine/shift matrix below as operational detail.

- Modify: `frontend/src/views/review/CostAccountingCenter.vue`
  - Make the first screen a normal "经营估算" ledger:
    `收入估算`, `成本估算`, `毛利估算`, `每吨成本`, `主要成本项`.
  - Move JSON strategy parameters, table snapshots, and variance records into a collapsed `高级参数` area.

- Modify: `frontend/e2e/helpers/review-mocks.js`
  - Add non-zero `management_estimate` mock values so visual and e2e checks show meaningful profit/loss state.

- Modify: `frontend/tests/managementCommandCenter.test.js`
  - Update navigation expectations.
  - Add source-level guards for first-screen labels if needed.

- Create: `frontend/tests/managementOverviewClarity.test.js`
  - Test the pure overview builder for production/loss/margin/blocker behavior.

- Modify: `frontend/e2e/manage-shell.spec.js`
  - Confirm the `经营效益`/`成本效益` navigation entry is visible and routes to `/manage/cost`.

---

### Task 1: Add Failing Tests For Navigation And Overview Semantics

**Files:**
- Modify: `frontend/tests/managementCommandCenter.test.js`
- Create: `frontend/tests/managementOverviewClarity.test.js`

- [ ] **Step 1: Update navigation test to expect cost entry**

In `frontend/tests/managementCommandCenter.test.js`, update `manageNavGroups keeps the manager surface focused on daily factory work`:

```js
assert.deepEqual(groups.map((group) => group.label), [
  '总览',
  '工厂状态',
  '经营效益',
  '填报审核',
  '日报交付',
  '异常质量',
])

const items = groups.flatMap((group) => group.items)
assert.equal(items.some((item) => item.path === '/manage/cost'), true)
assert.equal(items.some((item) => item.shortLabel === '成本效益'), true)
```

- [ ] **Step 2: Create pure overview utility tests**

Create `frontend/tests/managementOverviewClarity.test.js`:

```js
import test from 'node:test'
import assert from 'node:assert/strict'

import { buildManagementOverview, marginTone } from '../src/utils/managementOverview.js'

test('buildManagementOverview exposes management first-screen metrics', () => {
  const overview = buildManagementOverview({
    aggregation: {
      overall_progress: {
        submitted_cells: 6,
        total_cells: 8,
        missing_cell_count: 2,
        attention_cell_count: 1,
      },
      factory_total: {
        input: 220,
        output: 214,
        scrap: 6,
        yield_rate: 97.27,
      },
    },
    dashboard: {
      management_estimate: {
        estimate_ready: true,
        estimated_revenue: 280000,
        estimated_cost: 210000,
        estimated_margin: 70000,
      },
      exception_lane: {
        returned_shift_count: 1,
        reminder_late_count: 1,
        pending_report_publish_count: 1,
      },
    },
    delivery: {
      delivery_ready: false,
      missing_steps: ['日报未生成'],
    },
  })

  assert.equal(overview.outputWeight, 214)
  assert.equal(overview.lossWeight, 6)
  assert.equal(overview.lossRate, 2.73)
  assert.equal(overview.yieldRate, 97.27)
  assert.equal(overview.estimatedMargin, 70000)
  assert.equal(overview.blockerCount, 6)
  assert.equal(overview.deliveryReady, false)
})

test('buildManagementOverview falls back cleanly when estimate is not configured', () => {
  const overview = buildManagementOverview({
    aggregation: {
      factory_total: { output: 12, scrap: 0, yield_rate: null },
      overall_progress: { submitted_cells: 1, total_cells: 1 },
    },
    dashboard: {},
    delivery: { delivery_ready: true },
  })

  assert.equal(overview.estimateReady, false)
  assert.equal(overview.estimatedMargin, null)
  assert.equal(overview.marginLabel, '待配置')
  assert.equal(marginTone(null), 'muted')
})

test('marginTone maps operating estimate to readable states', () => {
  assert.equal(marginTone(100), 'success')
  assert.equal(marginTone(0), 'neutral')
  assert.equal(marginTone(-1), 'danger')
  assert.equal(marginTone(null), 'muted')
})
```

- [ ] **Step 3: Run tests and confirm they fail**

Run:

```bash
npm --prefix frontend test
```

Expected:
- `managementOverviewClarity.test.js` fails because `frontend/src/utils/managementOverview.js` does not exist.
- `managementCommandCenter.test.js` fails because navigation does not include `经营效益`.

---

### Task 2: Expose Cost Center In Management Navigation

**Files:**
- Modify: `frontend/src/config/manage-navigation.js`

- [ ] **Step 1: Import a cost-suitable icon**

Modify the icon import:

```js
import {
  Coin,
  Connection,
  Document,
  Grid,
  List,
  Monitor,
  Printer,
  Setting,
  Tickets,
  TrendCharts,
  Upload,
  Warning
} from '@element-plus/icons-vue'
```

- [ ] **Step 2: Add the `经营效益` group after `工厂状态`**

Insert this group between `工厂状态` and `填报审核`:

```js
{
  label: '经营效益',
  commandGroup: '经营效益',
  items: [
    {
      title: '成本核算与效益中心',
      shortLabel: '成本效益',
      path: '/manage/cost',
      icon: Coin,
      access: 'review',
      commandGroup: '经营效益',
      secondaryGroup: '估算'
    }
  ]
},
```

- [ ] **Step 3: Run navigation test**

Run:

```bash
npm --prefix frontend test -- tests/managementCommandCenter.test.js
```

Expected: navigation-related assertions pass; overview utility tests still fail until Task 3.

- [ ] **Step 4: Commit navigation change**

```bash
git add frontend/src/config/manage-navigation.js frontend/tests/managementCommandCenter.test.js
git commit -m "feat: expose cost center in management navigation"
```

---

### Task 3: Implement Management Overview Normalizer

**Files:**
- Create: `frontend/src/utils/managementOverview.js`
- Test: `frontend/tests/managementOverviewClarity.test.js`

- [ ] **Step 1: Create the utility file**

Create `frontend/src/utils/managementOverview.js`:

```js
export function numberValue(value, fallback = 0) {
  if (value === null || value === undefined || value === '') return fallback
  const number = Number(value)
  return Number.isFinite(number) ? number : fallback
}

function rounded(value, digits = 2) {
  if (value === null || value === undefined) return null
  const number = Number(value)
  if (!Number.isFinite(number)) return null
  return Number(number.toFixed(digits))
}

function countMissingCells(aggregation) {
  const progress = aggregation?.overall_progress || {}
  if (progress.missing_cell_count !== undefined) return numberValue(progress.missing_cell_count, 0)
  const total = numberValue(progress.total_cells, 0)
  const submitted = numberValue(progress.submitted_cells, 0)
  return Math.max(total - submitted, 0)
}

export function marginTone(value) {
  if (value === null || value === undefined) return 'muted'
  const number = Number(value)
  if (!Number.isFinite(number)) return 'muted'
  if (number > 0) return 'success'
  if (number < 0) return 'danger'
  return 'neutral'
}

export function buildManagementOverview({ aggregation = {}, dashboard = {}, delivery = {} } = {}) {
  const factoryTotal = aggregation.factory_total || {}
  const leaderMetrics = dashboard.leader_metrics || {}
  const estimate = dashboard.management_estimate || {}
  const exceptionLane = dashboard.exception_lane || {}
  const progress = aggregation.overall_progress || {}

  const inputWeight = numberValue(factoryTotal.input, null)
  const outputWeight = numberValue(
    factoryTotal.output,
    numberValue(leaderMetrics.today_total_output, 0)
  )
  const lossWeight = numberValue(factoryTotal.scrap, 0)
  const lossRate = inputWeight && inputWeight > 0
    ? rounded((lossWeight / inputWeight) * 100)
    : null
  const yieldRate = rounded(numberValue(factoryTotal.yield_rate, numberValue(leaderMetrics.yield_rate, null)))

  const estimatedRevenue = rounded(numberValue(
    estimate.estimated_revenue,
    numberValue(leaderMetrics.estimated_revenue, null)
  ))
  const estimatedCost = rounded(numberValue(
    estimate.estimated_cost,
    numberValue(leaderMetrics.estimated_cost, null)
  ))
  const estimatedMargin = rounded(numberValue(
    estimate.estimated_margin,
    numberValue(leaderMetrics.estimated_margin, null)
  ))
  const estimateReady = Boolean(estimate.estimate_ready) || estimatedMargin !== null

  const missingCells = countMissingCells(aggregation)
  const attentionCells = numberValue(progress.attention_cell_count, 0)
  const returnedShifts = numberValue(exceptionLane.returned_shift_count, 0)
  const lateReminders = numberValue(exceptionLane.reminder_late_count, 0)
  const pendingPublish = numberValue(exceptionLane.pending_report_publish_count, 0)
  const deliveryReady = Boolean(delivery.delivery_ready ?? dashboard.delivery_ready)
  const deliveryBlocker = deliveryReady ? 0 : 1
  const blockerCount = missingCells + attentionCells + returnedShifts + lateReminders + pendingPublish + deliveryBlocker

  return {
    inputWeight,
    outputWeight,
    lossWeight,
    lossRate,
    yieldRate,
    estimatedRevenue,
    estimatedCost,
    estimatedMargin,
    estimateReady,
    marginLabel: estimateReady ? (estimatedMargin >= 0 ? '毛利估算' : '亏损估算') : '待配置',
    missingCells,
    attentionCells,
    deliveryReady,
    blockerCount,
    deliveryMissingSteps: delivery.missing_steps || dashboard.delivery_status?.missing_steps || [],
  }
}
```

- [ ] **Step 2: Run utility tests**

Run:

```bash
npm --prefix frontend test -- tests/managementOverviewClarity.test.js
```

Expected: all tests in `managementOverviewClarity.test.js` pass.

- [ ] **Step 3: Run full frontend unit tests**

Run:

```bash
npm --prefix frontend test
```

Expected: all frontend unit tests pass.

- [ ] **Step 4: Commit utility**

```bash
git add frontend/src/utils/managementOverview.js frontend/tests/managementOverviewClarity.test.js
git commit -m "feat: normalize management overview metrics"
```

---

### Task 4: Rework Management Home First Screen

**Files:**
- Modify: `frontend/src/views/reports/LiveDashboard.vue`
- Test: `frontend/tests/managementCommandCenter.test.js`

- [ ] **Step 1: Add source guard test for clear labels**

In `frontend/tests/managementCommandCenter.test.js`, add a static test:

```js
test('LiveDashboard first screen uses management-readable labels', () => {
  assert.match(liveDashboardSource, /今日产量/)
  assert.match(liveDashboardSource, /损耗重量/)
  assert.match(liveDashboardSource, /成材率/)
  assert.match(liveDashboardSource, /毛利估算|亏损估算/)
  assert.match(liveDashboardSource, /待处理/)
  assert.match(liveDashboardSource, /经营链路/)
})
```

- [ ] **Step 2: Run test and confirm it fails**

Run:

```bash
npm --prefix frontend test -- tests/managementCommandCenter.test.js
```

Expected: new label test fails because the current template still uses `今日产出`, `缺报单元`, and the old KPI strip.

- [ ] **Step 3: Import dashboard APIs and overview utility**

In `frontend/src/views/reports/LiveDashboard.vue`, add imports:

```js
import { fetchDeliveryStatus, fetchFactoryDashboard } from '../../api/dashboard'
import { buildManagementOverview, marginTone } from '../../utils/managementOverview'
```

- [ ] **Step 4: Add reactive state and computed summary**

Add near the existing refs:

```js
const factorySnapshot = ref({})
const deliverySnapshot = ref({})
```

Add computed values:

```js
const managementOverview = computed(() => buildManagementOverview({
  aggregation: aggregation.value,
  dashboard: factorySnapshot.value,
  delivery: deliverySnapshot.value
}))

const marginToneClass = computed(() => `is-${marginTone(managementOverview.value.estimatedMargin)}`)
```

- [ ] **Step 5: Load dashboard snapshot with live aggregation**

Replace `loadAggregation` internals so non-silent loads still set `loading`, but fetch three payloads together:

```js
const [liveData, factoryData, deliveryData] = await Promise.all([
  fetchLiveAggregation({
    business_date: targetDate.value,
    workshop_id: streamScope.value === 'all' ? undefined : Number(streamScope.value)
  }),
  fetchFactoryDashboard({ target_date: targetDate.value }),
  fetchDeliveryStatus({ target_date: targetDate.value })
])

aggregation.value = liveData
factorySnapshot.value = factoryData
deliverySnapshot.value = deliveryData
lastLoadedAt.value = new Date().toISOString()
activePanels.value = sortWorkshopsForCommandCenter(liveData.workshops || []).map((item) => String(item.workshop_id))
```

- [ ] **Step 6: Replace first KPI strip template**

Replace the current `command-status-strip` top cards with:

```vue
<section class="management-overview-strip">
  <article class="management-overview-card management-overview-card--primary">
    <span>今日产量</span>
    <strong>{{ formatWeight(managementOverview.outputWeight) }}</strong>
    <em>吨</em>
  </article>
  <article class="management-overview-card">
    <span>损耗重量</span>
    <strong>{{ formatWeight(managementOverview.lossWeight) }}</strong>
    <em>{{ managementOverview.lossRate == null ? '损耗率 --' : `损耗率 ${formatPercent(managementOverview.lossRate)}` }}</em>
  </article>
  <article class="management-overview-card">
    <span>成材率</span>
    <strong :class="yieldToneClass(managementOverview.yieldRate)">{{ formatPercent(managementOverview.yieldRate) }}</strong>
    <em>{{ commandSummary.dataSourceLabel }}</em>
  </article>
  <article class="management-overview-card" :class="marginToneClass">
    <span>{{ managementOverview.marginLabel }}</span>
    <strong>{{ managementOverview.estimatedMargin == null ? '--' : `¥ ${formatWeight(managementOverview.estimatedMargin)}` }}</strong>
    <em>经营估算</em>
  </article>
  <article class="management-overview-card" :class="{ 'is-danger': managementOverview.blockerCount > 0 }">
    <span>待处理</span>
    <strong>{{ managementOverview.blockerCount }}</strong>
    <em>{{ managementOverview.deliveryReady ? '交付可用' : '交付待补齐' }}</em>
  </article>
</section>
```

- [ ] **Step 7: Add compact flow below KPI strip**

Add after the overview strip:

```vue
<section class="management-flow" aria-label="经营链路">
  <div class="management-flow__head">
    <strong>经营链路</strong>
    <span>{{ targetDate }}</span>
  </div>
  <div class="management-flow__nodes">
    <div class="management-flow__node">
      <span>投入</span>
      <strong>{{ formatWeight(managementOverview.inputWeight) }}</strong>
    </div>
    <div class="management-flow__node">
      <span>生产</span>
      <strong>{{ formatWeight(managementOverview.outputWeight) }}</strong>
    </div>
    <div class="management-flow__node">
      <span>损耗</span>
      <strong>{{ formatWeight(managementOverview.lossWeight) }}</strong>
    </div>
    <div class="management-flow__node">
      <span>成本/毛利</span>
      <strong>{{ managementOverview.estimatedMargin == null ? '待配置' : managementOverview.marginLabel }}</strong>
    </div>
    <div class="management-flow__node">
      <span>日报交付</span>
      <strong>{{ managementOverview.deliveryReady ? '可交付' : '待补齐' }}</strong>
    </div>
  </div>
</section>
```

- [ ] **Step 8: Keep old matrix but rename section boundary**

Before the collapse area, add a small section title if needed:

```vue
<div class="live-dashboard__section-title">
  <strong>机列填报明细</strong>
  <span>{{ commandSummary.submittedCells }}/{{ commandSummary.totalCells }} 班次</span>
</div>
```

- [ ] **Step 9: Add CSS for the new overview**

Use existing visual language and avoid new dependencies. Add styles in the scoped style block:

```css
.management-overview-strip {
  display: grid;
  grid-template-columns: minmax(240px, 1.35fr) repeat(4, minmax(150px, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}

.management-overview-card {
  display: grid;
  align-content: space-between;
  min-height: 112px;
  padding: 15px;
  border: 1px solid var(--command-line);
  border-radius: var(--command-radius);
  background: var(--command-panel);
  box-shadow: 0 14px 32px rgba(25, 62, 118, 0.07);
}

.management-overview-card--primary {
  border-color: transparent;
  background: linear-gradient(135deg, rgba(9, 96, 238, 0.98), rgba(15, 142, 234, 0.96));
  color: #fff;
}

.management-overview-card span,
.management-flow__node span {
  color: var(--xt-text-muted);
  font-size: 12px;
  font-weight: 850;
}

.management-overview-card strong {
  color: var(--command-ink);
  font-family: var(--xt-font-number);
  font-size: 30px;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0;
  line-height: 1;
}

.management-overview-card--primary span,
.management-overview-card--primary strong,
.management-overview-card--primary em {
  color: rgba(255, 255, 255, 0.92);
}

.management-overview-card em {
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-style: normal;
  font-weight: 800;
}

.management-overview-card.is-success {
  border-color: rgba(22, 138, 85, 0.24);
}

.management-overview-card.is-danger {
  border-color: rgba(194, 65, 52, 0.24);
}

.management-overview-card.is-muted {
  background: var(--xt-bg-panel-muted);
}

.management-flow {
  display: grid;
  gap: 12px;
  margin-bottom: 12px;
  padding: 14px;
  border: 1px solid var(--command-line);
  border-radius: var(--command-radius);
  background: #fff;
}

.management-flow__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.management-flow__nodes {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
}

.management-flow__node {
  position: relative;
  display: grid;
  gap: 4px;
  min-height: 64px;
  padding: 10px;
  border: 1px solid var(--command-line);
  border-radius: var(--command-radius-sm);
  background: var(--command-blue-soft);
}

.management-flow__node strong {
  color: var(--command-blue-deep);
  font-size: 14px;
  font-weight: 900;
}

.live-dashboard__section-title {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin: 2px 0 10px;
  color: var(--command-ink);
  font-weight: 900;
}
```

Add responsive rules:

```css
@media (max-width: 1200px) {
  .management-overview-strip {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .management-flow__nodes {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .management-overview-strip,
  .management-flow__nodes {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 10: Run unit tests**

Run:

```bash
npm --prefix frontend test
```

Expected: all frontend unit tests pass.

- [ ] **Step 11: Commit management home changes**

```bash
git add frontend/src/views/reports/LiveDashboard.vue frontend/tests/managementCommandCenter.test.js
git commit -m "feat: clarify management overview first screen"
```

---

### Task 5: Simplify Cost Center First Screen

**Files:**
- Modify: `frontend/src/views/review/CostAccountingCenter.vue`
- Test: `frontend/tests/managementCommandCenter.test.js`

- [ ] **Step 1: Add source guard test for cost center labels**

In `frontend/tests/managementCommandCenter.test.js`, read the cost center source:

```js
const costCenterSource = readFileSync(
  new URL('../src/views/review/CostAccountingCenter.vue', import.meta.url),
  'utf8',
)
```

Add:

```js
test('CostAccountingCenter starts with a readable operating ledger', () => {
  assert.match(costCenterSource, /收入估算/)
  assert.match(costCenterSource, /成本估算/)
  assert.match(costCenterSource, /毛利估算/)
  assert.match(costCenterSource, /每吨成本/)
  assert.match(costCenterSource, /高级参数/)
})
```

- [ ] **Step 2: Run test and confirm it fails**

Run:

```bash
npm --prefix frontend test -- tests/managementCommandCenter.test.js
```

Expected: cost source guard fails because the current first screen uses strategy/JSON/table wording.

- [ ] **Step 3: Add revenue assumptions to default scenarios**

In every object returned by `buildDefaultScenario`, add a `revenuePerTon` field. Use one consistent estimate for now:

```js
revenuePerTon: 1200,
```

This is an operating estimate, not settlement data. The value remains editable in the JSON advanced area.

- [ ] **Step 4: Add scenario parsing helpers**

Add after `const result = ref(...)`:

```js
function parseScenarioPayload() {
  try {
    return JSON.parse(scenarioJson.value || '{}')
  } catch {
    return {}
  }
}

function sumOutputTon(rows = []) {
  return rows.reduce((sum, row) => sum + Number(row.outputTon || 0), 0)
}

const ledgerSummary = computed(() => {
  const scenario = parseScenarioPayload()
  const processOutput = sumOutputTon(result.value.processRows || [])
  const outputTon = Number(scenario.outputTon || processOutput || 0)
  const throughputTon = Number(scenario.throughputTon || outputTon || 0)
  const lossTon = Math.max(throughputTon - outputTon, 0)
  const revenuePerTon = Number(scenario.revenuePerTon || 0)
  const revenue = revenuePerTon > 0 ? outputTon * revenuePerTon : null
  const cost = Number(result.value.totalCost || 0)
  const margin = revenue === null ? null : revenue - cost
  const perTon = caliber.value === 'throughput'
    ? result.value.byThroughputTon
    : result.value.byOutputTon

  return {
    outputTon,
    throughputTon,
    lossTon,
    revenue,
    cost,
    margin,
    perTon,
    majorCost: [...(result.value.breakdown || [])].sort((a, b) => Number(b.value || 0) - Number(a.value || 0))[0] || null,
  }
})
```

- [ ] **Step 5: Replace first `stat-grid` with ledger cards**

Replace the top `stat-grid` with:

```vue
<section class="cost-ledger" data-testid="cost-ledger">
  <article class="cost-ledger__card cost-ledger__card--primary">
    <span>收入估算</span>
    <strong>{{ ledgerSummary.revenue == null ? '--' : `¥ ${formatNumber(ledgerSummary.revenue, 2)}` }}</strong>
    <em>{{ formatNumber(ledgerSummary.outputTon, 2) }} 吨</em>
  </article>
  <article class="cost-ledger__card">
    <span>成本估算</span>
    <strong>¥ {{ formatNumber(ledgerSummary.cost, 2) }}</strong>
    <em>经营口径</em>
  </article>
  <article class="cost-ledger__card" :class="{ 'is-loss': ledgerSummary.margin != null && ledgerSummary.margin < 0 }">
    <span>毛利估算</span>
    <strong>{{ ledgerSummary.margin == null ? '--' : `¥ ${formatNumber(ledgerSummary.margin, 2)}` }}</strong>
    <em>收入 - 成本</em>
  </article>
  <article class="cost-ledger__card">
    <span>每吨成本</span>
    <strong>¥ {{ formatNumber(ledgerSummary.perTon, 2) }}</strong>
    <em>{{ caliber === 'throughput' ? '按通货量' : '按产量' }}</em>
  </article>
  <article class="cost-ledger__card">
    <span>主要成本项</span>
    <strong>{{ ledgerSummary.majorCost?.label || '--' }}</strong>
    <em>{{ ledgerSummary.majorCost ? `¥ ${formatNumber(ledgerSummary.majorCost.value, 2)}` : '暂无' }}</em>
  </article>
</section>
```

- [ ] **Step 6: Add normal process strip**

Add under the ledger:

```vue
<section class="cost-flow">
  <div>
    <span>产量</span>
    <strong>{{ formatNumber(ledgerSummary.outputTon, 2) }} 吨</strong>
  </div>
  <div>
    <span>通货量</span>
    <strong>{{ formatNumber(ledgerSummary.throughputTon, 2) }} 吨</strong>
  </div>
  <div>
    <span>损耗</span>
    <strong>{{ formatNumber(ledgerSummary.lossTon, 2) }} 吨</strong>
  </div>
  <div>
    <span>口径</span>
    <strong>{{ caliber === 'throughput' ? '按通货量' : '按产量' }}</strong>
  </div>
</section>
```

- [ ] **Step 7: Move strategy JSON and table snapshots into advanced collapse**

Wrap the existing strategy JSON card, backend table snapshot, variance records, and price snapshot in:

```vue
<el-collapse class="cost-advanced">
  <el-collapse-item title="高级参数" name="advanced">
    <!-- Existing strategy JSON, table snapshot, variance, and price cards go here. -->
  </el-collapse-item>
</el-collapse>
```

Keep `成本拆解` and `工序拆解` visible below the first screen, because they explain the ledger without exposing raw JSON.

- [ ] **Step 8: Add cost center CSS**

Add:

```css
.cost-ledger {
  display: grid;
  grid-template-columns: minmax(220px, 1.25fr) repeat(4, minmax(150px, 1fr));
  gap: 12px;
}

.cost-ledger__card {
  display: grid;
  gap: 8px;
  min-height: 112px;
  padding: 16px;
  border: 1px solid var(--xt-border-light);
  border-radius: 8px;
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-sm);
}

.cost-ledger__card--primary {
  border-color: transparent;
  background: var(--xt-primary);
  color: var(--xt-text-inverse);
}

.cost-ledger__card span,
.cost-flow span {
  color: var(--xt-text-muted);
  font-size: 12px;
  font-weight: 850;
}

.cost-ledger__card--primary span,
.cost-ledger__card--primary em,
.cost-ledger__card--primary strong {
  color: rgba(255, 255, 255, 0.92);
}

.cost-ledger__card strong {
  color: var(--xt-text);
  font-family: var(--xt-font-number);
  font-size: 26px;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  letter-spacing: 0;
}

.cost-ledger__card em {
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-style: normal;
  font-weight: 800;
}

.cost-ledger__card.is-loss {
  border-color: rgba(194, 65, 52, 0.24);
}

.cost-flow {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  padding: 12px;
  border: 1px solid var(--xt-border-light);
  border-radius: 8px;
  background: var(--xt-bg-panel);
}

.cost-flow div {
  display: grid;
  gap: 4px;
  padding: 10px;
  border-radius: 6px;
  background: var(--xt-bg-panel-soft);
}

@media (max-width: 1100px) {
  .cost-ledger {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .cost-flow {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .cost-ledger,
  .cost-flow {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 9: Run tests**

Run:

```bash
npm --prefix frontend test
```

Expected: all frontend unit tests pass.

- [ ] **Step 10: Commit cost center clarity**

```bash
git add frontend/src/views/review/CostAccountingCenter.vue frontend/tests/managementCommandCenter.test.js
git commit -m "feat: simplify cost center operating ledger"
```

---

### Task 6: Add E2E Coverage And Visual Verification

**Files:**
- Modify: `frontend/e2e/helpers/review-mocks.js`
- Modify: `frontend/e2e/manage-shell.spec.js`

- [ ] **Step 1: Add meaningful management estimate mock**

In `frontend/e2e/helpers/review-mocks.js`, change `leader_metrics` and/or add top-level `management_estimate`:

```js
leader_metrics: {
  today_total_output: 1175,
  energy_per_ton: 234.6,
  in_process_weight: 80,
  storage_finished_weight: 52,
  shipment_weight: 48,
  storage_inbound_area: 960,
  contract_weight: 120,
  estimated_revenue: 280000,
  estimated_cost: 210000,
  estimated_margin: 70000,
  active_contract_count: 3,
  stalled_contract_count: 1,
  active_coil_count: 10,
  yield_rate: 98.2,
  total_attendance: 33
},
management_estimate: {
  estimate_ready: true,
  estimated_revenue: 280000,
  estimated_cost: 210000,
  estimated_margin: 70000,
  energy_cost: 46000,
  labor_cost: 38000,
  active_contract_count: 3,
  stalled_contract_count: 1,
  active_coil_count: 10,
  reporting_rate: 94,
}
```

- [ ] **Step 2: Add manage shell route assertion**

In `frontend/e2e/manage-shell.spec.js`, add:

```js
test('cost center is visible from the management navigation', async ({ page }) => {
  await setupReviewSessionAndMocks(page)
  await page.goto('/manage/overview')

  await expect(page.locator('.xt-manage__nav-item', { hasText: '成本效益' })).toBeVisible()
  await page.locator('.xt-manage__nav-item', { hasText: '成本效益' }).click()
  await expect(page).toHaveURL(/\/manage\/cost$/)
  await expect(page.getByTestId('review-cost-center')).toBeVisible()
  await expect(page.getByText('收入估算')).toBeVisible()
  await expect(page.getByText('毛利估算')).toBeVisible()
})
```

- [ ] **Step 3: Run e2e test against local dev server**

Start dev server if needed:

```bash
npm --prefix frontend run dev -- --host 127.0.0.1 --port 5174
```

Run:

```bash
PLAYWRIGHT_BASE_URL=http://127.0.0.1:5174 npm --prefix frontend run e2e -- e2e/manage-shell.spec.js
```

Expected: all manage shell e2e tests pass.

- [ ] **Step 4: Capture desktop and mobile screenshots**

Use Playwright or the in-app browser to inspect:

- `http://127.0.0.1:5174/manage/overview?desktop=1`
- `http://127.0.0.1:5174/manage/cost?desktop=1`

Expected:
- No horizontal overflow at `1440px`, `900px`, and `390px`.
- First screen shows management metrics before machine matrix.
- Cost center first screen shows ledger cards before advanced parameters.

- [ ] **Step 5: Commit e2e and mock updates**

```bash
git add frontend/e2e/helpers/review-mocks.js frontend/e2e/manage-shell.spec.js
git commit -m "test: cover management cost center clarity"
```

---

### Task 7: Final Validation

**Files:**
- No new files unless a test failure requires a focused fix.

- [ ] **Step 1: Run frontend unit tests**

```bash
npm --prefix frontend test
```

Expected: `23+` tests pass, including the new overview clarity tests.

- [ ] **Step 2: Run frontend production build**

```bash
npm --prefix frontend run build
```

Expected: Vite build succeeds.

- [ ] **Step 3: Run focused e2e**

```bash
PLAYWRIGHT_BASE_URL=http://127.0.0.1:5174 npm --prefix frontend run e2e -- e2e/manage-shell.spec.js
```

Expected: all manage shell e2e tests pass.

- [ ] **Step 4: Check git diff**

```bash
git diff --check
git status --short
```

Expected:
- No whitespace errors.
- Only planned files are modified.
- Pre-existing unrelated untracked files, such as `backend/scripts/deploy_zxtf_update.py`, remain untouched.

- [ ] **Step 5: Final commit if any validation fixes were made**

```bash
git add <validated-files>
git commit -m "chore: validate management overview clarity"
```

Only make this commit if Task 7 required additional changes.

---

## Acceptance Criteria

- `/manage/overview` first screen answers:
  - `今日产量`
  - `损耗重量`
  - `成材率`
  - `毛利估算` or `亏损估算` or `待配置`
  - `待处理`
- `/manage/overview` still includes the existing machine/shift matrix as detail, not as the first mental model.
- Management navigation exposes `/manage/cost` as `成本效益` under `经营效益`.
- `/manage/cost` starts with readable operating ledger cards, not JSON or table model snapshots.
- Strategy JSON, table snapshots, and variance records are still available under `高级参数`.
- Labels use normal management language, not childish copy and not internal implementation terms.
- All relevant unit tests, build, and focused e2e tests pass.

## Rollback Plan

This is a frontend-only information architecture change. Roll back by reverting the commits from Tasks 2 through 6. No database migration, backend state, or production data rollback is required.

## Risk Notes

- `management_estimate` may be absent if runtime estimate config is not set. The UI must show `待配置` instead of fabricating profit.
- Do not call this official profit or accounting result. Use `毛利估算` / `经营估算`.
- Avoid adding new navigation groups beyond `经营效益`; the goal is clarity, not more surfaces.
- Keep mobile layout one-column for the first-screen cards to avoid horizontal overflow.
