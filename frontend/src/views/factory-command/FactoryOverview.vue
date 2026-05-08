<template>
  <FactoryCommandShell title="工厂总览" active="overview" :freshness="freshness">
    <section class="fc-hero">
      <div class="fc-hero__item">
        <span class="fc-hero__label">日产总量</span>
        <strong class="fc-hero__number">{{ heroOutput }}</strong>
        <span v-if="heroDelta.output !== null" class="fc-hero__delta" :class="heroDelta.output >= 0 ? 'is-up' : 'is-down'">
          {{ heroDelta.output >= 0 ? '↑' : '↓' }} {{ Math.abs(heroDelta.output).toFixed(1) }}%
        </span>
      </div>
      <div class="fc-hero__item">
        <span class="fc-hero__label">日投料总量</span>
        <strong class="fc-hero__number">{{ heroInput }}</strong>
        <span v-if="heroDelta.input !== null" class="fc-hero__delta" :class="heroDelta.input >= 0 ? 'is-up' : 'is-down'">
          {{ heroDelta.input >= 0 ? '↑' : '↓' }} {{ Math.abs(heroDelta.input).toFixed(1) }}%
        </span>
      </div>
      <div class="fc-hero__item">
        <span class="fc-hero__label">成品率</span>
        <strong class="fc-hero__number">{{ heroYield }}<em>%</em></strong>
        <span v-if="heroDelta.yield !== null" class="fc-hero__delta" :class="heroDelta.yield >= 0 ? 'is-up' : 'is-down'">
          {{ heroDelta.yield >= 0 ? '↑' : '↓' }} {{ Math.abs(heroDelta.yield).toFixed(1) }}pp
        </span>
      </div>
    </section>

    <div class="fc-cutoff">
      <span>{{ cutoffLabel }}</span>
    </div>

    <section class="fc-grid fc-grid--metrics">
      <article class="fc-metric is-primary">
        <span>在制吨数</span>
        <strong>{{ overview?.wip_tons ?? '--' }}</strong>
        <em>数据源 {{ sourceLabel(freshness.source) }}</em>
      </article>
      <article class="fc-metric">
        <span>库存</span>
        <strong>{{ overview?.stock_tons ?? '--' }}</strong>
        <em>成品吨数</em>
      </article>
      <article class="fc-metric" :class="{ 'is-danger': overview?.abnormal_count > 0 }">
        <span>风险项</span>
        <strong>{{ overview?.abnormal_count ?? 0 }}</strong>
        <em>最后同步 {{ formatSyncTime(freshness.last_synced_at) }}</em>
      </article>
      <article class="fc-metric">
        <span>同步滞后</span>
        <strong>{{ formatLagLabel(freshness.lag_seconds) }}</strong>
        <em>{{ freshnessLabel(freshness.status) }}</em>
      </article>
    </section>

    <section class="fc-pending" :class="{ 'is-empty': !pendingAssignmentSummary.entryCount }">
      <div class="fc-pending__head">
        <div>
          <strong>填报实时归属</strong>
          <span>{{ liveBusinessDate || '--' }} · {{ sourceLabel(freshness.source) }}</span>
        </div>
        <RouterLink :to="pendingAssignmentRoute">处理待归属</RouterLink>
      </div>

      <div class="fc-pending__metrics">
        <article>
          <span>填报待归属</span>
          <strong>{{ pendingAssignmentSummary.entryCount }}</strong>
          <em>卷</em>
        </article>
        <article>
          <span>暂存产量</span>
          <strong>{{ formatWeight(pendingAssignmentSummary.output) }}</strong>
          <em>吨</em>
        </article>
        <article>
          <span>外部 MES 线索</span>
          <strong>{{ pendingAssignmentSummary.mesMatchedCount }}</strong>
          <em>卷</em>
        </article>
        <article>
          <span>可绑定入账</span>
          <strong>{{ pendingAssignmentSummary.bindableCount }}</strong>
          <em>卷</em>
        </article>
      </div>

      <div v-if="pendingAssignmentRows.length" class="fc-pending__rows">
        <article v-for="row in pendingAssignmentRows" :key="row.entryId">
          <div>
            <strong>{{ row.trackingCard }}</strong>
            <span>{{ row.workshop }} · {{ row.shift }}</span>
          </div>
          <span>{{ row.outputWeightLabel }}</span>
          <span>{{ row.assignmentHint }}</span>
          <b :class="`is-${row.bindingTone}`">{{ row.bindingLabel }}</b>
        </article>
      </div>
      <div v-else class="fc-pending__empty">暂无待归属填报</div>
    </section>

    <section class="fc-panel">
      <div class="fc-panel__head">
        <strong>车间扫描</strong>
        <button type="button" @click="askAi({ type: 'factory', key: 'all' })">问 AI</button>
      </div>
      <div class="fc-table">
        <div class="fc-table__row is-head">
          <span>车间</span><span>卷数</span><span>吨数</span><span>废料率</span><span>停滞</span>
        </div>
        <div v-for="row in store.workshops" :key="row.workshop_name" class="fc-table__row">
          <span>{{ row.workshop_name }}</span>
          <span>{{ row.active_coil_count }}</span>
          <span>{{ row.active_tons }}</span>
          <span :class="{ 'is-scrap-high': workshopScrapRate(row.workshop_name) > 3 }">{{ workshopScrapLabel(row.workshop_name) }}</span>
          <span>{{ row.stalled_count }}</span>
        </div>
      </div>
    </section>

    <section class="fc-panel">
      <div class="fc-panel__head">
        <strong>重点机列</strong>
        <button type="button" @click="askAi({ type: 'machine', key: 'priority' })">问 AI</button>
      </div>
      <div class="fc-table">
        <div class="fc-table__row is-head fc-table__row--lines">
          <span>机列</span><span>车间</span><span>在制吨数</span><span>停滞卷数</span>
        </div>
        <div v-for="line in priorityLines" :key="line.line_code" class="fc-table__row fc-table__row--lines">
          <span>{{ formatLineDisplay(line).title }}</span>
          <span>{{ formatLineDisplay(line).meta }}</span>
          <span>{{ line.active_tons ?? line.activeTons }}</span>
          <span>{{ line.stalled_count ?? line.stalledCount }}</span>
        </div>
      </div>
    </section>

    <section class="fc-charts">
      <WorkshopOutputRanking :items="overview?.workshop_summary || []" />
      <WorkshopScrapRate :items="overview?.workshop_summary || []" />
    </section>

    <section class="fc-charts">
      <ReconciliationWaterfall :items="workshopReconciliationItems" />
      <PendingAssignmentHeatmap :rows="pendingAssignment.items" />
    </section>
  </FactoryCommandShell>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { fetchLiveActiveDate, fetchPendingAssignmentEntries } from '../../api/realtime'
