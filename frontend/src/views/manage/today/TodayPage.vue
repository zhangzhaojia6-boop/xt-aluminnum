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

    <FactorySourceStrip :overview="snapshot.factoryCommandOverview.value" />

    <section id="daily-report" class="xt-today__daily" data-testid="daily-report-section">
      <header class="xt-today__daily-head">
        <div>
          <span class="xt-today__daily-eyebrow">昨日日报</span>
          <h2>昨日日报结算</h2>
        </div>
        <div class="xt-today__daily-tags" aria-label="日报核心口径">
          <span v-for="label in dailySectionLabels" :key="label">{{ label }}</span>
        </div>
      </header>

      <div class="xt-today__daily-grid">
        <article class="xt-today__panel xt-today__panel--compare">
          <header class="xt-today__panel-head">
            <h3>算法与填报对照</h3>
            <span>算法能耗 · 电工填报 · 算法成品率 · 内勤对照</span>
          </header>
          <div class="xt-today__compare-grid">
            <div
              v-for="item in comparisonCards"
              :key="item.key"
              class="xt-today__compare-card"
              :class="`tone-${item.tone}`"
            >
              <div class="xt-today__compare-title">{{ item.title }}</div>
              <div class="xt-today__compare-row">
                <span>{{ item.primaryLabel }}</span>
                <b>{{ item.primaryValue }}</b>
              </div>
              <div class="xt-today__compare-row is-muted">
                <span>{{ item.compareLabel }}</span>
                <b>{{ item.compareValue }}</b>
              </div>
            </div>
          </div>
        </article>

        <article class="xt-today__panel xt-today__panel--wip">
          <header class="xt-today__panel-head">
            <h3>外部 MES 当前在制</h3>
            <span>{{ wipRows.length }} 个位置</span>
          </header>
          <div v-if="wipRows.length" class="xt-today__wip-grid">
            <div v-for="row in wipRows" :key="row.key" class="xt-today__wip-card">
              <span>{{ row.title }}</span>
              <b>{{ row.weightText }}</b>
              <small>{{ row.countText }} · {{ row.sourceLabel }}</small>
            </div>
          </div>
          <div v-else class="xt-today__empty">暂无在制料数据</div>
        </article>
      </div>

      <article class="xt-today__panel">
        <header class="xt-today__panel-head">
          <h3>车间过站下机参考</h3>
          <span>不计入全厂最终产量</span>
        </header>
        <table v-if="workshopRows.length" class="xt-today__table">
          <thead>
            <tr>
              <th>车间</th>
              <th class="is-num">过站下机</th>
              <th class="is-num">比昨日</th>
              <th class="is-num">月累计</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in workshopRows" :key="row.key">
              <td>{{ row.workshop }}</td>
              <td class="is-num">{{ row.dailyOutputText }}</td>
              <td class="is-num">{{ row.deltaText }}</td>
              <td class="is-num">{{ row.monthlyOutputText }}</td>
            </tr>
          </tbody>
        </table>
        <div v-else class="xt-today__empty">暂无车间过站数据</div>
      </article>
    </section>

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
import FactorySourceStrip from '../../../components/manage/FactorySourceStrip.vue'
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
import {
  buildDailyComparisonCards,
  buildDailySettlementCards,
  buildDailyWorkshopRows,
  buildDailyWipRows,
} from '../../../utils/manageDailyReportSurface.js'

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
  (v == null || Number.isNaN(Number(v)))
    ? '—'
    : Number(v).toLocaleString('zh-CN', {
      minimumFractionDigits: 0,
      maximumFractionDigits: digits,
    })

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

const dailyOverview = computed(() => snapshot.data.value.daily_overview || {})
const settlementCards = computed(() => buildDailySettlementCards(dailyOverview.value))
const comparisonCards = computed(() => buildDailyComparisonCards(dailyOverview.value))
const workshopRows = computed(() => buildDailyWorkshopRows(dailyOverview.value.workshop_output || []))
const wipRows = computed(() => buildDailyWipRows(dailyOverview.value.wip_distribution || []))
const dailySectionLabels = ['全厂入库产量', '过站下机参考', '合同吨数']

