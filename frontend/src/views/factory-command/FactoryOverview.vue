<template>
  <FactoryCommandShell title="工厂总览" active="overview" :freshness="freshness">
    <section class="fc-hero">
      <div class="fc-hero__grid"></div>
      <div class="fc-hero__scan"></div>
      <div class="fc-hero__item" :style="{ '--stagger': 0 }">
        <span class="fc-hero__label">日产总量</span>
        <strong class="fc-hero__number">{{ heroOutput }}</strong>
        <span v-if="heroDelta.output !== null" class="fc-hero__delta" :class="heroDelta.output >= 0 ? 'is-up' : 'is-down'">
          {{ heroDelta.output >= 0 ? '↑' : '↓' }} {{ Math.abs(heroDelta.output).toFixed(1) }}%
        </span>
      </div>
      <div class="fc-hero__item" :style="{ '--stagger': 1 }">
        <span class="fc-hero__label">日投料总量</span>
        <strong class="fc-hero__number">{{ heroInput }}</strong>
        <span v-if="heroDelta.input !== null" class="fc-hero__delta" :class="heroDelta.input >= 0 ? 'is-up' : 'is-down'">
          {{ heroDelta.input >= 0 ? '↑' : '↓' }} {{ Math.abs(heroDelta.input).toFixed(1) }}%
        </span>
      </div>
      <div class="fc-hero__item" :style="{ '--stagger': 2 }">
        <span class="fc-hero__label">成品率</span>
        <strong class="fc-hero__number">{{ heroYield }}<em>%</em></strong>
        <span v-if="heroDelta.yield !== null" class="fc-hero__delta" :class="heroDelta.yield >= 0 ? 'is-up' : 'is-down'">
          {{ heroDelta.yield >= 0 ? '↑' : '↓' }} {{ Math.abs(heroDelta.yield).toFixed(1) }}pp
        </span>
      </div>
      <div class="fc-hero__cutoff">{{ cutoffLabel }}</div>
    </section>

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

    <section v-if="hasLiveReality" class="fc-live-reality" :class="`is-${liveRealityStatus.tone}`" aria-label="实时数据日期">
      <article>
        <span>实时数据日期</span>
        <strong>{{ liveRealityStatus.primaryLabel }}</strong>
        <em>{{ liveRealityStatus.currentDateLabel }}</em>
        <em>{{ liveRealityStatus.activeDateLabel }}</em>
      </article>
      <article>
        <span>填报端上传</span>
        <strong>{{ liveRealityStatus.fillLabel }}</strong>
        <em>{{ liveRealityStatus.matchLabel }}</em>
      </article>
      <article>
        <span>外部 MES 机列绑定</span>
        <strong>{{ liveRealityStatus.bindingLabel }}</strong>
        <em>{{ liveRealityStatus.mesLabel }} · {{ liveRealityStatus.routeLabel }}</em>
        <em>{{ liveRealityStatus.pendingLabel }}</em>
      </article>
    </section>

    <section v-if="missingOutputWeightSummary.entryCount" class="fc-pending fc-missing-output" :class="`is-${missingOutputWeightSummary.tone}`" aria-label="待补产出重量">
      <div class="fc-pending__head">
        <div>
          <strong>待补产出重量</strong>
          <span>{{ liveBusinessDate || '--' }} · {{ sourceLabel(freshness.source) }}</span>
        </div>
        <RouterLink :to="missingOutputRoute">补重量</RouterLink>
      </div>

      <div class="fc-pending__metrics">
        <article>
          <span>缺产出</span>
          <strong>{{ missingOutputWeightSummary.entryCount }}</strong>
          <em>卷</em>
        </article>
        <article>
          <span>影响投入</span>
          <strong>{{ formatWeight(missingOutputWeightSummary.input) }}</strong>
          <em>吨</em>
        </article>
        <article>
          <span>废料记录</span>
          <strong>{{ formatWeight(missingOutputWeightSummary.scrap) }}</strong>
          <em>吨</em>
        </article>
      </div>

      <div v-if="missingOutputWeightSummary.items.length" class="fc-pending__rows">
        <article v-for="item in missingOutputWeightSummary.items" :key="item.entryId || item.trackingCardNo">
          <div>
            <strong>{{ item.trackingCardNo }}</strong>
            <span>{{ item.workshopName }} · {{ item.machineName }} · {{ item.shiftName }}</span>
          </div>
          <b>缺产出</b>
        </article>
      </div>
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

