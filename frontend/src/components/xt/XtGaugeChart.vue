<script setup>
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { GaugeChart } from 'echarts/charts'
import { TooltipComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { useHudChartTheme } from '../../composables/useHudChartTheme.js'

use([CanvasRenderer, GaugeChart, TooltipComponent])

defineOptions({ name: 'XtGaugeChart' })
const chartTheme = useHudChartTheme()

const props = defineProps({
  value: {
    type: Number,
    required: true
  },
  max: {
    type: Number,
    default: 100
  },
  label: {
    type: String,
    default: ''
  },
  unit: {
    type: String,
    default: '%'
  },
  height: {
    type: String,
    default: '180px'
  },
  thresholds: {
    type: Array,
    default: () => [[0.6, '#cf222e'], [0.8, '#bf8700'], [1, '#2da44e']]
  }
})

const option = computed(() => ({
  tooltip: { formatter: `{b}: {c}${props.unit}` },
  series: [{
    type: 'gauge',
    min: 0,
    max: props.max,
    progress: { show: true, width: 12 },
    axisLine: {
      lineStyle: {
        width: 12,
        color: props.thresholds
      }
    },
    axisTick: { show: false },
    splitLine: { show: false },
    axisLabel: { show: false },
    pointer: { show: true, length: '60%', width: 4 },
    anchor: { show: true, size: 8 },
    title: {
      show: true,
      offsetCenter: [0, '70%'],
      fontSize: 12,
      color: 'var(--xt-text-secondary, #57606a)'
    },
    detail: {
      valueAnimation: true,
      fontSize: 20,
      fontFamily: 'var(--xt-font-mono, "JetBrains Mono", monospace)',
      fontFeatureSettings: '"tnum"',
      offsetCenter: [0, '40%'],
      formatter: `{value}${props.unit}`,
      color: 'var(--xt-text-primary, #1f2328)'
    },
    data: [{ value: props.value, name: props.label }]
  }]
}))
</script>

<template>
  <div class="xt-gauge-chart" :style="{ height }">
    <VChart :option="option" :theme="chartTheme" autoresize />
  </div>
</template>

<style scoped>
.xt-gauge-chart {
  width: 100%;
}
</style>
