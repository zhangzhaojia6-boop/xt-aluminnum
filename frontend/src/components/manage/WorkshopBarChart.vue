<script setup>
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { mapWorkshopRows } from './_workshopRows.js'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, LegendComponent])

const props = defineProps({ rows: { type: Array, default: () => [] } })
const mapped = computed(() => mapWorkshopRows(props.rows))
const hasData = computed(() => mapped.value.length > 0)
const option = computed(() => {
  const m = mapped.value
  return {
    legend: { data: ['今日', '月日均'], top: 0 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: { left: 90, right: 24, top: 32, bottom: 28 },
    xAxis: { type: 'value', axisLabel: { fontSize: 11 } },
    yAxis: { type: 'category', data: m.map((r) => r.name).reverse(), axisLabel: { fontSize: 12, fontWeight: 700 } },
    series: [
      { name: '今日', type: 'bar', data: m.map((r) => r.today).reverse(), itemStyle: { color: '#1f6feb' }, barGap: 0 },
      { name: '月日均', type: 'bar', data: m.map((r) => r.monthAvg).reverse(), itemStyle: { color: '#b0b8c1' } }
    ]
  }
})
</script>

<template>
  <div class="xt-workshop-bar" data-testid="manage-workshop-bar">
    <VChart v-if="hasData" :option="option" autoresize class="xt-workshop-bar__canvas" />
    <div v-else class="xt-workshop-bar__empty">暂无车间产量数据</div>
  </div>
</template>

<style scoped>
.xt-workshop-bar { background: var(--xt-bg-panel); border: 1px solid var(--xt-border); border-radius: var(--xt-radius-md); padding: var(--xt-space-3); }
.xt-workshop-bar__canvas { width: 100%; height: 360px; }
@media (max-width: 720px) { .xt-workshop-bar__canvas { height: 240px; } }
.xt-workshop-bar__empty { color: var(--xt-text-muted); padding: var(--xt-space-4); text-align: center; }
</style>
