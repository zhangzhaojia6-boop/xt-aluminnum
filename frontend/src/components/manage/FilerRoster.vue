<script setup>
import { computed } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import VChart from 'vue-echarts'
import { useHudChartTheme } from '../../composables/useHudChartTheme.js'
import { buildFilerRoster, rosterStats, statusTone, statusLabel } from './_filerRoster.js'

use([CanvasRenderer, BarChart, GridComponent, TooltipComponent, LegendComponent])

const props = defineProps({
  reportingStatus: { type: Array, default: () => [] },
  users: { type: Array, default: () => [] }
})

const chartTheme = useHudChartTheme()

const roster = computed(() => buildFilerRoster(props.reportingStatus, props.users))
const stats = computed(() => rosterStats(roster.value))
const hasData = computed(() => roster.value.length > 0)

function readToken(name, fallback) {
  if (typeof window === 'undefined' || !window.getComputedStyle) return fallback
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim()
  return v || fallback
}

const progressOption = computed(() => {
  const okC = readToken('--xt-success', '#3ba55c')
  const warnC = readToken('--xt-warning', '#cc8a1f')
  const dangerC = readToken('--xt-danger', '#d65241')
  const s = stats.value
  return {
    grid: { left: 0, right: 0, top: 4, bottom: 4 },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    xAxis: { type: 'value', show: false, max: Math.max(s.total, 1) },
    yAxis: { type: 'category', show: false, data: ['进度'] },
    series: [
      { name: '已报', type: 'bar', stack: 't', data: [s.reported], itemStyle: { color: okC, borderRadius: [4, 0, 0, 4] } },
      { name: '异常/迟', type: 'bar', stack: 't', data: [s.abnormal], itemStyle: { color: warnC } },
      { name: '未报', type: 'bar', stack: 't', data: [s.unreported], itemStyle: { color: dangerC, borderRadius: [0, 4, 4, 0] } }
    ]
  }
})

function fmtOps(ops) {
  if (!ops || !ops.length) return '主操未配'
  return ops.map((o) => o.name).filter(Boolean).join('、') || '主操未配'
}

function machineSummary(r) {
  if (!r.machineCount) return '—'
  return `开机 ${r.onlineCount} / ${r.machineCount}`
}
</script>

<template>
  <section class="xt-filer-roster" data-testid="manage-filer-roster">
    <header class="xt-filer-roster__head">
      <div class="xt-filer-roster__title">
        <span class="xt-filer-roster__title-text">车间填报责任表</span>
        <span class="xt-filer-roster__total">{{ stats.total }} 个车间</span>
      </div>
      <div class="xt-filer-roster__legend" v-if="hasData">
        <span class="xt-tag tone-success">已报 {{ stats.reported }}</span>
        <span class="xt-tag tone-warning">异常/迟 {{ stats.abnormal }}</span>
        <span class="xt-tag tone-danger">未报 {{ stats.unreported }}</span>
      </div>
    </header>

    <div class="xt-filer-roster__progress" v-if="hasData">
      <VChart class="xt-filer-roster__progress-chart" :option="progressOption" :theme="chartTheme" autoresize />
    </div>

    <div class="xt-filer-roster__grid" v-if="hasData">
      <article
        v-for="r in roster"
        :key="r.workshopId"
        class="xt-filer-card"
        :class="`tone-${statusTone(r.reportStatus)}`"
      >
        <header class="xt-filer-card__head">
          <span class="xt-filer-card__name">{{ r.workshopName }}</span>
          <span class="xt-filer-card__status" :class="`tone-${statusTone(r.reportStatus)}`">{{ statusLabel(r.reportStatus) }}</span>
        </header>
        <div class="xt-filer-card__source">{{ r.sourceLabel || '—' }}</div>
        <div class="xt-filer-card__machines" v-if="r.machines && r.machines.length">
          <span
            v-for="m in r.machines"
            :key="m.id"
            class="xt-machine-chip"
            :class="m.online ? 'is-on' : 'is-off'"
          >{{ m.id }}</span>
        </div>
        <div class="xt-filer-card__machines-empty" v-else>机列未录入</div>
        <div class="xt-filer-card__machine-count">{{ machineSummary(r) }}</div>
      </article>
    </div>

    <div v-else class="xt-filer-roster__empty">暂无车间填报数据</div>
  </section>