import { useFactoryCommandStore } from '../../stores/factory-command'
import { openAiAssistant } from '../../utils/assistantLauncher'
import { formatLagLabel, formatLineDisplay, formatSyncTime, freshnessLabel, sourceLabel } from '../../utils/factoryCommandFormatters'
import { formatWeight } from '../../utils/liveDashboardFormatters'
import PendingAssignmentHeatmap from '../../components/charts/PendingAssignmentHeatmap.vue'
import ReconciliationWaterfall from '../../components/charts/ReconciliationWaterfall.vue'
import WorkshopOutputRanking from '../../components/charts/WorkshopOutputRanking.vue'
import WorkshopScrapRate from '../../components/charts/WorkshopScrapRate.vue'
import FactoryCommandShell from './FactoryCommandShell.vue'

const store = useFactoryCommandStore()
const route = useRoute()
const liveBusinessDate = ref('')
const pendingAssignment = ref({ summary: {}, items: [] })
const overview = computed(() => store.overview || {})
const freshness = computed(() => overview.value.freshness || {})

const heroOutput = computed(() => {
  const v = overview.value.today_output_tons
  return v != null ? Number(v).toFixed(1) : '--'
})
const heroInput = computed(() => {
  const v = overview.value.total_input_tons
  return v != null ? Number(v).toFixed(1) : '--'
})
const heroYield = computed(() => {
  const v = overview.value.yield_rate
  return v != null ? Number(v).toFixed(1) : '--'
})
const heroDelta = computed(() => {
  const prev = overview.value.previous_day
  if (!prev) return { output: null, input: null, yield: null }
  const pct = (cur, old) => old > 0 ? ((cur - old) / old) * 100 : null
  return {
    output: pct(overview.value.today_output_tons, prev.total_output_tons),
    input: pct(overview.value.total_input_tons, prev.total_input_tons),
    yield: prev.yield_rate != null && overview.value.yield_rate != null
      ? overview.value.yield_rate - prev.yield_rate
      : null
  }
})
const cutoffLabel = computed(() => {
  const ts = freshness.value.last_synced_at
  if (!ts) return '同步中...'
  try {
    const d = new Date(ts)
    const month = d.getMonth() + 1
    const day = d.getDate()
    const h = d.getHours()
    const shift = h < 8 ? '夜班' : h < 20 ? '白班' : '夜班'
    return `数据截止 ${month}月${day}日 ${shift}`
  } catch { return '同步异常' }
})
const priorityLines = computed(() => [...store.machineLines].sort((a, b) => {
  const stalledDiff = (b.stalled_count ?? b.stalledCount ?? 0) - (a.stalled_count ?? a.stalledCount ?? 0)
  if (stalledDiff !== 0) return stalledDiff
  return (b.active_tons ?? b.activeTons ?? 0) - (a.active_tons ?? a.activeTons ?? 0)
}).slice(0, 5))
const workshopReconciliationItems = computed(() => (overview.value.workshop_summary || []).map((ws) => ({
  workshop_name: ws.workshop_name,
  mes_output_tons: ws.total_input_tons || 0,
  fill_output_tons: ws.total_output_tons || 0
})))
const pendingAssignmentRoute = computed(() => ({
  path: '/manage/entry-center',
  query: route.query.desktop === '1' ? { tab: 'pendingAssignment', desktop: '1' } : { tab: 'pendingAssignment' }
}))
const pendingAssignmentSummary = computed(() => {
  const summary = pendingAssignment.value.summary || {}
  const items = pendingAssignment.value.items || []
  return {
    entryCount: Number(summary.entry_count ?? pendingAssignment.value.total ?? 0) || 0,
    output: Number(summary.output || 0) || 0,
    mesMatchedCount: items.filter((item) => Number(item.mes_match_count || 0) > 0).length,
    bindableCount: items.filter((item) => canBindPendingAssignment(item)).length
  }
})
const pendingAssignmentRows = computed(() => (pendingAssignment.value.items || []).slice(0, 5).map((item) => ({
  entryId: item.entry_id,
  trackingCard: item.tracking_card_no || '-',
  workshop: item.workshop_name || '-',
  shift: item.shift_name || '-',
  outputWeightLabel: `${formatWeight(item.output_weight)} 吨`,
  assignmentHint: pendingAssignmentHint(item),
  bindingLabel: canBindPendingAssignment(item) ? '可绑定' : '待确认',
  bindingTone: canBindPendingAssignment(item) ? 'ready' : 'pending'
})))

