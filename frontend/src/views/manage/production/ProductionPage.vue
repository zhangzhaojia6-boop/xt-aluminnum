<template>
  <section
    class="xt-production"
    data-testid="manage-production"
    data-visual-pass="stitch-image2-second-pass"
    :data-stitch-project-id="stitchSurface.stitch.projectId"
    :data-stitch-screen-id="stitchSurface.stitch.screenId"
  >
    <header class="xt-production__hero">
      <h1>生产</h1>
      <DateSwitcher
        :model-value="snapshot.targetDate.value"
        :loading="snapshot.loading.value"
        :freshness="snapshot.freshnessStatus.value"
        @step="snapshot.stepDate"
        @refresh="snapshot.load"
        @pick="(d) => snapshot.targetDate.value = d"
      />
    </header>

    <KpiBar :items="kpiItems" />

    <FactorySourceStrip :overview="stitchSurface.sourceOverview" />

    <div v-if="snapshot.lastError.value" class="xt-production__error">{{ snapshot.lastError.value }}</div>

    <div class="xt-production__grid">
      <section class="xt-production__ranking">
        <div class="xt-production__panel-head">
          <h2>车间产量</h2>
          <span v-if="hasMonthlyMarker" class="xt-production__legend"><i aria-hidden="true"></i>月均</span>
        </div>
        <p v-if="rankedRows.length === 0" class="xt-production__empty">无车间数据</p>
        <table v-else class="xt-production__table" data-testid="manage-production-table">
          <thead>
            <tr>
              <th scope="col">车间</th>
              <th scope="col" class="is-chart"><span class="xt-production__sr">产量条</span></th>
              <th scope="col" class="is-num">今日产量</th>
              <th scope="col" class="is-num">比昨日</th>
              <th scope="col" class="is-num">月均参照</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, index) in chartRows" :key="row.key">
              <td>
                <span class="xt-production__workshop">{{ row.name }}</span>
              </td>
              <td class="is-chart">
                <div class="xt-production__bar" aria-hidden="true">
                  <span :style="{ width: `${row.outputRatio * 100}%`, animationDelay: `${index * 50}ms` }"></span>
                  <i v-if="row.markerRatio != null" :style="{ left: `${row.markerRatio * 100}%` }"></i>
                </div>
              </td>
              <td class="is-num is-strong">
                <span>{{ fmt(row.totalOutput, 2) }}</span>
                <small v-if="row.totalOutput != null">吨</small>
              </td>
              <td class="is-num" :class="row.compareTone ? `tone-${row.compareTone}` : ''">
                <template v-if="row.compareValue == null">—</template>
                <template v-else>{{ row.compareArrow }}{{ fmt(Math.abs(row.compareValue), 2) }}</template>
              </td>
              <td class="is-num is-muted">
                <template v-if="row.targetValue == null">—</template>
                <template v-else>{{ fmt(row.targetValue, 2) }} <small>月均</small></template>
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <aside class="xt-production__aside">
        <h2>生产摘要</h2>
        <dl class="xt-production__brief-list">
          <div v-for="item in productionBrief" :key="item.key">
            <dt>{{ item.label }}</dt>
            <dd>{{ item.value }}</dd>
          </div>
        </dl>
      </aside>
    </div>

    <footer class="xt-production__status-bar" data-testid="stitch-bottom-status">
      <div
        v-for="item in bottomStatusItems"
        :key="item.key"
        class="xt-production__status-item"
        :class="item.tone ? `tone-${item.tone}` : ''"
      >
        <span aria-hidden="true"></span>
        <small>{{ item.label }}</small>
        <strong>{{ item.value }}</strong>
      </div>
    </footer>
  </section>
</template>

<script setup>
import { computed } from 'vue'

import DateSwitcher from '../../../components/manage/DateSwitcher.vue'
import KpiBar from '../../../components/manage/KpiBar.vue'
import FactorySourceStrip from '../../../components/manage/FactorySourceStrip.vue'
import { useDashboardSnapshot } from '../../../composables/useDashboardSnapshot.js'
import { buildDailyWipRows, sumWipWeight } from '../../../utils/manageDailyReportSurface.js'
import { buildProductionStitchSurface } from '../../../utils/stitchManageSurface.js'

const snapshot = useDashboardSnapshot()
snapshot.load()