import { fetchLiveActiveDate, fetchLiveAggregation, fetchPendingAssignmentEntries } from '../../api/realtime'
import { useFactoryCommandStore } from '../../stores/factory-command'
import { openAiAssistant } from '../../utils/assistantLauncher'
import { formatLagLabel, formatLineDisplay, formatSyncTime, freshnessLabel, sourceLabel } from '../../utils/factoryCommandFormatters'
import { formatWeight } from '../../utils/liveDashboardFormatters'
import { buildLiveRealityStatus, buildMissingOutputWeightSummary } from '../../utils/managementCommandCenter'
import PendingAssignmentHeatmap from '../../components/charts/PendingAssignmentHeatmap.vue'
import ReconciliationWaterfall from '../../components/charts/ReconciliationWaterfall.vue'
import WorkshopOutputRanking from '../../components/charts/WorkshopOutputRanking.vue'
import WorkshopScrapRate from '../../components/charts/WorkshopScrapRate.vue'
import FactoryCommandShell from './FactoryCommandShell.vue'

const store = useFactoryCommandStore()
const route = useRoute()
const liveBusinessDate = ref('')
const liveAggregation = ref(null)
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
  const pct = (cur, old) => (cur != null && old > 0) ? ((cur - old) / old) * 100 : null
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
const missingOutputRoute = computed(() => ({
  path: '/manage/entry-center',
  query: route.query.desktop === '1' ? { tab: 'missingOutput', desktop: '1' } : { tab: 'missingOutput' }
}))
const hasLiveReality = computed(() => Boolean(liveAggregation.value?.business_date || liveAggregation.value?.businessDate))
const liveRealityStatus = computed(() => buildLiveRealityStatus(liveAggregation.value || {}))
const missingOutputWeightSummary = computed(() => buildMissingOutputWeightSummary(liveAggregation.value || {}, 3))
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

async function loadLiveSurface() {
  liveAggregation.value = null
  pendingAssignment.value = { summary: {}, items: [] }
  try {
    const activeDate = await fetchLiveActiveDate()
    liveBusinessDate.value = activeDate?.business_date || ''
    if (!liveBusinessDate.value) return
  } catch {
    liveBusinessDate.value = ''
    return
  }

  const [aggregationResult, pendingResult] = await Promise.allSettled([
    fetchLiveAggregation({ business_date: liveBusinessDate.value }),
    fetchPendingAssignmentEntries({ business_date: liveBusinessDate.value })
  ])
  liveAggregation.value = aggregationResult.status === 'fulfilled' ? aggregationResult.value : null
  pendingAssignment.value = pendingResult.status === 'fulfilled' ? pendingResult.value : { summary: {}, items: [] }
}

onMounted(async () => {
  await Promise.all([store.loadOverview(), store.loadWorkshops(), store.loadMachineLines(), loadLiveSurface()])
})
</script>

<style scoped>
:deep(*) {
  --xt-bg-panel: oklch(18% 0.022 252);
  --xt-bg-panel-soft: oklch(16% 0.018 252);
  --xt-bg-panel-muted: oklch(22% 0.025 252);
  --xt-border-light: oklch(28% 0.03 252);
  --xt-text: oklch(92% 0.01 252);
  --xt-text-secondary: oklch(58% 0.02 252);
  --xt-primary-soft: oklch(24% 0.04 255);
  --xt-shadow-sm: 0 4px 16px rgba(0, 0, 0, 0.3);
  --xt-shadow-md: 0 8px 32px rgba(0, 0, 0, 0.4);
  --xt-danger-border: oklch(50% 0.16 28);
  --xt-danger: oklch(65% 0.18 28);
  --xt-success-light: oklch(25% 0.06 158);
  --xt-success: oklch(65% 0.14 158);
}

.fc-hero {
  position: relative;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  overflow: hidden;
  padding: 36px 0 16px;
  border-radius: 10px;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.05), rgba(255, 255, 255, 0.015)),
    var(--xt-bg-ink);
  box-shadow:
    0 24px 56px rgba(5, 10, 20, 0.28),
    inset 0 1px 0 rgba(255, 255, 255, 0.06);
}

.fc-hero__grid {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    linear-gradient(90deg, rgba(11, 91, 212, 0.07) 1px, transparent 1px),
    linear-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px);
  background-size: 32px 32px;
  mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.5), transparent 82%);
}

.fc-hero__scan {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 120px;
  pointer-events: none;
  background: linear-gradient(90deg, transparent, rgba(11, 99, 246, 0.14), transparent);
  animation: fc-scan 4.5s cubic-bezier(0.16, 1, 0.3, 1) infinite;
}

@keyframes fc-scan {
  0% { opacity: 0; transform: translateX(-100%); }
  15% { opacity: 1; }
  100% { opacity: 0; transform: translateX(calc(100vw + 120px)); }
}

.fc-hero__item {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  animation: fc-rise 0.5s cubic-bezier(0.16, 1, 0.3, 1) both;
  animation-delay: calc(var(--stagger, 0) * 80ms);
}

@keyframes fc-rise {
  from { opacity: 0; transform: translateY(12px); }
  to { opacity: 1; transform: translateY(0); }
}