const kpiItems = computed(() => {
  const me = snapshot.managementEstimate.value
  return [
    ...settlementCards.value.map((item) => ({
      ...item,
      spark: item.key === 'plant-output' ? outputTonsSpark.value : (item.key === 'energy-per-ton' ? energyPerTonSpark.value : null),
      sparkTone: item.key === 'energy-per-ton' ? 'warning' : 'primary',
    })),
    {
      key: 'mtd',
      label: '月累计成品',
      value: fmt(snapshot.monthArchive.value.total_output, 0),
      unit: '吨',
      spark: mtdSpark.value,
      sparkTone: 'success'
    },
    {
      key: 'margin',
      label: '估算毛利',
      value: me.estimate_ready && me.estimated_margin != null ? fmt(Number(me.estimated_margin) / 10000, 1) : '—',
      unit: '万元',
      status: me.estimate_ready ? null : 'muted',
      hint: me.estimate_ready ? null : '估算未就绪'
    }
  ]
})

const summaryText = computed(() => snapshot.leaderSummary.value.summary_text || '')
const quickLinks = computed(() => {
  const links = [
    { label: '实时', path: '/manage/live' },
    { label: '日报', path: '/manage/today?section=daily-report' },
    { label: '生产', path: '/manage/production' },
    { label: '填报明细', path: '/manage/fill-details' },
    { label: '异常', path: '/manage/alerts' },
    { label: '能耗', path: '/manage/energy' },
  ]
  if (auth.adminSurface) {
    links.push(
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
.xt-today {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: var(--xt-space-4);
  min-height: 100%;
  padding: var(--xt-space-1);
  color: var(--xt-text-inverse);
}

.xt-today::before,
.xt-today::after {
  content: '';
  position: fixed;
  pointer-events: none;
}

.xt-today::before {
  inset: 0;
  z-index: 0;
  background:
    radial-gradient(circle at 16% 0%, color-mix(in srgb, var(--xt-primary) 24%, transparent), transparent 30%),
    radial-gradient(circle at 86% 10%, color-mix(in srgb, var(--xt-info) 18%, transparent), transparent 32%),
    linear-gradient(180deg, var(--xt-bg-ink), var(--xt-bg-ink-soft));
}

.xt-today::after {
  inset: 0;
  z-index: 1;
  background:
    linear-gradient(90deg, color-mix(in srgb, var(--xt-primary) 10%, transparent) 1px, transparent 1px),
    linear-gradient(color-mix(in srgb, var(--xt-primary) 8%, transparent) 1px, transparent 1px);
  background-size: 34px 34px;
  mask-image: linear-gradient(180deg, color-mix(in srgb, var(--xt-bg-ink) 72%, transparent), transparent 76%);
}

.xt-today > * {
  position: relative;
  z-index: 2;
}

.xt-today__header {
  display: flex;
  align-items: stretch;
  justify-content: space-between;
  gap: var(--xt-space-3);
  flex-wrap: wrap;
  padding: var(--xt-space-4);
  border: 1px solid color-mix(in srgb, var(--xt-primary) 24%, var(--xt-border-ink));
  border-radius: var(--xt-radius-xl);
  background:
    linear-gradient(135deg, color-mix(in srgb, var(--xt-primary) 14%, transparent), transparent 42%),
    linear-gradient(180deg, color-mix(in srgb, var(--xt-bg-ink-panel) 92%, transparent), var(--xt-bg-ink));
  box-shadow: 0 22px 58px color-mix(in srgb, var(--xt-bg-ink) 72%, transparent);
  overflow: hidden;
}

.xt-today__header::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(90deg, transparent, color-mix(in srgb, var(--xt-primary) 22%, transparent), transparent);
  transform: translateX(-100%);
  animation: xt-today-sweep 5.8s var(--xt-ease) infinite;
}

.xt-today__title-wrap {
  display: flex;
  align-items: center;
  gap: var(--xt-space-3);
  flex-wrap: wrap;
}

.xt-today__header h1 {
  margin: 0;
  color: var(--xt-text-inverse);
  font-family: var(--xt-font-display);
  font-size: clamp(var(--xt-text-2xl), 4vw, var(--xt-text-3xl));
  font-weight: 900;
  letter-spacing: -0.04em;
  text-shadow: 0 0 24px color-mix(in srgb, var(--xt-primary) 42%, transparent);
}

.xt-today__quick-nav {
  display: flex;
  align-items: center;
  gap: var(--xt-space-2);
  padding: var(--xt-space-2);
  border: 1px solid color-mix(in srgb, var(--xt-primary) 18%, var(--xt-border-ink));
  border-radius: var(--xt-radius-xl);
  background: color-mix(in srgb, var(--xt-bg-ink-panel) 76%, transparent);
  overflow-x: auto;
  scrollbar-width: thin;
}

.xt-today__quick-link {
  position: relative;
  flex: 0 0 auto;
  padding: 9px 13px;
  border: 1px solid color-mix(in srgb, var(--xt-primary) 15%, var(--xt-border-ink));
  border-radius: var(--xt-radius-pill);
  background: color-mix(in srgb, var(--xt-bg-ink-panel) 70%, transparent);
  color: color-mix(in srgb, var(--xt-text-inverse) 68%, transparent);
  font-size: var(--xt-text-sm);
  font-weight: 850;
  text-decoration: none;
  transition:
    color var(--xt-motion-fast) var(--xt-ease),
    border-color var(--xt-motion-fast) var(--xt-ease),
    background var(--xt-motion-fast) var(--xt-ease),
    transform var(--xt-motion-fast) var(--xt-ease);
}

.xt-today__quick-link:hover,
.xt-today__quick-link.router-link-active {
  color: var(--xt-text-inverse);
  border-color: color-mix(in srgb, var(--xt-primary) 58%, var(--xt-border-ink));
  background: color-mix(in srgb, var(--xt-primary) 16%, var(--xt-bg-ink-panel));
  box-shadow: 0 0 22px color-mix(in srgb, var(--xt-primary) 18%, transparent);
}

.xt-today__quick-link:active {
  transform: scale(0.97);
}

.xt-today__daily {
  position: relative;
  display: grid;
  gap: var(--xt-space-3);
  padding: var(--xt-space-4);
  border: 1px solid color-mix(in srgb, var(--xt-primary) 24%, var(--xt-border-ink));
  border-radius: var(--xt-radius-xl);
  background:
    radial-gradient(circle at 8% 4%, color-mix(in srgb, var(--xt-primary) 16%, transparent), transparent 34%),
    linear-gradient(160deg, color-mix(in srgb, var(--xt-bg-ink-panel) 88%, transparent), color-mix(in srgb, var(--xt-bg-ink) 96%, transparent));
  box-shadow: 0 18px 44px color-mix(in srgb, var(--xt-bg-ink) 62%, transparent);
  overflow: hidden;
}

.xt-today__daily::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    linear-gradient(90deg, transparent, color-mix(in srgb, var(--xt-primary) 16%, transparent), transparent),
    linear-gradient(color-mix(in srgb, var(--xt-text-inverse) 4%, transparent) 50%, transparent 50%);
  background-size: auto, 100% 4px;
  opacity: 0.5;
  transform: translateX(-100%);
  animation: xt-today-sweep 6.4s var(--xt-ease) infinite;
}

.xt-today__daily-head,
.xt-today__panel-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--xt-space-3);
  flex-wrap: wrap;
}