const fmt = (v, digits = 2) =>
  (v == null || Number.isNaN(Number(v)))
    ? '—'
    : Number(v).toLocaleString('zh-CN', {
      minimumFractionDigits: 0,
      maximumFractionDigits: digits,
    })

function sumDailyWorkshopOutput(rows = []) {
  if (!Array.isArray(rows) || rows.length === 0) return null
  let hasValue = false
  const total = rows.reduce((sum, row) => {
    const value = Number(row?.daily_output)
    if (!Number.isFinite(value)) return sum
    hasValue = true
    return sum + value
  }, 0)
  return hasValue ? total : null
}

// 有在执行合同却算出 0，是工单没填合同余量，不是没有缺口
function contractGapKnown(estimate) {
  if (estimate.remaining_weight == null) return false
  return Number(estimate.remaining_weight) !== 0 || !Number(estimate.active_contract_count)
}

const rawKpiItems = computed(() => {
  const lm = snapshot.leaderMetrics.value
  const trend = snapshot.trend.value
  const me = snapshot.managementEstimate.value

  const delta = trend.output_delta_vs_yesterday
  const deltaTone = delta == null ? null : (Number(delta) > 0 ? 'positive' : Number(delta) < 0 ? 'negative' : null)
  const deltaArrow = delta == null ? '' : (Number(delta) > 0 ? '↑' : Number(delta) < 0 ? '↓' : '')
  const deltaText = delta == null ? '—' : `${deltaArrow}${fmt(Math.abs(Number(delta)), 2)}`

  const marginReady = me.estimate_ready !== false && me.estimated_margin != null
  const marginValue = marginReady ? fmt(Number(me.estimated_margin) / 10000, 1) : '—'

  return [
    { key: 'output', label: '包装产量', value: fmt(lm.total_output_weight, 2), unit: '吨' },
    { key: 'delta', label: '比昨日', value: deltaText, unit: '吨', tone: deltaTone },
    {
      key: 'margin',
      label: '估算毛利',
      value: marginValue,
      unit: '万元',
      status: marginReady ? null : 'muted',
      hint: marginReady ? null : '估算未就绪'
    },
    { key: 'gap', label: '合同缺口', value: contractGapKnown(me) ? Number(me.remaining_weight).toFixed(0) : '—', unit: '吨' },
    { key: 'energy', label: '日吨能耗', value: fmt(lm.energy_per_ton, 1), unit: 'kWh/吨' }
  ]
})

const rawRankedRows = computed(() => {
  const rows = snapshot.productionLane.value || []
  return [...rows]
    .sort((a, b) => Number(b.total_output || 0) - Number(a.total_output || 0))
    .map((r, i) => {
      const compare = r.delta_vs_yesterday == null ? null : Number(r.delta_vs_yesterday)
      const compareTone = compare == null ? null : (compare > 0 ? 'positive' : compare < 0 ? 'negative' : null)
      const compareArrow = compare == null ? '' : (compare > 0 ? '↑' : compare < 0 ? '↓' : '')
      const totalOutput = r.total_output == null ? null : Number(r.total_output)
      const targetValue = r.target_value == null ? null : Number(r.target_value)
      const progress = targetValue && targetValue > 0
        ? Math.min(Math.max(((totalOutput || 0) / targetValue) * 100, 8), 100)
        : Math.min(Math.max(totalOutput || 0, 8), 100)
      return {
        key: r.workshop_id ?? r.workshop_name ?? i,
        rank: i + 1,
        rankTone: i === 0 ? 'hot' : i === 1 ? 'warm' : i === 2 ? 'live' : '',
        name: r.workshop_name || '—',
        totalOutput,
        compareValue: compare,
        compareTone,
        compareArrow,
        targetValue,
        progress
      }
    })
})

const rawLeadingRow = computed(() => rawRankedRows.value[0] || null)

const rawLeadingWorkshopText = computed(() => {
  const row = rawLeadingRow.value
  return row?.totalOutput != null ? `${row.name} ${fmt(row.totalOutput, 2)} 吨` : '暂无车间数据'
})

const rawProductionBrief = computed(() => {
  const lm = snapshot.leaderMetrics.value
  const me = snapshot.managementEstimate.value
  return [
    { key: 'workshops', label: '参与车间', value: `${rawRankedRows.value.length} 个` },
    { key: 'leader', label: '当前最高', value: rawLeadingWorkshopText.value },
    { key: 'gap', label: '合同缺口', value: contractGapKnown(me) ? `${Number(me.remaining_weight).toFixed(0)} 吨` : '—' },
    { key: 'energy', label: '日吨能耗', value: lm.energy_per_ton == null ? '—' : `${fmt(lm.energy_per_ton, 1)} kWh/吨` }
  ]
})