</template>

<style scoped>
.xt-filer-roster {
  background: var(--xt-bg-panel);
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-md);
  padding: var(--xt-space-3);
  display: flex; flex-direction: column; gap: var(--xt-space-3);
}
.xt-filer-roster__head { display: flex; align-items: center; justify-content: space-between; gap: var(--xt-space-3); flex-wrap: wrap; }
.xt-filer-roster__title { display: flex; align-items: baseline; gap: var(--xt-space-2); }
.xt-filer-roster__title-text { font-size: var(--xt-text-base); font-weight: 850; color: var(--xt-text); }
.xt-filer-roster__total { font-size: var(--xt-text-xs); color: var(--xt-text-muted); font-weight: 700; }
.xt-filer-roster__legend { display: flex; gap: var(--xt-space-2); flex-wrap: wrap; }
.xt-tag { font-size: var(--xt-text-xs); font-weight: 800; padding: 2px var(--xt-space-2); border-radius: var(--xt-radius-pill); border: 1px solid; }
.xt-tag.tone-success { color: var(--xt-success); border-color: var(--xt-success-border); background: var(--xt-success-light); }
.xt-tag.tone-warning { color: var(--xt-warning); border-color: var(--xt-warning-border); background: var(--xt-warning-light); }
.xt-tag.tone-danger { color: var(--xt-danger); border-color: var(--xt-danger-border); background: var(--xt-danger-light); }

.xt-filer-roster__progress-chart { width: 100%; height: 14px; }
.xt-filer-roster__grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: var(--xt-space-2); }
.xt-filer-card { padding: var(--xt-space-2) var(--xt-space-3); border: 1px solid var(--xt-border); border-radius: var(--xt-radius-sm); background: var(--xt-bg-panel-soft); display: flex; flex-direction: column; gap: 4px; transition: border-color var(--xt-motion-fast) var(--xt-ease); }
.xt-filer-card.tone-success { border-left: 3px solid var(--xt-success); }
.xt-filer-card.tone-warning { border-left: 3px solid var(--xt-warning); }
.xt-filer-card.tone-danger { border-left: 3px solid var(--xt-danger); }
.xt-filer-card.tone-muted { border-left: 3px solid var(--xt-border-strong); opacity: 0.7; }
.xt-filer-card__head { display: flex; align-items: center; justify-content: space-between; gap: var(--xt-space-2); }
.xt-filer-card__name { font-size: var(--xt-text-sm); font-weight: 800; color: var(--xt-text); }
.xt-filer-card__status { font-size: var(--xt-text-xs); font-weight: 800; padding: 0 6px; border-radius: var(--xt-radius-pill); }
.xt-filer-card__status.tone-success { color: var(--xt-success); background: var(--xt-success-light); }
.xt-filer-card__status.tone-warning { color: var(--xt-warning); background: var(--xt-warning-light); }
.xt-filer-card__status.tone-danger { color: var(--xt-danger); background: var(--xt-danger-light); }
.xt-filer-card__status.tone-muted { color: var(--xt-text-muted); background: var(--xt-bg-panel-muted); }
.xt-filer-card__source { font-size: var(--xt-text-xs); color: var(--xt-text-muted); }
.xt-filer-card__machines { display: flex; flex-wrap: wrap; gap: 4px; min-height: 20px; }
.xt-filer-card__machines-empty { font-size: var(--xt-text-xs); color: var(--xt-text-muted); font-style: italic; }
.xt-machine-chip {
  display: inline-flex; align-items: center; justify-content: center;
  font-size: var(--xt-text-xs); font-weight: 700;
  padding: 1px 6px; border-radius: var(--xt-radius-sm);
  border: 1px solid; min-width: 22px;
  font-feature-settings: "tnum" 1;
}
.xt-machine-chip.is-on {
  color: var(--xt-success); border-color: var(--xt-success-border);
  background: var(--xt-success-light);
}
.xt-machine-chip.is-off {
  color: var(--xt-text-muted); border-color: var(--xt-border);
  background: var(--xt-bg-panel-muted); opacity: 0.65;
}
.xt-filer-card__machine-count { font-size: var(--xt-text-xs); color: var(--xt-text-secondary); font-weight: 700; }
.xt-filer-roster__empty { color: var(--xt-text-muted); padding: var(--xt-space-4); text-align: center; }
</style>
