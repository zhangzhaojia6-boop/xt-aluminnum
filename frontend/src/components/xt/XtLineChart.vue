<script setup>
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { useHudChartTheme } from '../../composables/useHudChartTheme.js'

use([CanvasRenderer, LineChart, GridComponent, TooltipComponent, LegendComponent])

defineOptions({ name: 'XtLineChart' })
const chartTheme = useHudChartTheme()

const props = defineProps({
  series: {
    type: Array,
    required: true
  },
  xLabels: {
    type: Array,
    required: true
  },
  yUnit: {
    type: String,
    default: ''
  },
  height: {
    type: String,
    default: '240px'
  },
  smooth: {
    type: Boolean,
    default: true
  }
})

const PALETTE = ['#1f6feb', '#2da44e', '#bf8700', '#cf222e', '#8250df', '#0969da']

const option = computed(() => ({
  tooltip: { trigger: 'axis' },
  legend: {
    show: props.series.length > 1,
    top: 4,
    right: 8,
    textStyle: { color: 'var(--xt-text-secondary, #57606a)', fontSize: 11 }
  },
  grid: { left: 48, right: 16, top: props.series.length > 1 ? 36 : 12, bottom: 24 },
  xAxis: {
    type: 'category',
    data: props.xLabels,
    axisLine: { lineStyle: { color: 'var(--xt-border, #d0d7de)' } },
    axisLabel: { color: 'var(--xt-text-secondary, #57606a)', fontSize: 11 }
  },
  yAxis: {
    type: 'value',
    name: props.yUnit,
    nameTextStyle: { color: 'var(--xt-text-secondary, #57606a)', fontSize: 11 },
    axisLine: { show: false },
    splitLine: { lineStyle: { color: 'var(--xt-border-light, #eaeef2)' } },
    axisLabel: { color: 'var(--xt-text-secondary, #57606a)', fontSize: 11 }
  },
  series: props.series.map((s, idx) => ({
    name: s.name || '',
    type: 'line',
    smooth: props.smooth,
    symbol: 'circle',
    symbolSize: 5,
    lineStyle: { width: 2 },
    itemStyle: { color: s.color || PALETTE[idx % PALETTE.length] },
    data: s.data
  }))
}))
</script>

<template>
  <div class="xt-line-chart" :style="{ height }" role="img" :aria-label="`折线图: ${series.map(s => s.name).join(', ')}`" >
    <VChart :option="option" :theme="chartTheme" autoresize />
  </div>
</template>

<style scoped>
.xt-line-chart {
  width: 100%;
}
</style>