function canBindPendingAssignment(item = {}) {
  if (item.entry_status !== 'draft') return false
  const missingFields = item.missing_fields || []
  if (missingFields.includes('shift_id')) return false
  if (item.mes_machine_id) return true
  return Number(item.machine_candidate_count || 0) === 1
}

function pendingAssignmentHint(item = {}) {
  const mesMatchCount = Number(item.mes_match_count || 0)
  if (mesMatchCount > 0 && item.mes_machine_name) return `外部 MES：${item.mes_machine_name}`
  if (mesMatchCount > 0) return '外部 MES 已匹配'
  const names = item.machine_candidate_names || []
  if (names.length) return `候选 ${names.slice(0, 2).join(' / ')}`
  const candidateCount = Number(item.machine_candidate_count || 0)
  if (candidateCount > 0) return `车间候选 ${candidateCount} 台`
  return '待补机列'
}

function askAi(scope) {
  openAiAssistant({
    question: '当前工厂状态和优先风险是什么？',
    scope: { type: scope.type, key: scope.key },
    freshness: freshness.value
  })
}

function workshopScrapRate(workshopName) {
  const ws = (overview.value.workshop_summary || []).find((s) => s.workshop_name === workshopName)
  if (!ws || ws.yield_rate == null) return null
  return 100 - ws.yield_rate
}

