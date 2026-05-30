<template>
  <section class="xt-today" data-testid="manage-today">
    <header class="xt-today__header">
      <div class="xt-today__title-wrap">
        <h1>昨日总览</h1>
        <button
          v-if="reportingStatus.length"
          type="button"
          class="xt-today__filer-badge"
          :class="`tone-${rosterTone}`"
          @click="rosterOpen = !rosterOpen"
          :aria-expanded="rosterOpen"
        >
          <span class="xt-today__filer-dot" />
          <span class="xt-today__filer-text">
            填报 <b>{{ rosterCounts.reported }}</b>/{{ rosterCounts.total }} 车间
            <span v-if="rosterCounts.unreported > 0" class="xt-today__filer-pending">· 未报 {{ rosterCounts.unreported }}</span>
          </span>
          <span class="xt-today__filer-chev" :class="{ 'is-open': rosterOpen }" aria-hidden="true">›</span>
        </button>
      </div>
      <DateSwitcher
        :model-value="snapshot.targetDate.value"
        :loading="snapshot.loading.value"
        :freshness="snapshot.freshnessStatus.value"
        @step="snapshot.stepDate"
        @refresh="snapshot.load"
        @pick="onDatePick"
      />
    </header>

    <nav class="xt-today__quick-nav" aria-label="核心入口">
      <RouterLink
        v-for="link in quickLinks"
        :key="link.path"
        class="xt-today__quick-link"
        :to="link.path"
      >
        {{ link.label }}
      </RouterLink>
    </nav>

    <YesterdayShiftPanel :payload="snapshot.yesterdayShiftBreakdown.value" />

    <SummaryHero
      :text="summaryText"
      :date="snapshot.targetDate.value"
      :metrics="snapshot.leaderMetrics.value"
    />

    <KpiBar :items="kpiItems" />

    <div class="xt-today__row">
      <OutputTrendLine :series="trendSeries" :days="14" class="xt-today__row-trend" />
        <CostLine
          :estimate="snapshot.managementEstimate.value"
          :series="trendSeries"
          :days="14"
          cost-label="昨日估算成本"
          class="xt-today__row-cost"
        />
    </div>

    <WorkshopBarChart :rows="snapshot.productionLane.value" />

    <Transition name="xt-roster-slide">
      <FilerRoster
        v-if="rosterOpen"
        :reporting-status="reportingStatus"
        :users="userList"
      />
    </Transition>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'

import DateSwitcher from '../../../components/manage/DateSwitcher.vue'
import KpiBar from '../../../components/manage/KpiBar.vue'
import WorkshopBarChart from '../../../components/manage/WorkshopBarChart.vue'
import CostLine from '../../../components/manage/CostLine.vue'
import OutputTrendLine from '../../../components/manage/OutputTrendLine.vue'
import FilerRoster from '../../../components/manage/FilerRoster.vue'
import SummaryHero from '../../../components/manage/SummaryHero.vue'
import YesterdayShiftPanel from '../../../components/manage/YesterdayShiftPanel.vue'
import { rosterStats, buildFilerRoster } from '../../../components/manage/_filerRoster.js'
import { useDashboardSnapshot } from '../../../composables/useDashboardSnapshot.js'
import { fetchTimeseries } from '../../../api/dashboard.js'
import { fetchUsersPage } from '../../../api/users.js'
import { useAuthStore } from '../../../stores/auth.js'

const auth = useAuthStore()
const snapshot = useDashboardSnapshot()
snapshot.load()

const trendSeries = ref([])
const userList = ref([])
const rosterOpen = ref(false)

async function loadTrend(targetDate) {
  try {
    const data = await fetchTimeseries({ target_date: targetDate, days: 14 })
    trendSeries.value = Array.isArray(data) ? data : []
  } catch (_e) {
    trendSeries.value = []
  }
}

async function loadUsers() {
  if (userList.value.length) return
  try {
    const page = await fetchUsersPage({ limit: 300 })
    userList.value = page.items || []
  } catch (_e) {
    userList.value = []
  }
}