.xt-today__daily-eyebrow {
  display: block;
  margin-bottom: 3px;
  color: color-mix(in srgb, var(--xt-primary) 76%, var(--xt-text-inverse));
  font-size: var(--xt-text-xs);
  font-weight: 900;
  letter-spacing: 0.18em;
}

.xt-today__daily h2,
.xt-today__panel h3 {
  margin: 0;
  color: var(--xt-text-inverse);
  font-family: var(--xt-font-display);
  font-weight: 900;
  letter-spacing: -0.025em;
}

.xt-today__daily h2 {
  font-size: var(--xt-text-xl);
}

.xt-today__panel h3 {
  font-size: var(--xt-text-base);
}

.xt-today__daily-tags {
  display: flex;
  align-items: center;
  gap: var(--xt-space-2);
  flex-wrap: wrap;
}

.xt-today__daily-tags span {
  padding: 5px 10px;
  border: 1px solid color-mix(in srgb, var(--xt-primary) 24%, var(--xt-border-ink));
  border-radius: var(--xt-radius-pill);
  color: color-mix(in srgb, var(--xt-text-inverse) 74%, transparent);
  background: color-mix(in srgb, var(--xt-primary) 9%, var(--xt-bg-ink-panel));
  font-size: var(--xt-text-xs);
  font-weight: 850;
}

