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
import { formatNumber } from '../../utils/display.js'

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
  days: { type: Number, default: 14 },
  costLabel: { type: String, default: '今日估算成本' }
})

const chartTheme = useHudChartTheme()

const muted = computed(() =>
  !props.estimate?.estimate_ready || props.estimate?.estimated_cost == null
)
const costWan = computed(() => {
  if (muted.value) return '—'
  return formatNumber(Number(props.estimate.estimated_cost) / 10000, 2)
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
  const lineColor = readToken('--xt-warning', 'rgb(240, 184, 74)')
  const muteColor = readToken('--xt-text-inverse', 'rgba(224, 236, 255, 0.58)')
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
        itemStyle: { color: lineColor, borderColor: 'rgba(255, 255, 255, 0.9)', borderWidth: 2 },
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
        <span class="xt-cost-panel__cost-label">{{ costLabel }}</span>
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
  position: relative;
  display: flex;
  flex-direction: column;
  gap: var(--xt-space-3);
  min-height: 100%;
  padding: var(--xt-space-3);
  border: 1px solid color-mix(in srgb, var(--xt-warning) 26%, var(--xt-border));
  border-radius: var(--xt-radius-xl);
  background:
    radial-gradient(circle at 100% 0%, color-mix(in srgb, var(--xt-warning) 16%, transparent), transparent 38%),
    color-mix(in srgb, var(--xt-bg-ink-panel) 86%, var(--xt-bg-panel));
  box-shadow:
    inset 0 1px 0 color-mix(in srgb, var(--xt-text-inverse) 8%, transparent),
    0 18px 40px color-mix(in srgb, var(--xt-bg-ink) 48%, transparent);
  overflow: hidden;
}

.xt-cost-panel::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--xt-warning), transparent);
  opacity: 0.85;
}

.xt-cost-panel__head {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.xt-cost-panel__cost.is-muted {
  opacity: 0.58;
}

.xt-cost-panel__cost-label {
  color: color-mix(in srgb, var(--xt-text-inverse) 54%, transparent);
  font-size: var(--xt-text-xs);
  font-weight: 850;
}

.xt-cost-panel__cost-row {
  display: flex;
  align-items: baseline;
  gap: var(--xt-space-2);
  margin-top: 2px;
}

.xt-cost-panel__cost-value {
  color: var(--xt-text-inverse);
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-2xl);
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
  text-shadow: 0 0 18px color-mix(in srgb, var(--xt-warning) 28%, transparent);
}

.xt-cost-panel__cost-unit {
  color: color-mix(in srgb, var(--xt-text-inverse) 58%, transparent);
  font-size: var(--xt-text-sm);
  font-weight: 800;
}

.xt-cost-panel__cost-pill {
  margin-left: auto;
  padding: 3px var(--xt-space-2);
  border: 1px solid color-mix(in srgb, var(--xt-warning) 42%, var(--xt-border));
  border-radius: var(--xt-radius-pill);
  background: color-mix(in srgb, var(--xt-warning-light) 10%, transparent);
  color: color-mix(in srgb, var(--xt-warning) 72%, var(--xt-text-inverse));
  font-size: var(--xt-text-xs);
  font-weight: 850;
  font-variant-numeric: tabular-nums;
}

.xt-cost-panel__cost-pill.is-muted {
  border-color: color-mix(in srgb, var(--xt-primary) 16%, var(--xt-border));
  background: color-mix(in srgb, var(--xt-bg-panel-soft) 8%, transparent);
  color: color-mix(in srgb, var(--xt-text-inverse) 46%, transparent);
}

.xt-cost-panel__trend {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.xt-cost-panel__trend-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--xt-space-2);
}

.xt-cost-panel__trend-title {
  color: color-mix(in srgb, var(--xt-text-inverse) 54%, transparent);
  font-size: var(--xt-text-xs);
  font-weight: 850;
}

.xt-cost-panel__trend-meta {
  color: color-mix(in srgb, var(--xt-text-inverse) 62%, transparent);
  font-size: var(--xt-text-xs);
  font-variant-numeric: tabular-nums;
}

.xt-cost-panel__trend-meta b {
  color: var(--xt-text-inverse);
  font-family: var(--xt-font-number);
  font-weight: 900;
}

.xt-cost-panel__chart {
  width: 100%;
  height: 138px;
}

.xt-cost-panel__empty {
  display: grid;
  place-items: center;
  height: 138px;
  color: color-mix(in srgb, var(--xt-text-inverse) 48%, transparent);
  font-size: var(--xt-text-sm);
}
</style>