.fc-hero__item + .fc-hero__item::before {
  content: '';
  position: absolute;
  left: 0;
  top: 10px;
  bottom: 10px;
  width: 1px;
  background: rgba(255, 255, 255, 0.08);
}

.fc-hero__label {
  font-size: 12px;
  font-weight: 850;
  color: rgba(255, 255, 255, 0.5);
  letter-spacing: 0.06em;
  text-transform: uppercase;
}

.fc-hero__number {
  font-family: var(--xt-font-number);
  font-size: 52px;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  color: #fff;
  line-height: 1.05;
  text-shadow: 0 2px 18px rgba(11, 99, 246, 0.25);
}

.fc-hero__number em {
  font-size: 24px;
  font-style: normal;
  font-weight: 800;
  color: rgba(255, 255, 255, 0.45);
  margin-left: 2px;
}

.fc-hero__delta {
  font-size: 13px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}

.fc-hero__delta.is-up {
  color: oklch(72% 0.16 158);
}

.fc-hero__delta.is-down {
  color: oklch(70% 0.16 28);
}

.fc-hero__cutoff {
  position: relative;
  z-index: 1;
  grid-column: 1 / -1;
  display: flex;
  justify-content: center;
  padding-top: 14px;
  font-size: 11px;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.32);
  letter-spacing: 0.04em;
}

.fc-grid {
  display: grid;
  gap: 10px;
}

.fc-grid--metrics {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-top: 4px;
  margin-bottom: 12px;
}

.fc-metric,
.fc-panel {
  border: 1px solid var(--xt-border-light);
  border-radius: 10px;
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-sm);
  transition: transform var(--xt-motion-fast) var(--xt-ease), box-shadow var(--xt-motion-fast) var(--xt-ease), border-color var(--xt-motion-fast) var(--xt-ease);
}

.fc-panel {
  background:
    linear-gradient(180deg, rgba(11, 91, 212, 0.012) 0%, transparent 40%),
    var(--xt-bg-panel);
}

@media (hover: hover) {
  .fc-metric:hover {
    transform: translateY(-2px);
    box-shadow: var(--xt-shadow-md);
  }
}

.fc-metric {
  position: relative;
  display: grid;
  gap: 8px;
  min-height: 112px;
  padding: 15px;
  overflow: hidden;
}

.fc-metric::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  border-radius: inherit;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06);
}

.fc-metric span,
.fc-metric em {
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-style: normal;
  font-weight: 850;
}

.fc-metric strong {
  color: var(--xt-text);
  font-family: var(--xt-font-number);
  font-size: 30px;
  font-variant-numeric: tabular-nums;
  font-weight: 900;
}

.fc-metric.is-primary {
  background:
    linear-gradient(135deg, oklch(50% 0.18 255), oklch(42% 0.16 260));
  border-color: transparent;
  box-shadow:
    0 14px 34px rgba(11, 91, 212, 0.22),
    0 0 0 1px rgba(11, 91, 212, 0.15),
    inset 0 1px 0 rgba(255, 255, 255, 0.12);
  color: #fff;
  animation: fc-glow-pulse 3s ease-in-out infinite;
}

@keyframes fc-glow-pulse {
  0%, 100% { box-shadow: 0 14px 34px rgba(11, 91, 212, 0.22), 0 0 0 1px rgba(11, 91, 212, 0.15), inset 0 1px 0 rgba(255, 255, 255, 0.12); }
  50% { box-shadow: 0 14px 44px rgba(11, 91, 212, 0.32), 0 0 0 1px rgba(11, 91, 212, 0.25), inset 0 1px 0 rgba(255, 255, 255, 0.12); }
}

.fc-metric.is-primary::before {
  box-shadow: none;
}

.fc-metric.is-primary span,
.fc-metric.is-primary strong,
.fc-metric.is-primary em {
  color: rgba(255, 255, 255, 0.92);
}

.fc-metric.is-danger {
  border-color: var(--xt-danger-border);
  animation: fc-danger-pulse 2s ease-in-out infinite;
}

@keyframes fc-danger-pulse {
  0%, 100% { box-shadow: var(--xt-shadow-sm); }
  50% { box-shadow: 0 0 0 2px var(--xt-danger-border), 0 8px 24px rgba(194, 65, 52, 0.12); }
}

.fc-live-reality {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 12px;
}

.fc-live-reality article {
  display: grid;
  gap: 6px;
  min-width: 0;
  min-height: 118px;
  padding: 14px;
  border: 1px solid var(--xt-border-light);
  border-radius: 10px;
  background:
    linear-gradient(180deg, rgba(11, 91, 212, 0.04), rgba(255, 255, 255, 0.01)),
    var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-sm);
}