.xt-today__daily-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr);
  gap: var(--xt-space-3);
}

.xt-today__panel {
  position: relative;
  display: grid;
  gap: var(--xt-space-3);
  padding: var(--xt-space-3);
  border: 1px solid color-mix(in srgb, var(--xt-primary) 18%, var(--xt-border-ink));
  border-radius: var(--xt-radius-lg);
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--xt-text-inverse) 6%, transparent), transparent),
    color-mix(in srgb, var(--xt-bg-ink-panel) 84%, transparent);
  overflow: hidden;
}

.xt-today__panel::before {
  content: '';
  position: absolute;
  top: 0;
  left: var(--xt-space-3);
  right: var(--xt-space-3);
  height: 1px;
  background: linear-gradient(90deg, transparent, color-mix(in srgb, var(--xt-primary) 55%, transparent), transparent);
}

.xt-today__panel-head span {
  color: color-mix(in srgb, var(--xt-text-inverse) 52%, transparent);
  font-size: var(--xt-text-xs);
  font-weight: 800;
}

.xt-today__compare-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--xt-space-2);
}

.xt-today__compare-card {
  display: grid;
  gap: var(--xt-space-2);
  padding: var(--xt-space-3);
  border: 1px solid color-mix(in srgb, var(--xt-primary) 18%, var(--xt-border-ink));
  border-radius: var(--xt-radius-lg);
  background: color-mix(in srgb, var(--xt-bg-ink) 72%, transparent);
  box-shadow: inset 0 1px 0 color-mix(in srgb, var(--xt-text-inverse) 6%, transparent);
}

.xt-today__compare-card.tone-warning {
  border-color: color-mix(in srgb, var(--xt-warning) 64%, var(--xt-border-ink));
}

.xt-today__compare-card.tone-primary {
  border-color: color-mix(in srgb, var(--xt-primary) 64%, var(--xt-border-ink));
}

.xt-today__compare-title {
  color: var(--xt-text-inverse);
  font-size: var(--xt-text-sm);
  font-weight: 900;
}

.xt-today__compare-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--xt-space-2);
  color: color-mix(in srgb, var(--xt-text-inverse) 62%, transparent);
  font-size: var(--xt-text-xs);
}

.xt-today__compare-row b {
  color: var(--xt-text-inverse);
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-lg);
  font-variant-numeric: tabular-nums;
}

.xt-today__compare-row.is-muted b {
  color: color-mix(in srgb, var(--xt-text-inverse) 72%, transparent);
  font-size: var(--xt-text-base);
}

.xt-today__wip-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--xt-space-2);
}

.xt-today__wip-card {
  display: grid;
  gap: 3px;
  padding: var(--xt-space-2);
  border: 1px solid color-mix(in srgb, var(--xt-primary) 14%, var(--xt-border-ink));
  border-radius: var(--xt-radius-lg);
  background: color-mix(in srgb, var(--xt-bg-ink) 66%, transparent);
}

.xt-today__wip-card span {
  color: color-mix(in srgb, var(--xt-text-inverse) 62%, transparent);
  font-size: var(--xt-text-xs);
  font-weight: 850;
}

.xt-today__wip-card b {
  color: var(--xt-text-inverse);
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-lg);
  font-variant-numeric: tabular-nums;
}

.xt-today__wip-card small {
  color: color-mix(in srgb, var(--xt-text-inverse) 46%, transparent);
  font-size: var(--xt-text-xs);
  font-weight: 750;
}

.xt-today__table {
  width: 100%;
  border-collapse: collapse;
  color: color-mix(in srgb, var(--xt-text-inverse) 82%, transparent);
  font-size: var(--xt-text-sm);
}

.xt-today__table th,
.xt-today__table td {
  padding: var(--xt-space-2);
  border-bottom: 1px solid color-mix(in srgb, var(--xt-primary) 14%, var(--xt-border-ink));
}

.xt-today__table th {
  color: color-mix(in srgb, var(--xt-text-inverse) 48%, transparent);
  font-size: var(--xt-text-xs);
  text-align: left;
}

.xt-today__table tbody tr {
  transition: background var(--xt-motion-fast) var(--xt-ease);
}

.xt-today__table tbody tr:hover {
  background: color-mix(in srgb, var(--xt-primary) 8%, transparent);
}

