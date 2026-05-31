<script setup>
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { useHudChartTheme } from '../../composables/useHudChartTheme.js'
import { mapWorkshopRows } from './_workshopRows.js'
import { formatNumber } from '../../utils/display.js'

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
  const todayColor = readToken('--xt-primary', 'rgb(94, 184, 255)')
  const peakColor = readToken('--xt-success', 'rgb(78, 203, 138)')
  const avgColor = readToken('--xt-text-inverse', 'rgba(224, 236, 255, 0.58)')
  const labelColor = readToken('--xt-text-inverse', 'rgba(224, 236, 255, 0.9)')

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
          `今日 ${formatNumber(today || 0, 2)} 吨<br/>` +
          (avg != null ? `月均 ${formatNumber(avg, 2)} 吨${deltaTxt}` : '月均 —')
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
          formatter: (p) => formatNumber(p.value || 0, 1)
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
        共 <b>{{ mapped.length }}</b> 个 · 峰值 <b>{{ formatNumber(peakValue, 1) }}</b> 吨
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
  position: relative;
  display: flex;
  flex-direction: column;
  gap: var(--xt-space-2);
  padding: var(--xt-space-3);
  border: 1px solid color-mix(in srgb, var(--xt-primary) 24%, var(--xt-border));
  border-radius: var(--xt-radius-xl);
  background:
    radial-gradient(circle at 96% 0%, color-mix(in srgb, var(--xt-success) 14%, transparent), transparent 34%),
    color-mix(in srgb, var(--xt-bg-ink-panel) 88%, var(--xt-bg-panel));
  box-shadow:
    inset 0 1px 0 color-mix(in srgb, var(--xt-text-inverse) 8%, transparent),
    0 18px 40px color-mix(in srgb, var(--xt-bg-ink) 48%, transparent);
  overflow: hidden;
}

.xt-workshop-bar::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--xt-success), var(--xt-primary), transparent);
  opacity: 0.85;
}

.xt-workshop-bar__head {
  position: relative;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--xt-space-2);
}

.xt-workshop-bar__title {
  color: var(--xt-text-inverse);
  font-size: var(--xt-text-base);
  font-weight: 900;
}

.xt-workshop-bar__meta {
  color: color-mix(in srgb, var(--xt-text-inverse) 58%, transparent);
  font-size: var(--xt-text-xs);
  font-variant-numeric: tabular-nums;
}

.xt-workshop-bar__meta b {
  color: var(--xt-text-inverse);
  font-family: var(--xt-font-number);
  font-weight: 900;
}

.xt-workshop-bar__canvas {
  position: relative;
  width: 100%;
  height: 420px;
}

.xt-workshop-bar__empty {
  padding: var(--xt-space-4);
  color: color-mix(in srgb, var(--xt-text-inverse) 48%, transparent);
  text-align: center;
}

@media (max-width: 720px) {
  .xt-workshop-bar__canvas { height: 280px; }
}
</style>