function workshopScrapLabel(workshopName) {
  const rate = workshopScrapRate(workshopName)
  return rate != null ? `${rate.toFixed(1)}%` : '--'
}

async function loadPendingAssignment() {
  try {
    const activeDate = await fetchLiveActiveDate()
    liveBusinessDate.value = activeDate?.business_date || ''
    if (!liveBusinessDate.value) return
    pendingAssignment.value = await fetchPendingAssignmentEntries({ business_date: liveBusinessDate.value })
  } catch {
    pendingAssignment.value = { summary: {}, items: [] }
  }
}

onMounted(async () => {
  await Promise.all([store.loadOverview(), store.loadWorkshops(), store.loadMachineLines(), loadPendingAssignment()])
})
</script>

<style scoped>
.fc-hero {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  background: oklch(99% 0.003 248);
  border-bottom: 1px solid rgba(43, 93, 178, 0.10);
  padding: 28px 0 24px;
  margin-bottom: 0;
}

.fc-hero__item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  position: relative;
}

.fc-hero__item + .fc-hero__item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 8px;
  bottom: 8px;
  width: 1px;
  background: rgba(43, 93, 178, 0.12);
}

.fc-hero__label {
  font-size: 12px;
  font-weight: 800;
  color: var(--xt-text-secondary);
  letter-spacing: 0.02em;
}

.fc-hero__number {
  font-family: var(--xt-font-number);
  font-size: 48px;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  color: var(--xt-text);
  line-height: 1.1;
}

.fc-hero__number em {
  font-size: 24px;
  font-style: normal;
  font-weight: 800;
  color: var(--xt-text-secondary);
  margin-left: 2px;
}

