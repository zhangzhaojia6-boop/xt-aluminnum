<script setup>
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, MarkLineComponent } from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, MarkLineComponent])

const props = defineProps({
  items: { type: Array, default: () => [] },
  threshold: { type: Number, default: 3 },
})

const option = computed(() => {
  const labels = props.items.map((d) => d.workshop_name || '-')
  const scrapRates = props.items.map((d) => {
    if (d.yield_rate == null) return null
    return Number((100 - d.yield_rate).toFixed(2))
  })
  return {
    tooltip: {
      trigger: 'axis',
      formatter(params) {
        const p = params[0]
        if (!p) return ''
        return `<strong>${p.name}</strong><br>废料率: ${p.value ?? '--'}%`
      },
    },
    grid: { left: 80, right: 24, top: 20, bottom: 28 },
    xAxis: {
      type: 'category',
      data: labels,
      axisLabel: { color: '#57606a', fontSize: 11 },
      axisLine: { lineStyle: { color: '#d0d7de' } },
    },
    yAxis: {
      type: 'value',
      name: '%',
      nameTextStyle: { color: '#57606a', fontSize: 11 },
      axisLine: { show: false },
      splitLine: { lineStyle: { color: '#eaeef2' } },
      axisLabel: { color: '#57606a', fontSize: 11 },
    },
    series: [
      {
        type: 'line',
        data: scrapRates,
        symbol: 'circle',
        symbolSize: 8,
        lineStyle: { color: '#57606a', width: 2 },
        itemStyle: {
          color(params) {
            return params.value > props.threshold ? '#cf222e' : '#1f6feb'
          },
        },
        markLine: {
          silent: true,
          symbol: 'none',
          lineStyle: { color: '#cf222e', type: 'dashed', width: 1 },
          data: [{ yAxis: props.threshold, label: { formatter: `阈值 ${props.threshold}%`, color: '#cf222e', fontSize: 11 } }],
        },
      },
    ],
  }
})

const hasData = computed(() => props.items.some((d) => d.yield_rate != null))
</script>

<template>
  <div class="chart-card">
    <div class="chart-card__title">车间废料率</div>
    <VChart v-if="hasData" :option="option" autoresize class="chart-card__canvas" />
    <div v-else class="chart-card__empty">暂无废料率数据</div>
  </div>
</template>

<style scoped>
.chart-card { background: #fff; border: 1px solid rgba(43, 93, 178, 0.13); border-radius: 8px; padding: 12px; display: flex; flex-direction: column; min-height: 280px; box-shadow: 0 14px 34px rgba(25, 62, 118, 0.07); }
.chart-card__title { font-size: 13px; font-weight: 900; color: var(--xt-text); margin-bottom: 4px; }
.chart-card__canvas { flex: 1; min-height: 220px; }
.chart-card__empty { flex: 1; display: flex; align-items: center; justify-content: center; color: var(--xt-text-secondary); font-size: 13px; }
</style>
