<script setup>
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  MarkLineComponent,
  MarkPointComponent
} from 'echarts/components'
import VChart from 'vue-echarts'
import { useHudChartTheme } from '../../composables/useHudChartTheme.js'
import { shapeEnergyTrend, energyTrendStats } from './_costPanel.js'

use([
  CanvasRenderer,
  LineChart,
  GridComponent,
  TooltipComponent,
  MarkLineComponent,
  MarkPointComponent
])

const props = defineProps({
  estimate: { type: Object, default: () => ({}) },
  series: { type: Array, default: () => [] },
  days: { type: Number, default: 14 }
})

const chartTheme = useHudChartTheme()

const muted = computed(() =>
  !props.estimate?.estimate_ready || props.estimate?.estimated_cost == null
)
const costWan = computed(() => {
  if (muted.value) return '—'
  return (Number(props.estimate.estimated_cost) / 10000).toFixed(2)
})
const tonCost = computed(() => {
  const c = Number(props.estimate?.estimated_cost || 0)
  const t = Number(props.estimate?.total_output_weight || props.estimate?.output_tons || 0)
  if (!Number.isFinite(c) || !Number.isFinite(t) || t <= 0 || c <= 0) return null
  return Math.round(c / t)
})

const shaped = computed(() => shapeEnergyTrend(props.series, props.days))
const stats = computed(() => energyTrendStats(shaped.value))
const hasTrend = computed(() => shaped.value.some((p) => Number.isFinite(p.energyPerTon)))

function readToken(name, fallback) {
  if (typeof window === 'undefined' || !window.getComputedStyle) return fallback
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return v || fallback
}

const option = computed(() => {
  const lineColor = readToken('--xt-warning', '#cc8a1f')
  const muteColor = readToken('--xt-text-muted', '#94a3b8')
  const data = shaped.value.map((p) => p.energyPerTon)
  const lastIdx = data.length - 1
  return {
    grid: { left: 38, right: 12, top: 18, bottom: 22 },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'line' },
      formatter: (params) => {
        const p = params[0]
        const row = shaped.value[p.dataIndex] || {}
        return `${row.date || ''}<br/>` +
          `<b>${row.energyPerTon ?? '—'}</b> kWh/吨<br/>` +
          `产量 ${row.tons || 0} t · 用电 ${row.energy || 0} kWh`
      }
    },
    xAxis: {
      type: 'category',
      data: shaped.value.map((p) => p.label),
      axisLabel: { fontSize: 10, color: muteColor },
      axisLine: { show: false },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      axisLabel: { fontSize: 10, color: muteColor, formatter: '{value}' },
      splitLine: { lineStyle: { type: 'dashed', opacity: 0.35 } }
    },
    series: [{
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 4,
      data,
      lineStyle: { width: 2, color: lineColor },
      itemStyle: { color: lineColor },
      areaStyle: { color: lineColor, opacity: 0.06 },
      markPoint: lastIdx >= 0 ? {
        symbol: 'circle',
        symbolSize: 10,
        itemStyle: { color: lineColor, borderColor: '#fff', borderWidth: 2 },
        data: [{ coord: [lastIdx, data[lastIdx]] }]
      } : undefined,
      markLine: stats.value.avg > 0 ? {
        symbol: 'none',
        silent: true,
        lineStyle: { type: 'dashed', color: muteColor, width: 1, opacity: 0.6 },
        label: {
          formatter: `均 ${stats.value.avg.toFixed(0)}`,
          position: 'insideEndTop',
          fontSize: 10,
          color: muteColor
        },
        data: [{ yAxis: stats.value.avg }]
      } : undefined
    }]
  }
})
</script>

<template>
  <section class="xt-cost-panel" data-testid="manage-cost-line">
    <header class="xt-cost-panel__head">
      <div class="xt-cost-panel__cost" :class="{ 'is-muted': muted }">
        <span class="xt-cost-panel__cost-label">今日估算成本</span>
        <div class="xt-cost-panel__cost-row">
          <span class="xt-cost-panel__cost-value">{{ costWan }}</span>
          <span class="xt-cost-panel__cost-unit" v-if="!muted">万</span>
          <span class="xt-cost-panel__cost-pill" v-if="tonCost != null">{{ tonCost }} 元/吨</span>
          <span class="xt-cost-panel__cost-pill is-muted" v-else>口径：估算</span>
        </div>
      </div>
    </header>

    <div class="xt-cost-panel__trend">
      <div class="xt-cost-panel__trend-head">
        <span class="xt-cost-panel__trend-title">近 {{ days }} 日吨能耗</span>
        <span class="xt-cost-panel__trend-meta" v-if="hasTrend">
          当日 <b>{{ stats.last }}</b> · 均 {{ stats.avg.toFixed(0) }} kWh/吨
        </span>
      </div>
      <VChart
        v-if="hasTrend"
        class="xt-cost-panel__chart"
        :option="option"
        :theme="chartTheme"
        autoresize
      />
      <div v-else class="xt-cost-panel__empty">暂无能耗数据</div>
    </div>
  </section>
</template>

<style scoped>
.xt-cost-panel {
  background: var(--xt-bg-panel);
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-md);
  padding: var(--xt-space-3);
  display: flex;
  flex-direction: column;
  gap: var(--xt-space-3);
}
.xt-cost-panel__head { display: flex; flex-direction: column; gap: 2px; }
.xt-cost-panel__cost.is-muted { opacity: 0.55; }
.xt-cost-panel__cost-label { font-size: var(--xt-text-xs); color: var(--xt-text-muted); font-weight: 700; }
.xt-cost-panel__cost-row {
  display: flex; align-items: baseline; gap: var(--xt-space-2);
  margin-top: 2px;
}
.xt-cost-panel__cost-value {
  font-size: var(--xt-text-2xl); font-weight: 850; color: var(--xt-text);
  font-variant-numeric: tabular-nums; letter-spacing: -0.01em;
}
.xt-cost-panel__cost-unit { font-size: var(--xt-text-sm); color: var(--xt-text-secondary); font-weight: 700; }
.xt-cost-panel__cost-pill {
  margin-left: auto; padding: 2px var(--xt-space-2);
  background: var(--xt-warning-light);
  color: var(--xt-warning);
  border: 1px solid var(--xt-warning-border);
  font-size: var(--xt-text-xs); font-weight: 800;
  border-radius: var(--xt-radius-pill);
  font-variant-numeric: tabular-nums;
}
.xt-cost-panel__cost-pill.is-muted {
  background: var(--xt-bg-panel-soft);
  color: var(--xt-text-muted);
  border-color: var(--xt-border);
}

.xt-cost-panel__trend { display: flex; flex-direction: column; gap: 4px; }
.xt-cost-panel__trend-head {
  display: flex; align-items: baseline; justify-content: space-between;
  gap: var(--xt-space-2);
}
.xt-cost-panel__trend-title { font-size: var(--xt-text-xs); color: var(--xt-text-muted); font-weight: 700; }
.xt-cost-panel__trend-meta {
  font-size: var(--xt-text-xs); color: var(--xt-text-secondary);
  font-variant-numeric: tabular-nums;
}
.xt-cost-panel__trend-meta b { color: var(--xt-text); font-weight: 850; }
.xt-cost-panel__chart { width: 100%; height: 138px; }
.xt-cost-panel__empty {
  height: 138px; display: grid; place-items: center;
  color: var(--xt-text-muted); font-size: var(--xt-text-sm);
}
</style>