loadTrend(snapshot.targetDate.value)
loadUsers()
watch(snapshot.targetDate, (next) => loadTrend(next))

const reportingStatus = computed(() => snapshot.data.value.workshop_reporting_status || [])
const rosterRows = computed(() => buildFilerRoster(reportingStatus.value, userList.value))
const rosterCounts = computed(() => rosterStats(rosterRows.value))
const rosterTone = computed(() => {
  const c = rosterCounts.value
  if (!c.total) return 'muted'
  if (c.unreported === 0 && c.abnormal === 0) return 'success'
  if (c.unreported > 0) return 'danger'
  return 'warning'
})

function onDatePick(next) {
  if (next && typeof next === 'string') snapshot.targetDate.value = next
}

const fmt = (v, digits = 2) =>
  (v == null || Number.isNaN(Number(v))) ? '—' : Number(v).toFixed(digits)

const outputTonsSpark = computed(() => {
  const tail = trendSeries.value.slice(-7)
  return tail.map((r) => Number(r.output_weight ?? r.output ?? 0) / 1000)
})
const energyPerTonSpark = computed(() => {
  const tail = trendSeries.value.slice(-7)
  return tail.map((r) => {
    const tons = Number(r.output_weight ?? r.output ?? 0) / 1000
    const kwh = r.energy == null ? null : Number(r.energy)
    return tons > 0 && kwh != null ? kwh / tons : null
  })
})
const mtdSpark = computed(() => {
  const tail = trendSeries.value.slice(-7)
  let cum = 0
  return tail.map((r) => {
    cum += Number(r.output_weight ?? r.output ?? 0) / 1000
    return cum
  })
})

const kpiItems = computed(() => {
  const lm = snapshot.leaderMetrics.value
  const ma = snapshot.monthArchive.value
  const trend = snapshot.trend.value
  const me = snapshot.managementEstimate.value

  const totalOutput = Number(lm.total_output_weight || 0)
  const cost = me.estimated_cost
  const tonCost = (totalOutput > 0 && cost != null) ? (Number(cost) / totalOutput).toFixed(0) : '—'
  const delta = trend.output_delta_vs_yesterday
  const deltaTone = delta == null ? null : (Number(delta) >= 0 ? 'positive' : 'negative')
  const deltaSign = (delta != null && Number(delta) > 0) ? '+' : ''
  const deltaText = delta == null ? null : `${deltaSign}${fmt(delta, 1)} t`

      return [
        {
          key: 'output',
          label: '昨日成品',
          value: fmt(lm.total_output_weight, 2),
          unit: '吨',
      deltaText,
      deltaTone,
      spark: outputTonsSpark.value,
      sparkTone: 'primary'
    },
        {
          key: 'energy',
          label: '昨日吨能耗',
          value: fmt(lm.energy_per_ton, 1),
          unit: 'kWh/吨',
      spark: energyPerTonSpark.value,
      sparkTone: 'warning'
    },
        {
          key: 'cost',
          label: '昨日吨成本',
          value: tonCost,
          unit: '元/吨',
          hint: cost == null ? '估算未就绪' : null
        },
        {
          key: 'mtd',
          label: '月累计成品',
          value: fmt(ma.total_output, 0),
          unit: '吨',
      spark: mtdSpark.value,
      sparkTone: 'success'
    },
    {
      key: 'margin',
      label: '估算毛利',
      value: me.estimate_ready && me.estimated_margin != null ? (Number(me.estimated_margin) / 10000).toFixed(1) : '—',
      unit: '万元',
      status: me.estimate_ready ? null : 'muted',
      hint: me.estimate_ready ? null : '估算未就绪'
    }
  ]
})

