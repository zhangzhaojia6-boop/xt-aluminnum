<script setup>
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, LegendComponent])

defineOptions({ name: 'XtBarChart' })

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
  stacked: {
    type: Boolean,
    default: false
  },
  horizontal: {
    type: Boolean,
    default: false
  }
})

const PALETTE = ['#1f6feb', '#2da44e', '#bf8700', '#cf222e', '#8250df', '#0969da']

const option = computed(() => {
  const categoryAxis = {
    type: 'category',
    data: props.xLabels,
    axisLine: { lineStyle: { color: 'var(--xt-border, #d0d7de)' } },
    axisLabel: { color: 'var(--xt-text-secondary, #57606a)', fontSize: 11 }
  }
  const valueAxis = {
    type: 'value',
    name: props.yUnit,
    nameTextStyle: { color: 'var(--xt-text-secondary, #57606a)', fontSize: 11 },
    axisLine: { show: false },
    splitLine: { lineStyle: { color: 'var(--xt-border-light, #eaeef2)' } },
    axisLabel: { color: 'var(--xt-text-secondary, #57606a)', fontSize: 11 }
  }

  return {
    tooltip: { trigger: 'axis' },
    legend: {
      show: props.series.length > 1,
      top: 4,
      right: 8,
      textStyle: { color: 'var(--xt-text-secondary, #57606a)', fontSize: 11 }
    },
    grid: { left: 48, right: 16, top: props.series.length > 1 ? 36 : 12, bottom: 24 },
    xAxis: props.horizontal ? valueAxis : categoryAxis,
    yAxis: props.horizontal ? categoryAxis : valueAxis,
    series: props.series.map((s, idx) => ({
      name: s.name || '',
      type: 'bar',
      stack: props.stacked ? 'total' : undefined,
      barMaxWidth: 32,
      itemStyle: {
        color: s.color || PALETTE[idx % PALETTE.length],
        borderRadius: [2, 2, 0, 0]
      },
      data: s.data
    }))
  }
})
</script>

<template>
  <div class="xt-bar-chart" :style="{ height }">
    <VChart :option="option" autoresize />
  </div>
</template>

<style scoped>
.xt-bar-chart {
  width: 100%;
}
</style>
