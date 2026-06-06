<script setup>
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import {
  GridComponent,
  TooltipComponent,
  MarkLineComponent,
  AxisPointerComponent
} from 'echarts/components'
import VChart from 'vue-echarts'
import { useHudChartTheme } from '../../composables/useHudChartTheme.js'
import { shapeTrendSeries, trendStats } from './_outputTrend.js'

use([
  CanvasRenderer,
  LineChart,
  GridComponent,
  TooltipComponent,
  MarkLineComponent,
  AxisPointerComponent
])

const props = defineProps({
  series: { type: Array, default: () => [] },
  days: { type: Number, default: 14 }
})

const chartTheme = useHudChartTheme()

const shaped = computed(() => shapeTrendSeries(props.series, props.days))
const stats = computed(() => trendStats(shaped.value))
const hasData = computed(() => shaped.value.some((p) => p.output > 0))

function readToken(name, fallback) {
  if (typeof window === 'undefined' || !window.getComputedStyle) return fallback
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return v || fallback
}

const option = computed(() => {
  const lineColor = readToken('--xt-primary', 'rgb(94, 184, 255)')
  const avgColor = readToken('--xt-text-inverse', 'rgba(224, 236, 255, 0.58)')
  return {
    grid: { left: 48, right: 16, top: 24, bottom: 28 },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'line' },
      valueFormatter: (v) => `${Number(v).toFixed(1)} 吨`
    },
    xAxis: {
      type: 'category',
      data: shaped.value.map((p) => p.label),
      axisLabel: { fontSize: 11, color: avgColor },
      axisLine: { show: false },
      axisTick: { show: false }
    },
    yAxis: {
      type: 'value',
      axisLabel: { fontSize: 11, color: avgColor },
      splitLine: { lineStyle: { type: 'dashed', opacity: 0.4 } }
    },
    series: [{
      type: 'line',
      smooth: true,
      symbol: 'circle',
      symbolSize: 6,
      data: shaped.value.map((p) => p.output),
      lineStyle: { width: 2, color: lineColor },
      itemStyle: { color: lineColor },
      areaStyle: { color: lineColor, opacity: 0.08 },
      markLine: stats.value.avg > 0 ? {
        symbol: 'none',
        silent: true,
        lineStyle: { type: 'dashed', color: avgColor, width: 1 },
        label: {
          formatter: `均 ${stats.value.avg.toFixed(0)}`,
          position: 'insideEndTop',
          fontSize: 11,
          color: avgColor
        },
        data: [{ yAxis: stats.value.avg }]
      } : undefined
    }]
  }
})
</script>

<template>
  <div class="xt-output-trend" data-testid="manage-output-trend">
    <div class="xt-output-trend__head">
      <span class="xt-output-trend__title">近{{ days }}日产量</span>
      <span class="xt-output-trend__meta" v-if="hasData">
        日均 {{ stats.avg.toFixed(0) }} 吨 · 峰值 {{ stats.max.toFixed(0) }} 吨
      </span>
    </div>
    <VChart
      v-if="hasData"
      class="xt-output-trend__canvas"
      :option="option"
      :theme="chartTheme"
      autoresize
    />
    <div v-else class="xt-output-trend__empty">暂无近期产量数据</div>
  </div>
</template>

<style scoped>
.xt-output-trend {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: var(--xt-space-2);
  padding: var(--xt-space-3);
  border: 1px solid color-mix(in srgb, var(--xt-primary) 24%, var(--xt-border));
  border-radius: var(--xt-radius-xl);
  background:
    radial-gradient(circle at 0% 0%, color-mix(in srgb, var(--xt-primary) 18%, transparent), transparent 36%),
    color-mix(in srgb, var(--xt-bg-ink-panel) 86%, var(--xt-bg-panel));
  box-shadow:
    inset 0 1px 0 color-mix(in srgb, var(--xt-text-inverse) 8%, transparent),
    0 12px 28px color-mix(in srgb, var(--xt-bg-ink) 38%, transparent);
  overflow: hidden;
}

.xt-output-trend::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--xt-primary), transparent);
  opacity: 0.85;
}

.xt-output-trend__head {
  position: relative;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--xt-space-2);
}

.xt-output-trend__title {
  color: var(--xt-text-inverse);
  font-size: var(--xt-text-sm);
  font-weight: 900;
}

.xt-output-trend__meta {
  color: color-mix(in srgb, var(--xt-text-inverse) 58%, transparent);
  font-size: var(--xt-text-xs);
  font-variant-numeric: tabular-nums;
}

.xt-output-trend__canvas {
  position: relative;
  width: 100%;
  height: 220px;
}

.xt-output-trend__empty {
  display: grid;
  place-items: center;
  height: 220px;
  color: color-mix(in srgb, var(--xt-text-inverse) 48%, transparent);
  font-size: var(--xt-text-sm);
}

@media (max-width: 720px) {
  .xt-output-trend__canvas { height: 180px; }
}
</style>
