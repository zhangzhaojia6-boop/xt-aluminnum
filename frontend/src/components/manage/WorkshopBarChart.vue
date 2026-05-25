<script setup>
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { useHudChartTheme } from '../../composables/useHudChartTheme.js'
import { mapWorkshopRows } from './_workshopRows.js'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, LegendComponent])

const props = defineProps({ rows: { type: Array, default: () => [] } })
const chartTheme = useHudChartTheme()
const mapped = computed(() => mapWorkshopRows(props.rows))
const hasData = computed(() => mapped.value.length > 0)

function readToken(name, fallback) {
  if (typeof window === 'undefined' || !window.getComputedStyle) return fallback
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return v || fallback
}

const peakValue = computed(() =>
  mapped.value.reduce((m, r) => (r.today > m ? r.today : m), 0)
)

const option = computed(() => {
  const m = mapped.value
  const todayColor = readToken('--xt-primary', '#1f6feb')
  const peakColor = readToken('--xt-success', '#3ba55c')
  const avgColor = readToken('--xt-text-muted', '#94a3b8')
  const labelColor = readToken('--xt-text', '#0f172a')

  const reversed = [...m].reverse()
  const peak = peakValue.value
  const totalRanks = m.length

  // each bar gets an explicit color via richer data items so peak pops
  const todayData = reversed.map((r, i) => {
    const rankFromTop = totalRanks - i
    const isTop = rankFromTop === 1
    return {
      value: r.today,
      itemStyle: {
        color: isTop ? peakColor : todayColor,
        borderRadius: [0, 6, 6, 0]
      }
    }
  })
  const avgData = reversed.map((r) => r.monthAvg)

  return {
    legend: {
      data: ['今日', '月日均'],
      top: 0,
      icon: 'roundRect',
      itemWidth: 12,
      itemHeight: 8,
      textStyle: { fontSize: 11 }
    },
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (params) => {
        if (!params?.length) return ''
        const name = params[0].name
        const today = params.find((p) => p.seriesName === '今日')?.value ?? null
        const avg = params.find((p) => p.seriesName === '月日均')?.value ?? null
        const delta = (Number.isFinite(today) && Number.isFinite(avg) && avg > 0)
          ? (((today - avg) / avg) * 100).toFixed(1)
          : null
        const deltaTxt = delta == null ? '' :
          `<br/><span style="color:${delta >= 0 ? peakColor : avgColor}">${delta >= 0 ? '↑' : '↓'} ${Math.abs(delta)}%</span> vs 月均`
        return `<b>${name}</b><br/>` +
          `今日 ${Number(today || 0).toFixed(2)} 吨<br/>` +
          (avg != null ? `月均 ${Number(avg).toFixed(2)} 吨${deltaTxt}` : '月均 —')
      }
    },
    grid: { left: 110, right: 56, top: 32, bottom: 16 },
    xAxis: {
      type: 'value',
      axisLabel: { fontSize: 10, color: avgColor },
      splitLine: { lineStyle: { type: 'dashed', opacity: 0.3 } }
    },
    yAxis: {
      type: 'category',
      data: reversed.map((r, i) => `${totalRanks - i}. ${r.name}`),
      axisLabel: {
        fontSize: 12,
        fontWeight: 700,
        color: labelColor
      },
      axisLine: { show: false },
      axisTick: { show: false }
    },
    series: [
      {
        name: '今日',
        type: 'bar',
        data: todayData,
        barGap: 0,
        barCategoryGap: '32%',
        label: {
          show: true,
          position: 'right',
          fontSize: 11,
          fontWeight: 700,
          color: labelColor,
          formatter: (p) => Number(p.value || 0).toFixed(1)
        }
      },
      {
        name: '月日均',
        type: 'bar',
        data: avgData,
        itemStyle: { color: avgColor, borderRadius: [0, 6, 6, 0], opacity: 0.45 },
        barCategoryGap: '32%'
      }
    ]
  }
})
</script>

<template>
  <section class="xt-workshop-bar" data-testid="manage-workshop-bar">
    <header class="xt-workshop-bar__head">
      <span class="xt-workshop-bar__title">车间产量排名</span>
      <span v-if="hasData" class="xt-workshop-bar__meta">
        共 <b>{{ mapped.length }}</b> 个 · 峰值 <b>{{ peakValue.toFixed(1) }}</b> 吨
      </span>
    </header>
    <VChart
      v-if="hasData"
      :option="option"
      :theme="chartTheme"
      autoresize
      class="xt-workshop-bar__canvas"
    />
    <div v-else class="xt-workshop-bar__empty">暂无车间产量数据</div>
  </section>
</template>

<style scoped>
.xt-workshop-bar {
  background: var(--xt-bg-panel);
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-md);
  padding: var(--xt-space-3);
  display: flex;
  flex-direction: column;
  gap: var(--xt-space-2);
}
.xt-workshop-bar__head { display: flex; align-items: baseline; justify-content: space-between; gap: var(--xt-space-2); }
.xt-workshop-bar__title { font-size: var(--xt-text-base); font-weight: 850; color: var(--xt-text); }
.xt-workshop-bar__meta { font-size: var(--xt-text-xs); color: var(--xt-text-muted); font-variant-numeric: tabular-nums; }
.xt-workshop-bar__meta b { color: var(--xt-text); font-weight: 850; }
.xt-workshop-bar__canvas { width: 100%; height: 420px; }
@media (max-width: 720px) { .xt-workshop-bar__canvas { height: 280px; } }
.xt-workshop-bar__empty { color: var(--xt-text-muted); padding: var(--xt-space-4); text-align: center; }
</style>
