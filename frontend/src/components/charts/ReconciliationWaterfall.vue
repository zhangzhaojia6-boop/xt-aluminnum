<script setup>
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, LegendComponent])

const props = defineProps({
  items: { type: Array, default: () => [] },
})

const option = computed(() => {
  const labels = props.items.map((d) => d.workshop_name || d.label || '-')
  const inputData = props.items.map((d) => Number((d.mes_output_tons || 0).toFixed(1)))
  const outputData = props.items.map((d) => Number((d.fill_output_tons || d.local_output_tons || 0).toFixed(1)))
  return {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { top: 4, right: 8, textStyle: { color: '#57606a', fontSize: 11 } },
    grid: { left: 52, right: 16, top: 36, bottom: 48 },
    xAxis: { type: 'category', data: labels, axisLabel: { color: '#57606a', fontSize: 11, rotate: labels.length > 6 ? 25 : 0 }, axisLine: { lineStyle: { color: '#d0d7de' } } },
    yAxis: { type: 'value', name: '吨', nameTextStyle: { color: '#57606a', fontSize: 11 }, axisLine: { show: false }, splitLine: { lineStyle: { color: '#eaeef2' } }, axisLabel: { color: '#57606a', fontSize: 11 } },
    series: [
      { name: '投料', type: 'bar', data: inputData, itemStyle: { color: '#79b8ff' }, barGap: '10%' },
      { name: '产出', type: 'bar', data: outputData, itemStyle: { color: '#1f6feb' } },
    ],
  }
})

const hasData = computed(() => props.items.length > 0)
</script>

<template>
  <div class="chart-card">
    <div class="chart-card__title">车间投料 vs 产出</div>
    <VChart v-if="hasData" :option="option" autoresize class="chart-card__canvas" />
    <div v-else class="chart-card__empty">暂无对账数据</div>
  </div>
</template>

<style scoped>
.chart-card { background: var(--xt-bg-panel, #fff); border: 1px solid var(--xt-border-light, #d0d7de); border-radius: 10px; padding: 12px; display: flex; flex-direction: column; min-height: 280px; box-shadow: var(--xt-shadow-sm, 0 1px 3px rgba(15,23,42,.1)); position: relative; overflow: hidden; }
.chart-card::before { content: ''; position: absolute; inset: 0; pointer-events: none; border-radius: inherit; box-shadow: inset 0 1px 0 rgba(255,255,255,.88); }
.chart-card__title { font-size: 13px; font-weight: 900; color: var(--xt-text, #1f2328); margin-bottom: 4px; }
.chart-card__canvas { flex: 1; min-height: 220px; }
.chart-card__empty { flex: 1; display: flex; align-items: center; justify-content: center; color: var(--xt-text-secondary, #6e7781); font-size: 13px; }
</style>