const productionSourceOverview = computed(() => {
  const dailyOverview = snapshot.data.value.daily_overview || {}
  const plantOutput = dailyOverview.plant_output || {}
  const factoryCommandOverview = snapshot.factoryCommandOverview.value || {}
  const lm = snapshot.leaderMetrics.value || {}
  const dailyProcessOutput = sumDailyWorkshopOutput(dailyOverview.workshop_output)

  return {
    ...factoryCommandOverview,
    source: plantOutput.daily_output == null ? factoryCommandOverview.source : 'mes_projection',
    today_output_tons: plantOutput.daily_output ?? factoryCommandOverview.today_output_tons,
    process_output_tons: dailyProcessOutput
      ?? factoryCommandOverview.process_output_tons
      ?? factoryCommandOverview.total_output_tons
      ?? snapshot.data.value.process_total_output,
    // 在制是存量，和经营总览同一天的在制料一致；工厂指挥给的是当天投入减产出，不是存量
    wip_tons: sumWipWeight(buildDailyWipRows(dailyOverview.wip_distribution || [])),
    yield_rate: lm.yield_rate ?? factoryCommandOverview.yield_rate,
  }
})

const stitchSurface = computed(() => buildProductionStitchSurface({
  snapshotData: snapshot.data.value,
  targetDate: snapshot.targetDate.value,
  kpiItems: rawKpiItems.value,
  rankedRows: rawRankedRows.value,
  productionBrief: rawProductionBrief.value,
  leadingWorkshopText: rawLeadingWorkshopText.value,
  sourceOverview: productionSourceOverview.value,
  runtimeState: {
    snapshotLoading: snapshot.loading.value,
    snapshotError: snapshot.lastError.value,
  },
}))

const kpiItems = computed(() => stitchSurface.value.kpiStrip)
const rankedRows = computed(() => stitchSurface.value.workshopRanking)
const productionBrief = computed(() => stitchSurface.value.productionBrief)
const chartRows = computed(() => {
  const rows = rankedRows.value
  const scale = Math.max(...rows.flatMap((row) => [Number(row.totalOutput) || 0, Number(row.targetValue) || 0]), 0)
  return rows.map((row) => ({
    ...row,
    outputRatio: scale > 0 ? (Number(row.totalOutput) || 0) / scale : 0,
    markerRatio: scale > 0 && row.targetValue != null ? Number(row.targetValue) / scale : null,
  }))
})
const hasMonthlyMarker = computed(() => chartRows.value.some((row) => row.markerRatio != null))
const bottomStatusItems = computed(() => stitchSurface.value.bottomStatus)
</script>

<style scoped>
.xt-production {
  display: flex;
  flex-direction: column;
  gap: var(--xt-space-6);
}

.xt-production__hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-3);
}

.xt-production__hero h1 {
  margin: 0;
  color: var(--xt-text);
  font-size: clamp(var(--xt-text-2xl), 3vw, 40px);
  font-weight: 600;
  letter-spacing: -0.02em;
}

.xt-production :deep(.xt-kpi-bar__card),
.xt-production :deep(.xt-source-strip),
.xt-production :deep(.xt-source-strip__source),
.xt-production :deep(.xt-source-strip__items li) {
  border: 0;
  background: transparent;
  box-shadow: none;
}

.xt-production :deep(.xt-kpi-bar__card),
.xt-production :deep(.xt-source-strip),
.xt-production :deep(.xt-source-strip__source),
.xt-production :deep(.xt-source-strip__items li) {
  padding-inline: 0;
}

.xt-production :deep(.xt-kpi-bar__card) {
  min-height: 0;
}

.xt-production :deep(.xt-kpi-bar__card::before),
.xt-production :deep(.xt-kpi-bar__card::after),
.xt-production :deep(.xt-kpi-bar__hint--placeholder),
.xt-production :deep(.xt-source-strip__pulse) {
  display: none;
}

.xt-production__error {
  color: var(--xt-danger);
  font-size: var(--xt-text-sm);
  font-weight: 600;
}