.fc-live-reality.is-warning article:first-child {
  border-color: rgba(183, 121, 31, 0.55);
}

.fc-live-reality span,
.fc-live-reality em {
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-style: normal;
  font-weight: 850;
}

.fc-live-reality strong {
  overflow: hidden;
  color: var(--xt-text);
  font-size: 20px;
  font-weight: 900;
  line-height: 1.18;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fc-panel {
  padding: 14px;
  position: relative;
  overflow: hidden;
}

.fc-panel::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  border-radius: inherit;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.fc-pending {
  display: grid;
  gap: 12px;
  margin-bottom: 12px;
  padding: 14px;
  border: 1px solid var(--xt-border-light);
  border-radius: 10px;
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-sm);
  position: relative;
  overflow: hidden;
}

.fc-pending::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  border-radius: inherit;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
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
  font-weight: 850;
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
  border: 1px solid var(--xt-border-light);
  border-radius: 8px;
  background: var(--xt-bg-panel-soft);
}

.fc-pending__metrics strong {
  color: var(--xt-text);
  font-family: var(--xt-font-number);
  font-size: 24px;
  font-weight: 900;
}

.fc-pending__rows {
  display: grid;
  border: 1px solid var(--xt-border-light);
  border-radius: 8px;
  overflow: hidden;
}

.fc-pending__rows article {
  min-width: 0;
  padding: 10px 12px;
  background: var(--xt-bg-panel);
  border-bottom: 1px solid var(--xt-border-light);
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
  background: var(--xt-bg-panel-muted);
  color: var(--xt-text-secondary);
  font-size: 12px;
}

.fc-pending__rows b.is-ready {
  background: var(--xt-success-light);
  color: var(--xt-success);
}

.fc-missing-output {
  border-color: rgba(194, 65, 52, 0.52);
  background:
    linear-gradient(180deg, rgba(194, 65, 52, 0.14), rgba(255, 255, 255, 0.015)),
    var(--xt-bg-panel);
}

.fc-missing-output .fc-pending__head a {
  background: var(--xt-danger);
  white-space: nowrap;
}

.fc-missing-output .fc-pending__metrics {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.fc-missing-output .fc-pending__metrics article,
.fc-missing-output .fc-pending__rows {
  border-color: rgba(194, 65, 52, 0.28);
  background: rgba(194, 65, 52, 0.06);
}

.fc-missing-output .fc-pending__rows div {
  min-width: 0;
}

.fc-missing-output .fc-pending__rows span,
.fc-missing-output .fc-pending__rows strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.fc-missing-output .fc-pending__rows b {
  background: rgba(194, 65, 52, 0.14);
  color: var(--xt-danger);
  font-weight: 900;
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
  position: relative;
}

.fc-charts :deep(.chart-card) {
  border: 1px solid oklch(28% 0.03 252);
  border-radius: 10px;
  background:
    linear-gradient(180deg, rgba(80, 160, 255, 0.02) 0%, transparent 50%),
    oklch(18% 0.022 252);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
  transition: transform var(--xt-motion-fast) var(--xt-ease), box-shadow var(--xt-motion-fast) var(--xt-ease);
}

@media (hover: hover) {
  .fc-charts :deep(.chart-card:hover) {
    transform: translateY(-2px);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  }
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
  border: 1px solid var(--xt-border-light);
  border-radius: 8px;
  overflow: hidden;
}

.fc-table__row {
  display: grid;
  grid-template-columns: minmax(160px, 1.4fr) repeat(4, minmax(80px, 1fr));
  gap: 12px;
  padding: 10px 12px;
  background: var(--xt-bg-panel);
  border-bottom: 1px solid var(--xt-border-light);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
  transition: background-color var(--xt-motion-fast) var(--xt-ease);
}

@media (hover: hover) {
  .fc-table__row:not(.is-head):hover {
    background: var(--xt-primary-soft);
  }
}

.fc-table__row.is-head {
  background: var(--xt-bg-panel-soft);
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
    padding: 24px 0 14px;
  }

  .fc-hero__number {
    font-size: 38px;
  }

  .fc-grid--metrics,
  .fc-live-reality,
  .fc-missing-output .fc-pending__metrics,
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
    padding: 24px 0 14px;
  }

  .fc-hero__item + .fc-hero__item::before {
    display: none;
  }

  .fc-hero__number {
    font-size: 44px;
  }

  .fc-grid--metrics,
  .fc-live-reality,
  .fc-missing-output .fc-pending__metrics,
  .fc-pending__metrics {
    grid-template-columns: 1fr;
  }

  .fc-pending__head,
  .fc-pending__rows article {
    align-items: flex-start;
    flex-direction: column;
  }
}

@media (prefers-reduced-motion: reduce) {
  .fc-hero__scan { animation: none !important; }
  .fc-hero__item { animation: none !important; }
}
</style>
