<template>
  <section class="xt-today" data-testid="manage-today">
    <header class="xt-today__header">
      <h1>今日</h1>
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

import DateSwitcher from '../../../components/manage/DateSwitcher.vue'
import KpiBar from '../../../components/manage/KpiBar.vue'
import WorkshopBarChart from '../../../components/manage/WorkshopBarChart.vue'
import KeyEventList from '../../../components/manage/KeyEventList.vue'
import { hasAnyEvent } from '../../../components/manage/_keyEvents.js'
import CostLine from '../../../components/manage/CostLine.vue'
import { useDashboardSnapshot } from '../../../composables/useDashboardSnapshot.js'

const snapshot = useDashboardSnapshot()
snapshot.load()

const fmt = (v, digits = 2) =>
  (v == null || Number.isNaN(Number(v))) ? '—' : Number(v).toFixed(digits)

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
