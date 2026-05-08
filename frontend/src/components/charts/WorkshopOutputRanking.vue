<script setup>
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent])

const props = defineProps({
  items: { type: Array, default: () => [] },
})

const option = computed(() => {
  const sorted = [...props.items].sort((a, b) => a.total_output_tons - b.total_output_tons)
  const labels = sorted.map((d) => d.workshop_name || '-')
  const outputData = sorted.map((d) => Number((d.total_output_tons || 0).toFixed(1)))
  const scrapData = sorted.map((d) => {
    const input = d.total_input_tons || 0
    const output = d.total_output_tons || 0
    return Number(Math.max(input - output, 0).toFixed(1))
  })
  return {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter(params) {
        const ws = params[0]?.name || ''
        const lines = params.map((p) => `${p.marker} ${p.seriesName}: ${p.value} 吨`)
        return `<strong>${ws}</strong><br>${lines.join('<br>')}`
      },
    },
    grid: { left: 80, right: 24, top: 12, bottom: 28 },
    xAxis: {
      type: 'value',
      name: '吨',
      nameTextStyle: { color: '#57606a', fontSize: 11 },
      axisLine: { show: false },
      splitLine: { lineStyle: { color: '#eaeef2' } },
      axisLabel: { color: '#57606a', fontSize: 11 },
    },
    yAxis: {
      type: 'category',
      data: labels,
      axisLabel: { color: '#1f2328', fontSize: 12, fontWeight: 600 },
      axisLine: { lineStyle: { color: '#d0d7de' } },
      axisTick: { show: false },
    },
    series: [
      {
        name: '产出',
        type: 'bar',
        stack: 'total',
        data: outputData,
        itemStyle: { color: '#1f6feb', borderRadius: [0, 0, 0, 0] },
        barWidth: sorted.length <= 4 ? 28 : 18,
      },
      {
        name: '废料',
        type: 'bar',
        stack: 'total',
        data: scrapData,
        itemStyle: { color: '#ff8182', borderRadius: [0, 3, 3, 0] },
      },
    ],
  }
})

const hasData = computed(() => props.items.length > 0)
</script>

<template>
  <div class="chart-card">
    <div class="chart-card__title">车间日产量排行</div>
    <VChart v-if="hasData" :option="option" autoresize class="chart-card__canvas" />
    <div v-else class="chart-card__empty">暂无车间产量数据</div>
  </div>
</template>

<style scoped>
.chart-card { background: #fff; border: 1px solid rgba(43, 93, 178, 0.13); border-radius: 8px; padding: 12px; display: flex; flex-direction: column; min-height: 280px; box-shadow: 0 14px 34px rgba(25, 62, 118, 0.07); }
.chart-card__title { font-size: 13px; font-weight: 900; color: var(--xt-text); margin-bottom: 4px; }
.chart-card__canvas { flex: 1; min-height: 220px; }
.chart-card__empty { flex: 1; display: flex; align-items: center; justify-content: center; color: var(--xt-text-secondary); font-size: 13px; }
</style>