.fc-hero__delta {
  font-size: 14px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.fc-hero__delta.is-up {
  color: var(--xt-success);
}

.fc-hero__delta.is-down {
  color: var(--xt-danger);
}

.fc-cutoff {
  display: flex;
  justify-content: center;
  padding: 8px 0 12px;
}

.fc-cutoff span {
  font-size: 12px;
  font-weight: 700;
  color: var(--xt-text-muted);
}

.fc-grid {
  display: grid;
  gap: 12px;
}

.fc-grid--metrics {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-bottom: 12px;
}

.fc-metric,
.fc-panel {
  border: 1px solid rgba(43, 93, 178, 0.13);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 14px 34px rgba(25, 62, 118, 0.07);
}

.fc-metric {
  display: grid;
  gap: 8px;
  min-height: 112px;
  padding: 15px;
}

.fc-metric span,
.fc-metric em {
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-style: normal;
  font-weight: 800;
}

.fc-metric strong {
  color: var(--xt-text);
  font-family: var(--xt-font-number);
  font-size: 30px;
  font-variant-numeric: tabular-nums;
  font-weight: 900;
}

.fc-metric.is-primary {
  background: oklch(54% 0.19 255);
  color: #fff;
}

.fc-metric.is-primary span,
.fc-metric.is-primary strong,
.fc-metric.is-primary em {
  color: rgba(255, 255, 255, 0.92);
}

.fc-metric.is-danger {
  border-color: rgba(194, 65, 52, 0.24);
}

.fc-panel {
  padding: 14px;
}

.fc-pending {
  display: grid;
  gap: 12px;
  margin-bottom: 12px;
  padding: 14px;
  border: 1px solid rgba(43, 93, 178, 0.13);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 14px 34px rgba(25, 62, 118, 0.07);
}

.fc-pending__head,
.fc-pending__rows article {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.fc-pending__head strong,
.fc-pending__rows strong {
  display: block;
  color: var(--xt-text);
  font-weight: 900;
}

.fc-pending__head span,
.fc-pending__rows span,
.fc-pending__metrics span,
.fc-pending__metrics em,
.fc-pending__empty {
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-style: normal;
  font-weight: 800;
}

.fc-pending__head a {
  min-height: 34px;
  display: inline-flex;
  align-items: center;
  padding: 0 10px;
  border-radius: 6px;
  background: var(--xt-primary);
  color: #fff;
  font-size: 13px;
  font-weight: 850;
  text-decoration: none;
}

.fc-pending__metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
}

.fc-pending__metrics article {
  min-width: 0;
  display: grid;
  gap: 5px;
  padding: 10px;
  border: 1px solid rgba(43, 93, 178, 0.11);
  border-radius: 7px;
  background: oklch(98% 0.008 248);
}

.fc-pending__metrics strong {
  color: var(--xt-text);
  font-family: var(--xt-font-number);
  font-size: 24px;
  font-weight: 900;
}

.fc-pending__rows {
  display: grid;
  border: 1px solid rgba(43, 93, 178, 0.11);
  border-radius: 8px;
  overflow: hidden;
}

.fc-pending__rows article {
  min-width: 0;
  padding: 10px 12px;
  background: #fff;
  border-bottom: 1px solid rgba(43, 93, 178, 0.1);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

.fc-pending__rows article:last-child {
  border-bottom: 0;
}

.fc-pending__rows b {
  min-width: 58px;
  display: inline-flex;
  justify-content: center;
  padding: 4px 8px;
  border-radius: 999px;
  background: oklch(96% 0.025 254);
  color: var(--xt-text-secondary);
  font-size: 12px;
}

.fc-pending__rows b.is-ready {
  background: oklch(95% 0.04 158);
  color: var(--xt-success);
}

.fc-pending__empty {
  padding: 8px 0;
}

.fc-panel + .fc-panel {
  margin-top: 12px;
}

.fc-charts {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-top: 12px;
}

.fc-charts + .fc-charts {
  margin-top: 12px;
}

.fc-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.fc-panel__head button {
  min-height: 36px;
  border: 0;
  border-radius: 6px;
  background: var(--xt-primary);
  color: #fff;
  font-weight: 850;
  cursor: pointer;
}

.fc-table {
  display: grid;
  border: 1px solid rgba(43, 93, 178, 0.13);
  border-radius: 8px;
  overflow: hidden;
}

.fc-table__row {
  display: grid;
  grid-template-columns: minmax(160px, 1.4fr) repeat(4, minmax(80px, 1fr));
  gap: 12px;
  padding: 10px 12px;
  background: #fff;
  border-bottom: 1px solid rgba(43, 93, 178, 0.1);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

.fc-table__row.is-head {
  background: oklch(96% 0.025 254);
  color: var(--xt-text-secondary);
  font-weight: 900;
}

.is-scrap-high {
  color: var(--xt-danger);
  font-weight: 900;
}

.fc-table__row--lines {
  grid-template-columns: minmax(160px, 1.2fr) minmax(120px, 1fr) repeat(2, minmax(90px, 1fr));
}

@media (max-width: 900px) {
  .fc-hero {
    padding: 20px 0 18px;
  }

  .fc-hero__number {
    font-size: 36px;
  }

  .fc-grid--metrics,
  .fc-pending__metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .fc-charts {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 520px) {
  .fc-hero {
    grid-template-columns: 1fr;
    gap: 20px;
    padding: 20px 0;
  }

  .fc-hero__item + .fc-hero__item::before {
    display: none;
  }

  .fc-hero__number {
    font-size: 40px;
  }

  .fc-grid--metrics,
  .fc-pending__metrics {
    grid-template-columns: 1fr;
  }

  .fc-pending__head,
  .fc-pending__rows article {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