.xt-production__grid {
  display: grid;
  grid-template-columns: minmax(0, 2.4fr) minmax(240px, 1fr);
  gap: var(--xt-space-6);
  align-items: start;
}

.xt-production__panel-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--xt-space-3);
  margin-bottom: var(--xt-space-3);
}

.xt-production__panel-head h2,
.xt-production__aside h2 {
  margin: 0;
  color: var(--xt-text);
  font-size: var(--xt-text-lg);
  font-weight: 600;
}

.xt-production__legend {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-xs);
}

.xt-production__legend i {
  width: 2px;
  height: 14px;
  background: var(--xt-text);
}

.xt-production__empty {
  display: grid;
  min-height: 240px;
  margin: 0;
  place-items: center;
  color: var(--xt-text-muted);
  font-size: var(--xt-text-sm);
}

.xt-production__table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--xt-text-sm);
}

.xt-production__table th,
.xt-production__table td {
  padding: 14px var(--xt-space-2);
  border-bottom: 1px solid var(--xt-border);
  color: var(--xt-text);
  text-align: left;
  white-space: nowrap;
}

.xt-production__table th {
  padding-block: var(--xt-space-2);
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-xs);
  font-weight: 500;
}

.xt-production__table .is-chart {
  width: 42%;
  min-width: 140px;
}

.xt-production__table .is-num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.xt-production__table .is-strong {
  font-weight: 600;
}

.xt-production__table small {
  margin-left: 2px;
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-xs);
  font-weight: 400;
}

.xt-production__table .is-muted {
  color: var(--xt-text-secondary);
}

.xt-production__table .tone-positive {
  color: var(--xt-success);
}

.xt-production__table .tone-negative {
  color: var(--xt-warning);
}

.xt-production__sr {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip-path: inset(50%);
}

.xt-production__workshop {
  color: var(--xt-text);
  font-weight: 500;
}

.xt-production__bar {
  position: relative;
  height: 12px;
  border-radius: 2px;
  background: var(--xt-bg-panel-soft);
}

.xt-production__bar span {
  display: block;
  height: 100%;
  border-radius: 2px;
  background: var(--xt-primary);
  transform-origin: left;
  animation: xt-production-bar-grow 800ms cubic-bezier(0.16, 1, 0.3, 1) backwards;
}

.xt-production__bar i {
  position: absolute;
  top: -3px;
  bottom: -3px;
  width: 2px;
  margin-left: -1px;
  background: var(--xt-text);
}

.xt-production__brief-list {
  margin: var(--xt-space-3) 0 0;
}

.xt-production__brief-list > div {
  padding: var(--xt-space-3) 0;
  border-bottom: 1px solid var(--xt-border);
}

.xt-production__brief-list dt {
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-xs);
}

.xt-production__brief-list dd {
  margin: 4px 0 0;
  color: var(--xt-text);
  font-size: var(--xt-text-md);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.xt-production__status-bar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--xt-space-3) var(--xt-space-6);
  padding-top: var(--xt-space-3);
  border-top: 1px solid var(--xt-border);
}

.xt-production__status-item {
  display: inline-flex;
  align-items: center;
  gap: var(--xt-space-2);
  min-width: 0;
  font-size: var(--xt-text-sm);
}

.xt-production__status-item > span {
  width: 8px;
  height: 8px;
  flex: 0 0 auto;
  border-radius: var(--xt-radius-pill);
  background: var(--xt-primary);
}

.xt-production__status-item small {
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-xs);
  white-space: nowrap;
}

.xt-production__status-item strong {
  color: var(--xt-text);
  font-weight: 600;
  white-space: nowrap;
}

.xt-production__status-item.tone-success > span {
  background: var(--xt-success);
}

.xt-production__status-item.tone-warning > span {
  background: var(--xt-warning);
}

.xt-production__status-item.tone-danger > span {
  background: var(--xt-danger);
}

@keyframes xt-production-bar-grow {
  from { transform: scaleX(0); }
}

@media (max-width: 1080px) {
  .xt-production__grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .xt-production__hero {
    flex-direction: column;
    align-items: stretch;
  }

  .xt-production__table .is-chart,
  .xt-production__table th:nth-child(4),
  .xt-production__table td:nth-child(4),
  .xt-production__table th:nth-child(5),
  .xt-production__table td:nth-child(5) {
    display: none;
  }
}

@media (prefers-reduced-motion: reduce) {
  .xt-production__bar span {
    animation: none;
  }
}
</style>
