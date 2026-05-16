<script setup>
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { LineChart } from 'echarts/charts'
import { GridComponent } from 'echarts/components'
import VChart from 'vue-echarts'

use([CanvasRenderer, LineChart, GridComponent])

defineOptions({ name: 'XtTrendSpark' })

const props = defineProps({
  data: {
    type: Array,
    required: true
  },
  color: {
    type: String,
    default: '#1f6feb'
  },
  width: {
    type: String,
    default: '120px'
  },
  height: {
    type: String,
    default: '32px'
  }
})

const option = computed(() => ({
  grid: { left: 0, right: 0, top: 0, bottom: 0 },
  xAxis: { type: 'category', show: false, data: props.data.map((_, i) => i) },
  yAxis: { type: 'value', show: false },
  series: [{
    type: 'line',
    smooth: true,
    symbol: 'none',
    lineStyle: { width: 1.5, color: props.color },
    areaStyle: { color: props.color, opacity: 0.08 },
    data: props.data
  }]
}))
</script>

<template>
  <div class="xt-trend-spark" :style="{ width, height }">
    <VChart :option="option" autoresize />
  </div>
</template>

<style scoped>
.xt-trend-spark {
  display: inline-block;
}
</style>