const summaryText = computed(() => snapshot.leaderSummary.value.summary_text || '')
const quickLinks = computed(() => {
  const links = [
    { label: '日报', path: '/manage/daily-report' },
    { label: '生产', path: '/manage/production' },
    { label: '能耗', path: '/energy/center' },
    { label: '报表', path: '/manage/reports' },
  ]
  if (auth.adminSurface) {
    links.push(
      { label: '填报明细', path: '/manage/fill-details' },
      { label: '主数据', path: '/manage/master' },
      { label: '用户', path: '/manage/admin/users' },
      { label: '模板', path: '/manage/admin/templates' },
      { label: '规则', path: '/manage/admin/rules' },
      { label: '设置', path: '/manage/admin/settings' },
    )
  }
  return links
})
</script>

<style scoped>
.xt-today { display: flex; flex-direction: column; gap: var(--xt-space-4); }
.xt-today__header {
  display: flex; align-items: flex-end; justify-content: space-between;
  gap: var(--xt-space-3); flex-wrap: wrap;
}
.xt-today__title-wrap { display: flex; align-items: center; gap: var(--xt-space-3); flex-wrap: wrap; }
.xt-today__header h1 { margin: 0; font-size: var(--xt-text-2xl); font-weight: 850; color: var(--xt-text); letter-spacing: -0.02em; }
.xt-today__quick-nav {
  display: flex; align-items: center; gap: var(--xt-space-2);
  overflow-x: auto; padding-bottom: 2px;
}
.xt-today__quick-link {
  flex: 0 0 auto;
  padding: 8px 12px;
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-pill);
  background: var(--xt-bg-panel);
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-sm);
  font-weight: 800;
  text-decoration: none;
}
.xt-today__quick-link:hover {
  color: var(--xt-text);
  border-color: var(--xt-border-strong);
}
@media (max-width: 720px) {
  .xt-today__header { flex-direction: column; align-items: stretch; }
  .xt-today__title-wrap { width: 100%; justify-content: space-between; }
}

.xt-today__filer-badge {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 4px 10px 4px 8px;
  background: var(--xt-bg-panel-soft);
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-pill);
  font-size: var(--xt-text-xs); font-weight: 700;
  color: var(--xt-text-secondary);
  cursor: pointer;
  transition: border-color var(--xt-motion-fast) var(--xt-ease), background var(--xt-motion-fast) var(--xt-ease);
}
.xt-today__filer-badge:hover { border-color: var(--xt-border-strong); }
.xt-today__filer-badge b { color: var(--xt-text); font-weight: 850; font-variant-numeric: tabular-nums; }
.xt-today__filer-dot { width: 7px; height: 7px; border-radius: 50%; background: var(--xt-text-muted); }
.xt-today__filer-badge.tone-success .xt-today__filer-dot { background: var(--xt-success, var(--xt-color-success)); box-shadow: 0 0 0 3px rgba(59, 165, 92, 0.14); }
.xt-today__filer-badge.tone-warning .xt-today__filer-dot { background: var(--xt-warning, var(--xt-color-warning)); box-shadow: 0 0 0 3px rgba(204, 138, 31, 0.14); }
.xt-today__filer-badge.tone-danger .xt-today__filer-dot { background: var(--xt-danger, var(--xt-color-danger)); box-shadow: 0 0 0 3px rgba(214, 82, 65, 0.14); }
.xt-today__filer-pending { color: var(--xt-danger, var(--xt-color-danger)); margin-left: 4px; font-weight: 800; }
.xt-today__filer-chev {
  font-size: 14px; line-height: 1; color: var(--xt-text-muted);
  transition: transform 160ms var(--xt-ease, ease);
  margin-left: 2px;
}
.xt-today__filer-chev.is-open { transform: rotate(90deg); }

.xt-today__row { display: grid; grid-template-columns: minmax(0, 2.4fr) minmax(0, 1fr); gap: var(--xt-space-3); align-items: stretch; }
.xt-today__row-trend { min-width: 0; }
.xt-today__row-cost { align-self: stretch; }
@media (max-width: 960px) {
  .xt-today__row { grid-template-columns: 1fr; }
}

.xt-roster-slide-enter-active,
.xt-roster-slide-leave-active { transition: opacity 200ms ease, transform 200ms ease; }
.xt-roster-slide-enter-from,
.xt-roster-slide-leave-to { opacity: 0; transform: translateY(-8px); }
</style>