.xt-today__table .is-num {
  text-align: right;
  font-family: var(--xt-font-number);
  font-variant-numeric: tabular-nums;
}

.xt-today__empty {
  display: grid;
  place-items: center;
  min-height: 96px;
  padding: var(--xt-space-4);
  border: 1px dashed color-mix(in srgb, var(--xt-primary) 22%, var(--xt-border-ink));
  border-radius: var(--xt-radius-lg);
  color: color-mix(in srgb, var(--xt-text-inverse) 52%, transparent);
  font-size: var(--xt-text-sm);
  text-align: center;
  background: color-mix(in srgb, var(--xt-bg-ink) 62%, transparent);
}

.xt-today__filer-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 11px 6px 9px;
  background: color-mix(in srgb, var(--xt-bg-ink-panel) 72%, transparent);
  border: 1px solid color-mix(in srgb, var(--xt-primary) 20%, var(--xt-border-ink));
  border-radius: var(--xt-radius-pill);
  color: color-mix(in srgb, var(--xt-text-inverse) 72%, transparent);
  font-size: var(--xt-text-xs);
  font-weight: 800;
  cursor: pointer;
  transition:
    border-color var(--xt-motion-fast) var(--xt-ease),
    background var(--xt-motion-fast) var(--xt-ease),
    transform var(--xt-motion-fast) var(--xt-ease);
}

.xt-today__filer-badge:hover {
  border-color: color-mix(in srgb, var(--xt-primary) 56%, var(--xt-border-ink));
}

.xt-today__filer-badge:active {
  transform: scale(0.97);
}

.xt-today__filer-badge b {
  color: var(--xt-text-inverse);
  font-family: var(--xt-font-number);
  font-weight: 900;
  font-variant-numeric: tabular-nums;
}

.xt-today__filer-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--xt-text-inverse) 44%, transparent);
}

.xt-today__filer-badge.tone-success .xt-today__filer-dot {
  background: var(--xt-success);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--xt-success) 20%, transparent), 0 0 14px var(--xt-success);
}

.xt-today__filer-badge.tone-warning .xt-today__filer-dot {
  background: var(--xt-warning);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--xt-warning) 20%, transparent), 0 0 14px var(--xt-warning);
}

.xt-today__filer-badge.tone-danger .xt-today__filer-dot {
  background: var(--xt-danger);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--xt-danger) 20%, transparent), 0 0 14px var(--xt-danger);
}

.xt-today__filer-pending {
  color: color-mix(in srgb, var(--xt-danger) 76%, var(--xt-text-inverse));
  margin-left: 4px;
  font-weight: 850;
}

.xt-today__filer-chev {
  margin-left: 2px;
  color: color-mix(in srgb, var(--xt-text-inverse) 48%, transparent);
  font-size: 14px;
  line-height: 1;
  transition: transform 160ms var(--xt-ease, ease);
}

.xt-today__filer-chev.is-open {
  transform: rotate(90deg);
}

.xt-today__row {
  display: grid;
  grid-template-columns: minmax(0, 2.4fr) minmax(0, 1fr);
  gap: var(--xt-space-3);
  align-items: stretch;
}

.xt-today__row-trend {
  min-width: 0;
}

.xt-today__row-cost {
  align-self: stretch;
}

.xt-roster-slide-enter-active,
.xt-roster-slide-leave-active {
  transition: opacity 200ms ease, transform 200ms ease;
}

.xt-roster-slide-enter-from,
.xt-roster-slide-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}

@keyframes xt-today-sweep {
  0% {
    opacity: 0;
    transform: translateX(-100%);
  }
  18% {
    opacity: 0.85;
  }
  100% {
    opacity: 0;
    transform: translateX(100%);
  }
}

@media (max-width: 960px) {
  .xt-today__row {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .xt-today {
    padding: 0;
  }

  .xt-today__header {
    flex-direction: column;
    align-items: stretch;
  }

  .xt-today__title-wrap {
    width: 100%;
    justify-content: space-between;
  }

  .xt-today__daily-grid,
  .xt-today__compare-grid,
  .xt-today__wip-grid {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  .xt-today__header::before,
  .xt-today__daily::before {
    animation: none;
  }

  .xt-today__quick-link,
  .xt-today__filer-badge,
  .xt-today__table tbody tr {
    transition: none;
  }
}
</style>
