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
        @pick="(d) => snapshot.targetDate.value = d"
      />
    </header>

    <KpiBar :items="kpiItems" />

    <div v-if="snapshot.lastError.value" class="xt-production__error">{{ snapshot.lastError.value }}</div>

    <div class="xt-production__ranking">
      <h2>车间产量排名</h2>
      <p v-if="rankedRows.length === 0" class="xt-production__empty">无车间数据</p>
      <table v-else class="xt-production__table" data-testid="manage-production-table">
        <thead>
          <tr>
            <th scope="col">车间</th>
            <th scope="col" class="is-num">今日产量</th>
            <th scope="col" class="is-num">比昨日</th>
            <th scope="col" class="is-num">月均参照</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rankedRows" :key="row.key">
            <td>{{ row.name }}</td>
            <td class="is-num">
              <span>{{ fmt(row.totalOutput, 2) }}</span>
              <small>吨</small>
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
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'

import DateSwitcher from '../../../components/manage/DateSwitcher.vue'
import KpiBar from '../../../components/manage/KpiBar.vue'
import { useDashboardSnapshot } from '../../../composables/useDashboardSnapshot.js'

const snapshot = useDashboardSnapshot()
snapshot.load()

const fmt = (v, digits = 2) =>
  (v == null || Number.isNaN(Number(v))) ? '—' : Number(v).toFixed(digits)

const kpiItems = computed(() => {
  const lm = snapshot.leaderMetrics.value
  const trend = snapshot.trend.value
  const me = snapshot.managementEstimate.value

  const delta = trend.output_delta_vs_yesterday
  const deltaTone = delta == null ? null : (Number(delta) > 0 ? 'positive' : Number(delta) < 0 ? 'negative' : null)
  const deltaArrow = delta == null ? '' : (Number(delta) > 0 ? '↑' : Number(delta) < 0 ? '↓' : '')
  const deltaText = delta == null ? '—' : `${deltaArrow}${fmt(Math.abs(Number(delta)), 2)}`

  const marginReady = me.estimate_ready !== false && me.estimated_margin != null
  const marginValue = marginReady ? (Number(me.estimated_margin) / 10000).toFixed(1) : '—'

  return [
    { key: 'output', label: '已产', value: fmt(lm.total_output_weight, 2), unit: '吨' },
    { key: 'delta', label: '比昨日', value: deltaText, unit: '吨', tone: deltaTone },
    {
      key: 'margin',
      label: '估算毛利',
      value: marginValue,
      unit: '万元',
      status: marginReady ? null : 'muted',
      hint: marginReady ? null : '估算未就绪'
    },
    { key: 'gap', label: '合同缺口', value: me.remaining_weight == null ? '—' : Number(me.remaining_weight).toFixed(0), unit: '吨' },
    { key: 'energy', label: '日吨能耗', value: fmt(lm.energy_per_ton, 1), unit: 'kWh/吨' }
  ]
})

const rankedRows = computed(() => {
  const rows = snapshot.productionLane.value || []
  return [...rows]
    .sort((a, b) => Number(b.total_output || 0) - Number(a.total_output || 0))
    .map((r, i) => {
      const compare = r.delta_vs_yesterday == null ? null : Number(r.delta_vs_yesterday)
      const compareTone = compare == null ? null : (compare > 0 ? 'positive' : compare < 0 ? 'negative' : null)
      const compareArrow = compare == null ? '' : (compare > 0 ? '↑' : compare < 0 ? '↓' : '')
      return {
        key: r.workshop_id ?? r.workshop_name ?? i,
        name: r.workshop_name || '—',
        totalOutput: Number(r.total_output || 0),
        compareValue: compare,
        compareTone,
        compareArrow,
        targetValue: r.target_value == null ? null : Number(r.target_value)
      }
    })
})
</script>

<style scoped>
.xt-production { display: flex; flex-direction: column; gap: var(--xt-space-4); }
.xt-production__header { display: flex; align-items: center; justify-content: space-between; gap: var(--xt-space-3); flex-wrap: wrap; }
.xt-production__header h1 { margin: 0; font-size: var(--xt-text-2xl); font-weight: 850; color: var(--xt-text); }
@media (max-width: 720px) {
  .xt-production__header { flex-direction: column; align-items: stretch; }
}
.xt-production__error {
  padding: var(--xt-space-2) var(--xt-space-3);
  background: var(--xt-bg-panel);
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-md);
  color: var(--xt-text-muted);
  font-size: var(--xt-text-sm);
}
.xt-production__ranking {
  background: var(--xt-bg-panel);
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-md);
  padding: var(--xt-space-3);
  display: flex; flex-direction: column; gap: var(--xt-space-2);
}
.xt-production__ranking h2 { margin: 0; font-size: var(--xt-text-md); font-weight: 800; color: var(--xt-text); }
.xt-production__empty { margin: 0; color: var(--xt-text-muted); font-size: var(--xt-text-sm); }
.xt-production__table { width: 100%; border-collapse: collapse; font-size: var(--xt-text-sm); }
.xt-production__table th,
.xt-production__table td {
  padding: var(--xt-space-2) var(--xt-space-3);
  border-bottom: 1px solid var(--xt-border);
  text-align: left;
  color: var(--xt-text);
}
.xt-production__table th { color: var(--xt-text-muted); font-weight: 700; font-size: var(--xt-text-xs); }
.xt-production__table .is-num { text-align: right; font-variant-numeric: tabular-nums; }
.xt-production__table small { color: var(--xt-text-secondary); margin-left: 2px; font-size: var(--xt-text-xs); }
.xt-production__table .is-muted { color: var(--xt-text-muted); }
.xt-production__table .tone-positive { color: var(--xt-color-success); }
.xt-production__table .tone-negative { color: var(--xt-color-warning); }
</style>
