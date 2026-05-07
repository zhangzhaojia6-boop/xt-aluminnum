<script setup>
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

const props = defineProps({
  workshops: { type: Array, default: () => [] },
  shifts: { type: Array, default: () => [] },
})

const PALETTE = ['#1f6feb', '#2da44e', '#bf8700', '#cf222e', '#8250df', '#0969da']

const option = computed(() => {
  const shiftLabels = props.shifts.map((s) => s.shift_name || s.name || `班次${s.id}`)
  const series = props.workshops.map((ws, idx) => ({
    name: ws.workshop_name,
    type: 'line',
    smooth: true,
    symbol: 'circle',
    symbolSize: 6,
    lineStyle: { width: 2 },
    itemStyle: { color: PALETTE[idx % PALETTE.length] },
    data: props.shifts.map((shift) => {
      const cell = (ws.shift_totals || []).find((t) => t.shift_id === shift.id)
      return cell ? Number((cell.output || cell.total_output || 0).toFixed(1)) : 0
    }),
  }))
  return {
    tooltip: { trigger: 'axis' },
    legend: { top: 4, right: 8, textStyle: { color: '#57606a', fontSize: 11 } },
    grid: { left: 44, right: 16, top: 36, bottom: 24 },
    xAxis: { type: 'category', data: shiftLabels, axisLine: { lineStyle: { color: '#d0d7de' } }, axisLabel: { color: '#57606a', fontSize: 11 } },
    yAxis: { type: 'value', name: '吨', nameTextStyle: { color: '#57606a', fontSize: 11 }, axisLine: { show: false }, splitLine: { lineStyle: { color: '#eaeef2' } }, axisLabel: { color: '#57606a', fontSize: 11 } },
    series,
  }
})

const hasData = computed(() => props.workshops.length > 0 && props.shifts.length > 0)
</script>

<template>
  <div class="chart-card">
    <div class="chart-card__title">车间班次产量</div>
    <VChart v-if="hasData" :option="option" autoresize class="chart-card__canvas" />
    <div v-else class="chart-card__empty">暂无班次产量数据</div>
  </div>
</template>

<style scoped>
.chart-card { background: #fff; border: 1px solid #d0d7de; border-radius: 8px; padding: 12px; display: flex; flex-direction: column; min-height: 280px; }
.chart-card__title { font-size: 13px; font-weight: 600; color: #1f2328; margin-bottom: 4px; }
.chart-card__canvas { flex: 1; min-height: 220px; }
.chart-card__empty { flex: 1; display: flex; align-items: center; justify-content: center; color: #6e7781; font-size: 13px; }
</style>
