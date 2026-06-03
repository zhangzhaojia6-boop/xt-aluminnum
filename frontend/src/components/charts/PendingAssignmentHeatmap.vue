<script setup>
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { HeatmapChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, VisualMapComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { compareShiftLabels, formatShiftLabel } from '../../utils/display.js'

use([CanvasRenderer, HeatmapChart, GridComponent, TooltipComponent, VisualMapComponent])

const props = defineProps({
  rows: { type: Array, default: () => [] },
})

const matrix = computed(() => {
  const wsNames = []
  const shiftNames = []
  const cells = new Map()
  for (const row of props.rows) {
    const ws = row.workshop_name || '未知'
    const sh = formatShiftLabel(row.shift_name, '未知')
    if (!wsNames.includes(ws)) wsNames.push(ws)
    if (!shiftNames.includes(sh)) shiftNames.push(sh)
    cells.set(`${ws}::${sh}`, (cells.get(`${ws}::${sh}`) || 0) + (row.entry_count || row.count || 1))
  }
  shiftNames.sort(compareShiftLabels)
  const data = []
  wsNames.forEach((ws, y) => {
    shiftNames.forEach((sh, x) => {
      data.push([x, y, cells.get(`${ws}::${sh}`) || 0])
    })
  })
  return { wsNames, shiftNames, data }
})

const option = computed(() => {
  const { wsNames, shiftNames, data } = matrix.value
  const maxVal = data.reduce((acc, d) => Math.max(acc, d[2]), 0)
  return {
    tooltip: { position: 'top', formatter: (p) => `${wsNames[p.data[1]]} · ${shiftNames[p.data[0]]}<br/>待归属 <b>${p.data[2]}</b>` },
    grid: { left: 80, right: 16, top: 8, bottom: 28 },
    xAxis: { type: 'category', data: shiftNames, splitArea: { show: true }, axisLine: { lineStyle: { color: '#d0d7de' } }, axisLabel: { color: '#57606a', fontSize: 11 } },
    yAxis: { type: 'category', data: wsNames, splitArea: { show: true }, axisLine: { lineStyle: { color: '#d0d7de' } }, axisLabel: { color: '#57606a', fontSize: 11 } },
    visualMap: { show: false, min: 0, max: maxVal || 1, inRange: { color: ['#f0f4f8', '#79b8ff', '#1f6feb', '#0a3069'] } },
    series: [{ type: 'heatmap', data, label: { show: true, color: '#1f2328', fontSize: 11 }, emphasis: { itemStyle: { shadowBlur: 4, shadowColor: 'rgba(0,0,0,.15)' } } }],
  }
})

const hasData = computed(() => props.rows.length > 0)
</script>

<template>
  <div class="chart-card">
    <div class="chart-card__title">草稿待归属分布</div>
    <VChart v-if="hasData" :option="option" autoresize class="chart-card__canvas" />
    <div v-else class="chart-card__empty">无待归属填报</div>
  </div>
</template>

<style scoped>
.chart-card { background: var(--xt-bg-panel, #fff); border: 1px solid var(--xt-border-light, #d0d7de); border-radius: 10px; padding: 12px; display: flex; flex-direction: column; min-height: 280px; box-shadow: var(--xt-shadow-sm, 0 1px 3px rgba(15,23,42,.1)); position: relative; overflow: hidden; }
.chart-card::before { content: ''; position: absolute; inset: 0; pointer-events: none; border-radius: inherit; box-shadow: inset 0 1px 0 rgba(255,255,255,.88); }
.chart-card__title { font-size: 13px; font-weight: 900; color: var(--xt-text, #1f2328); margin-bottom: 4px; }
.chart-card__canvas { flex: 1; min-height: 220px; }
.chart-card__empty { flex: 1; display: flex; align-items: center; justify-content: center; color: var(--xt-text-secondary, #6e7781); font-size: 13px; }
</style>
