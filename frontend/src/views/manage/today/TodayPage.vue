<template>
  <section
    class="xt-today"
    data-testid="manage-today"
    data-visual-pass="stitch-image2-second-pass"
    :data-stitch-project-id="stitchSurface.stitch.projectId"
    :data-stitch-screen-id="stitchSurface.stitch.screenId"
  >
    <header class="xt-today__topbar">
      <div class="xt-today__identity">
        <span>鑫泰铝业 数据中枢</span>
        <h1>工厂总览</h1>
        <p>统计周期：{{ businessDateLabel }}</p>
      </div>

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

      <div class="xt-today__top-actions">
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
        <DateSwitcher
          :model-value="snapshot.targetDate.value"
          :loading="snapshot.loading.value"
          :freshness="snapshot.freshnessStatus.value"
          @step="snapshot.stepDate"
          @refresh="snapshot.load"
          @pick="onDatePick"
        />
      </div>
    </header>

    <KpiBar :items="kpiItems" />

    <section class="xt-today__fact-strip" data-testid="today-fact-closure" aria-label="关键事实闭环">
      <button
        v-for="fact in factClosureSurface.criticalFields"
        :key="fact.key"
        type="button"
        class="xt-today__fact-item"
        :class="`is-${fact.status}`"
        :disabled="!fact.traceId"
        :aria-label="fact.traceId ? `查看${factFieldLabel(fact.key)}事实链` : `${factFieldLabel(fact.key)}无可用事实链`"
        @click="openTrace(fact.traceId)"
      >
        <span class="xt-today__fact-label">{{ factFieldLabel(fact.key) }}</span>
        <strong>
          {{ factValueText(fact) }}
          <small v-if="fact.unit">{{ fact.unit }}</small>
        </strong>
        <span class="xt-today__fact-status">{{ factStatusText(fact.status) }}</span>
        <span class="xt-today__fact-source">{{ fact.source }}</span>
        <span class="xt-today__fact-window">{{ fact.businessWindow || '--' }}</span>
      </button>
    </section>

    <section
      v-if="factActionSummary.openCount"
      class="xt-today__fact-actions"
      data-testid="today-fact-actions"
      aria-label="事实行动摘要"
    >
      <div class="xt-today__fact-action-lead">
        <span>事实待办</span>
        <strong>{{ factActionSummary.openCount }}</strong>
      </div>
      <div>
        <span>可人工补录</span>
        <strong>{{ factActionSummary.actionableCount }}</strong>
      </div>
      <div>
        <span>入口已发送</span>
        <strong>{{ factActionSummary.notifiedCount }}</strong>
      </div>
      <div>
        <span>来源复查</span>
        <strong>{{ factActionSummary.sourceRecheckCount }}</strong>
      </div>
      <div>
        <span>依赖补齐</span>
        <strong>{{ factActionSummary.dependencyCount }}</strong>
      </div>
      <RouterLink
        class="xt-today__fact-action-link"
        :to="factActionRoute"
        :aria-label="compactClient ? '查看日报事实' : '打开事实待办'"
      >
        <el-icon><ArrowRight /></el-icon>
      </RouterLink>
    </section>

    <section
      id="daily-report"
      class="xt-today__command-wall"
      data-testid="today-command-wall"
    >
      <div class="xt-today__command-main">
        <article class="xt-today__panel xt-today__flow" data-testid="today-production-flow">
          <header class="xt-today__panel-head">
            <h2>生产流转总览</h2>
            <span>算法主口径 · 填报数据作对照</span>
          </header>

          <ol class="xt-today__flow-steps">
            <li
              v-for="stage in productionFlowStages"
              :key="stage.key"
              class="xt-today__flow-step"
              :class="`stage-${stage.key}`"
            >
              <IndustrialProcessIcon class="xt-today__flow-icon" :stage="stage.key" />
              <div class="xt-today__flow-title">{{ stage.label }}</div>
              <div class="xt-today__flow-metric">
                <span>{{ stage.primaryLabel }}</span>
                <b>{{ stage.primaryValue }}</b>
              </div>
              <div class="xt-today__flow-metric is-muted">
                <span>{{ stage.secondaryLabel }}</span>
                <b>{{ stage.secondaryValue }}</b>
              </div>
              <ul v-if="stage.subItems.length" class="xt-today__flow-sub">
                <li v-for="sub in stage.subItems" :key="sub.label">
                  <span>{{ sub.label }}</span>
                  <b>{{ sub.value }}</b>
                </li>
              </ul>
            </li>
          </ol>
        </article>

        <div class="xt-today__lower-grid">
          <article class="xt-today__panel xt-today__workshop">
            <header class="xt-today__panel-head">
              <h2>车间产量概览</h2>
              <span>过站下机参考，不计入全厂最终产量</span>
            </header>
            <table v-if="workshopRows.length" class="xt-today__table">
              <thead>
                <tr>
                  <th>车间 / 工序</th>
                  <th class="is-num">日产</th>
                  <th class="is-num">月累计</th>
                  <th class="is-num">比昨日</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in workshopRows" :key="row.key">
                  <td>{{ row.workshop }}</td>
                  <td class="is-num">{{ row.dailyOutputText }}</td>
                  <td class="is-num">{{ row.monthlyOutputText }}</td>
                  <td class="is-num">{{ row.deltaText }}</td>
                </tr>
              </tbody>
            </table>
            <div v-else class="xt-today__empty">暂无车间过站数据</div>
          </article>

          <article class="xt-today__panel xt-today__wip">
            <header class="xt-today__panel-head">
              <h2>在制料分布</h2>
              <span>{{ wipRows.length }} 个位置 · {{ wipTotalText }}</span>
            </header>
            <div v-if="wipRows.length" class="xt-today__wip-grid">
              <div v-for="row in wipRows" :key="row.key" class="xt-today__wip-card">
                <span>{{ row.title }}</span>
                <b>{{ row.weightText }}</b>
                <small>{{ row.countText }} · {{ row.feedingText }}</small>
              </div>
            </div>
            <div v-else class="xt-today__empty">暂无在制料数据</div>
          </article>
        </div>

        <div class="xt-today__metric-grid">
          <article
            v-for="item in comparisonCards"
            :key="item.key"
            class="xt-today__compare-card"
            :class="`tone-${item.tone}`"
          >
            <span>{{ item.title }}</span>
            <strong>{{ item.primaryValue }}</strong>
            <small>{{ item.compareLabel }}：{{ item.compareValue }}</small>
          </article>
          <article
            v-for="item in highlightMetrics"
            :key="item.key"
            class="xt-today__compare-card"
            :class="`tone-${item.tone}`"
          >
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
            <small>{{ item.subText }}</small>
          </article>
        </div>
      </div>

      <aside class="xt-today__event-rail" data-testid="today-event-rail">
        <header class="xt-today__rail-head">
          <h2>异常 / 催报 / 告警 / AI 摘要</h2>
          <span>{{ eventRailItems.length }} 条</span>
        </header>

        <section class="xt-today__shift-card">
          <header class="xt-today__panel-head">
            <h3>三班填报</h3>
            <span>长白班-小夜班-大夜班</span>
          </header>
          <div class="xt-today__shift-list">
            <div
              v-for="shift in shiftTiles"
              :key="shift.key"
              class="xt-today__shift-row"
            >
              <span>{{ shift.name }}</span>
              <b>{{ shift.reported }}</b>
              <small>{{ shift.timeRange }}</small>
            </div>
          </div>
        </section>

        <article
          v-for="item in eventRailItems"
          :key="item.key"
          class="xt-today__event-card"
          :class="`tone-${item.tone}`"
        >
          <div class="xt-today__event-top">
            <span>{{ item.label }}</span>
            <time>{{ item.time }}</time>
          </div>
          <strong>{{ item.title }}</strong>
          <p>{{ item.body }}</p>
        </article>

        <MissingReportPanel
          title="缺报明细"
          :rows="missingRows"
          :loading="liveLoading"
          compact
        />
      </aside>
    </section>

    <footer class="xt-today__bottom-status" data-testid="stitch-bottom-status" aria-label="系统状态">
      <span
        v-for="item in bottomStatusItems"
        :key="item.key"
        class="xt-today__status-pill"
        :class="`tone-${item.tone}`"
      >
        <i aria-hidden="true" />
        <b>{{ item.label }}</b>
        <strong>{{ item.value }}</strong>
      </span>
    </footer>

    <section class="xt-today__below-fold">
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
    </section>

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
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { ArrowRight } from '@element-plus/icons-vue'
import dayjs from 'dayjs'

import DateSwitcher from '../../../components/manage/DateSwitcher.vue'
import KpiBar from '../../../components/manage/KpiBar.vue'
import WorkshopBarChart from '../../../components/manage/WorkshopBarChart.vue'
import CostLine from '../../../components/manage/CostLine.vue'
import OutputTrendLine from '../../../components/manage/OutputTrendLine.vue'
import FilerRoster from '../../../components/manage/FilerRoster.vue'
import IndustrialProcessIcon from '../../../components/manage/IndustrialProcessIcon.vue'
import MissingReportPanel from '../../../components/manage/MissingReportPanel.vue'
import { rosterStats, buildFilerRoster } from '../../../components/manage/_filerRoster.js'
import { useDashboardSnapshot } from '../../../composables/useDashboardSnapshot.js'
import { fetchTimeseries } from '../../../api/dashboard.js'
import { fetchLiveAggregation } from '../../../api/realtime.js'
import { fetchUsersPage } from '../../../api/users.js'
import { useAuthStore } from '../../../stores/auth.js'
import { isCompactClient } from '../../../router/guardRules.js'
import { buildTodayStitchSurface } from '../../../utils/stitchManageSurface.js'
import {
  buildFactActionSummary,
  buildFactClosureSurface,
  openFactTrace,
} from '../../../utils/manageDailyReportSurface.js'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const snapshot = useDashboardSnapshot()

function normalizeRouteDate(value) {
  const candidate = Array.isArray(value) ? value[0] : value
  if (typeof candidate !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(candidate)) return ''
  return dayjs(candidate).isValid() && dayjs(candidate).format('YYYY-MM-DD') === candidate
    ? candidate
    : ''
}

const initialTargetDate = normalizeRouteDate(route.query.target_date)
if (initialTargetDate && initialTargetDate !== snapshot.targetDate.value) {
  snapshot.targetDate.value = initialTargetDate
} else {
  snapshot.load()
}

const trendSeries = ref([])
const userList = ref([])
const rosterOpen = ref(false)
const liveAggregation = ref({})
const liveLoading = ref(false)
const liveLoadError = ref('')
const compactClient = ref(isCompactClient())

function syncCompactClient() {
  compactClient.value = isCompactClient()
}

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

async function loadLiveAggregation(targetDate) {
  liveLoading.value = true
  liveLoadError.value = ''
  try {
    liveAggregation.value = await fetchLiveAggregation({ business_date: targetDate })
  } catch (err) {
    liveAggregation.value = {}
    liveLoadError.value = err?.message || '实时聚合加载失败'
  } finally {
    liveLoading.value = false
  }
}

loadTrend(snapshot.targetDate.value)
loadUsers()
loadLiveAggregation(snapshot.targetDate.value)
watch(snapshot.targetDate, (next) => loadTrend(next))
watch(snapshot.targetDate, (next) => loadLiveAggregation(next))
watch(snapshot.targetDate, (next) => {
  if (normalizeRouteDate(route.query.target_date) === next) return
  void router.replace({
    path: route.path,
    query: { ...route.query, target_date: next },
    hash: route.hash,
  })
})
watch(() => route.query.target_date, (value) => {
  const next = normalizeRouteDate(value)
  if (next && next !== snapshot.targetDate.value) snapshot.targetDate.value = next
})

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

const stitchSurface = computed(() => buildTodayStitchSurface({
  snapshotData: snapshot.data.value,
  targetDate: snapshot.targetDate.value,
  liveAggregation: liveAggregation.value,
  runtimeState: {
    snapshotLoading: snapshot.loading.value,
    snapshotError: snapshot.lastError.value,
    liveLoading: liveLoading.value,
    liveError: liveLoadError.value,
  },
}))
const settlementCards = computed(() => stitchSurface.value.kpiStrip)
const comparisonCards = computed(() => stitchSurface.value.comparisonRail)
const workshopRows = computed(() => stitchSurface.value.workshopTable)
const wipRows = computed(() => stitchSurface.value.wipDistribution)
const wipTotalText = computed(() => {
  const total = wipRows.value.reduce((sum, row) => sum + (Number(row.totalWeight) || 0), 0)
  return `${fmt(total)} 吨`
})
const missingRows = computed(() => stitchSurface.value.missingReportRows)
const bottomStatusItems = computed(() => stitchSurface.value.bottomStatus)
const dailyOverview = computed(() => snapshot.data.value.daily_overview || {})
const factClosureSurface = computed(() => buildFactClosureSurface(dailyOverview.value.fact_closure))
const factActionSummary = computed(() => buildFactActionSummary(dailyOverview.value.fact_missing))
const factActionRoute = computed(() => (
  compactClient.value
    ? {
        path: '/manage/today',
        query: { ...route.query, target_date: snapshot.targetDate.value },
        hash: '#daily-report',
      }
    : {
        path: '/manage/alerts',
        query: { domain: 'reporting', target_date: snapshot.targetDate.value },
      }
))
const businessDateLabel = computed(() => {
  const d = dayjs(snapshot.targetDate.value)
  if (!d.isValid()) return snapshot.targetDate.value || '未选择'
  return `${d.month() + 1}月${d.date()}日生产经营数据`
})

const FACT_FIELD_LABELS = {
  total_output_daily: '全厂包装产量',
  finished_inbound_daily: '全厂入库产量',
  wip_total: '在制料总量',
  total_electricity_kwh: '全厂用电量',
  daily_yield_rate: '全厂成品率',
}

function factFieldLabel(field) {
  return FACT_FIELD_LABELS[field] || field
}

function factValueText(fact) {
  if (fact?.value === null || fact?.value === undefined || fact?.value === '') return '--'
  const number = Number(fact.value)
  return Number.isFinite(number) ? fmt(number) : '--'
}

function factStatusText(status) {
  return {
    confirmed: '已确认',
    missing: '缺失',
    mismatch: '冲突',
    needs_evidence: '待补证',
  }[status] || '待核验'
}

function openTrace(traceId) {
  return openFactTrace(router, traceId)
}

const kpiItems = computed(() => {
  return settlementCards.value.map((item) => ({
    ...item,
    spark: item.key === 'plant-output' && item.status === 'confirmed'
      ? outputTonsSpark.value
      : (item.key === 'energy-per-ton' ? energyPerTonSpark.value : null),
    sparkTone: item.key === 'energy-per-ton' ? 'warning' : 'primary',
  }))
})

const summaryText = computed(() => snapshot.leaderSummary.value.summary_text || '')
const highlightMetrics = computed(() => {
  const plantOutput = dailyOverview.value.plant_output || {}
  return [
    {
      key: 'feeding-month',
      label: '投料月累计',
      value: plantOutput.factory_feeding_month_to_date_input == null ? '—' : `${fmt(plantOutput.factory_feeding_month_to_date_input, 0)} 吨`,
      subText: 'MES投料',
      tone: plantOutput.factory_feeding_month_to_date_input == null ? 'muted' : 'primary',
    },
    {
      key: 'daily-output-month',
      label: '全厂包装月累计',
      value: plantOutput.monthly_output == null ? '—' : `${fmt(plantOutput.monthly_output, 0)} 吨`,
      subText: plantOutput.monthly_average_output == null ? '月均 —' : `月均 ${fmt(plantOutput.monthly_average_output, 1)} 吨`,
      tone: 'primary',
    },
    {
      key: 'finished-inbound-month',
      label: '全厂入库月累计',
      value: plantOutput.finished_inbound_monthly_output == null ? '—' : `${fmt(plantOutput.finished_inbound_monthly_output, 0)} 吨`,
      subText: plantOutput.finished_inbound_monthly_average == null ? '月均 —' : `月均 ${fmt(plantOutput.finished_inbound_monthly_average, 1)} 吨`,
      tone: plantOutput.finished_inbound_monthly_output == null ? 'muted' : 'success',
    },
    {
      key: 'yield-rate-month',
      label: '全厂成品率',
      value: plantOutput.monthly_yield_rate == null ? '—' : `${fmt(plantOutput.monthly_yield_rate, 2)}%`,
      subText: '投料入库',
      tone: plantOutput.monthly_yield_rate == null ? 'muted' : 'primary',
    },
  ]
})

function toFinite(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function sumField(rows, field) {
  return rows.reduce((sum, row) => sum + (toFinite(row?.[field]) || 0), 0)
}

function rowsByName(matchers) {
  return workshopRows.value.filter((row) => {
    const name = String(row.workshop || '')
    return matchers.some((matcher) => name.includes(matcher))
  })
}

function buildWorkshopStage(key, label, matchers) {
  const rows = rowsByName(matchers)
  const daily = rows.length ? sumField(rows, 'daily_output') : null
  const monthly = rows.length ? sumField(rows, 'monthly_output') : null
  return {
    key,
    label,
    primaryLabel: '日累计',
    primaryValue: daily == null ? '—' : `${fmt(daily, 0)} 吨`,
    secondaryLabel: '月累计',
    secondaryValue: monthly == null ? '—' : `${fmt(monthly, 0)} 吨`,
    subItems: rows.slice(0, 3).map((row) => ({
      label: row.workshop,
      value: row.dailyOutputText,
    })),
  }
}

const productionFlowStages = computed(() => {
  const plantOutput = dailyOverview.value.plant_output || {}
  return [
    buildWorkshopStage('casting', '铸锭', ['铸锭', '熔铸', '铸造']),
    buildWorkshopStage('cast-roll', '铸轧', ['铸轧']),
    buildWorkshopStage('hot-roll', '热轧', ['热轧']),
    buildWorkshopStage('cold-roll', '冷轧（轧机）', ['冷轧', '1650', '1850', '2050']),
    buildWorkshopStage('finish', '退火 / 拉矫 / 精整', ['退火', '拉矫', '精整', '剪切', '包装']),
    {
      key: 'warehouse',
      label: '包装 / 入库对照',
      primaryLabel: '全厂包装',
      primaryValue: plantOutput.daily_output == null ? '—' : `${fmt(plantOutput.daily_output, 0)} 吨`,
      secondaryLabel: '成品入库',
      secondaryValue: plantOutput.finished_inbound_output == null ? '—' : `${fmt(plantOutput.finished_inbound_output, 0)} 吨`,
      subItems: [
        {
          label: '投料月累计',
          value: plantOutput.factory_feeding_month_to_date_input == null ? '—' : `${fmt(plantOutput.factory_feeding_month_to_date_input, 0)} 吨`,
        },
        {
          label: '包装月累计',
          value: plantOutput.monthly_output == null ? '—' : `${fmt(plantOutput.monthly_output, 0)} 吨`,
        },
        {
          label: '入库月累计',
          value: plantOutput.finished_inbound_monthly_output == null ? '—' : `${fmt(plantOutput.finished_inbound_monthly_output, 0)} 吨`,
        },
      ],
    },
  ]
})

const shiftTiles = computed(() => {
  const raw = snapshot.yesterdayShiftBreakdown.value?.shifts || []
  const order = [
    { name: '长白班', timeRange: '07:30-15:30' },
    { name: '小夜班', timeRange: '15:30-23:30' },
    { name: '大夜班', timeRange: '23:30-07:30' },
  ]
  return order.map((slot, index) => {
    const shift = raw.find((item) => String(item.shift_name || item.name || '').includes(slot.name))
    const reported = shift?.reported_count ?? shift?.confirmed_count ?? shift?.submitted_count ?? null
    const expected = shift?.expected_count ?? shift?.total_count ?? shift?.required_count ?? null
    return {
      key: shift?.shift_id ?? slot.name ?? index,
      name: shift?.shift_name || shift?.name || slot.name,
      timeRange: shift?.time_range || shift?.timeRange || shift?.range || slot.timeRange,
      reported: expected ? `${reported ?? 0}/${expected}` : (reported == null ? '—' : `${reported}`),
    }
  })
})

const eventRailItems = computed(() => {
  const items = []
  const nowText = snapshot.lastRefreshAt.value
    ? dayjs(snapshot.lastRefreshAt.value).format('HH:mm')
    : '--:--'

  if (snapshot.lastError.value || liveLoadError.value) {
    items.push({
      key: 'load-error',
      label: '告警',
      title: '数据同步需核查',
      body: snapshot.lastError.value || liveLoadError.value,
      tone: 'danger',
      time: nowText,
    })
  }
  if (rosterCounts.value.unreported > 0) {
    items.push({
      key: 'reminder',
      label: '催报',
      title: `仍有 ${rosterCounts.value.unreported} 个车间未完成`,
      body: `已填 ${rosterCounts.value.reported}/${rosterCounts.value.total}，请优先确认缺报人员。`,
      tone: 'warning',
      time: nowText,
    })
  }
  if (missingRows.value.length) {
    items.push({
      key: 'missing',
      label: '异常',
      title: '存在缺报明细',
      body: `当前缺报队列 ${missingRows.value.length} 条，已在下方明细压缩展示。`,
      tone: 'danger',
      time: nowText,
    })
  }
  if (comparisonCards.value.length) {
    const energy = comparisonCards.value[0]
    items.push({
      key: 'energy-compare',
      label: '对照',
      title: energy.title || '算法与填报对照',
      body: `${energy.primaryLabel} ${energy.primaryValue}，${energy.compareLabel} ${energy.compareValue}`,
      tone: energy.tone || 'primary',
      time: nowText,
    })
  }
  const me = snapshot.managementEstimate.value
  const marginText = me.estimate_ready && me.estimated_margin != null
    ? `${fmt(Number(me.estimated_margin) / 10000, 1)} 万元`
    : '估算未就绪'
  if (me.estimate_ready && me.estimated_margin != null) {
    items.push({
      key: 'margin-estimate',
      label: '核算',
      title: '估算毛利',
      body: marginText,
      tone: 'success',
      time: nowText,
    })
  }
  if (summaryText.value) {
    items.push({
      key: 'ai-summary',
      label: 'AI 摘要',
      title: '日报摘要',
      body: summaryText.value,
      tone: 'primary',
      time: nowText,
    })
  }
  if (!items.length) {
    items.push({
      key: 'ok',
      label: '正常',
      title: '暂无阻塞项',
      body: '当前日报、填报和看板链路未发现前端阻塞。',
      tone: 'success',
      time: nowText,
    })
  }
  return items.slice(0, 5)
})
const quickLinks = computed(() => {
  const links = [
    { label: '实时', path: '/manage/live' },
    { label: '日报', path: '/manage/today?section=daily-report' },
  ]
  if (compactClient.value) return links
  links.push(
    { label: '生产', path: '/manage/production' },
    { label: '填报明细', path: '/manage/fill-details' },
    { label: '异常', path: '/manage/alerts' },
    { label: '能耗', path: '/manage/energy' },
  )
  if (auth.adminSurface) {
    links.push(
      { label: '主数据', path: '/manage/master' },
      { label: '用户', path: '/manage/admin/users' },
      { label: '规则', path: '/manage/admin/rules' },
      { label: '设置', path: '/manage/admin/settings' },
    )
  }
  return links
})

onMounted(() => {
  syncCompactClient()
  window.addEventListener('resize', syncCompactClient, { passive: true })
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', syncCompactClient)
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
  box-shadow: 0 12px 28px color-mix(in srgb, var(--xt-bg-ink) 56%, transparent);
  overflow: hidden;
}

.xt-today__header::before {
  content: '';
  position: absolute;
  top: 0;
  right: var(--xt-space-4);
  left: var(--xt-space-4);
  height: 1px;
  pointer-events: none;
  background: linear-gradient(90deg, transparent, color-mix(in srgb, var(--xt-primary) 22%, transparent), transparent);
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
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--xt-primary) 22%, transparent);
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
  box-shadow: 0 12px 28px color-mix(in srgb, var(--xt-bg-ink) 52%, transparent);
  overflow: hidden;
}

.xt-today__daily::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    linear-gradient(color-mix(in srgb, var(--xt-text-inverse) 4%, transparent) 50%, transparent 50%);
  background-size: auto, 100% 4px;
  opacity: 0.32;
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

.xt-today__bottom-status {
  display: flex;
  align-items: center;
  gap: var(--xt-space-2);
  flex-wrap: wrap;
  padding: var(--xt-space-3);
  border: 1px solid color-mix(in srgb, var(--xt-primary) 18%, var(--xt-border-ink));
  border-radius: var(--xt-radius-xl);
  background:
    linear-gradient(90deg, color-mix(in srgb, var(--xt-primary) 10%, transparent), transparent 42%),
    color-mix(in srgb, var(--xt-bg-ink-panel) 82%, transparent);
  box-shadow: inset 0 1px 0 color-mix(in srgb, var(--xt-text-inverse) 7%, transparent);
}

.xt-today__status-pill {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 32px;
  padding: 6px 11px;
  border: 1px solid color-mix(in srgb, var(--xt-primary) 16%, var(--xt-border-ink));
  border-radius: var(--xt-radius-pill);
  background: color-mix(in srgb, var(--xt-bg-ink) 64%, transparent);
  color: color-mix(in srgb, var(--xt-text-inverse) 68%, transparent);
  font-size: var(--xt-text-xs);
  font-weight: 850;
}

.xt-today__status-pill i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: color-mix(in srgb, var(--xt-text-inverse) 48%, transparent);
}

.xt-today__status-pill b {
  color: color-mix(in srgb, var(--xt-text-inverse) 58%, transparent);
  font-weight: 850;
}

.xt-today__status-pill strong {
  color: var(--xt-text-inverse);
  font-family: var(--xt-font-number);
  font-weight: 900;
  font-variant-numeric: tabular-nums;
}

.xt-today__status-pill.tone-success i {
  background: var(--xt-success);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--xt-success) 18%, transparent);
}

.xt-today__status-pill.tone-warning i {
  background: var(--xt-warning);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--xt-warning) 18%, transparent);
}

.xt-today__status-pill.tone-danger i {
  background: var(--xt-danger);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--xt-danger) 18%, transparent);
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
  .xt-today__quick-link,
  .xt-today__filer-badge,
  .xt-today__table tbody tr {
    transition: none;
  }
}

.xt-today {
  gap: 8px;
  padding: 10px 14px 14px;
  background:
    radial-gradient(circle at 24% 0%, color-mix(in srgb, var(--xt-primary) 18%, transparent), transparent 28%),
    radial-gradient(circle at 76% 8%, color-mix(in srgb, var(--xt-info) 12%, transparent), transparent 30%),
    linear-gradient(180deg, #03111d 0%, #061d2e 48%, #041423 100%);
}

.xt-today__topbar {
  display: grid;
  grid-template-columns: minmax(220px, 0.7fr) minmax(340px, 1.45fr) auto;
  align-items: center;
  gap: 10px;
  min-height: 48px;
  padding: 7px 12px;
  border: 1px solid rgba(52, 143, 224, 0.28);
  border-radius: 12px;
  background:
    linear-gradient(90deg, rgba(9, 41, 67, 0.96), rgba(5, 26, 45, 0.9)),
    rgba(5, 22, 38, 0.96);
  box-shadow: inset 0 1px 0 rgba(157, 211, 255, 0.08), 0 12px 28px rgba(0, 8, 16, 0.34);
}

.xt-today__identity {
  display: flex;
  align-items: baseline;
  gap: 12px;
  min-width: 0;
}

.xt-today__identity span {
  display: none;
  color: rgba(121, 194, 255, 0.78);
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.16em;
}

.xt-today__identity h1 {
  margin: 0;
  color: #f3f8ff;
  font-family: var(--xt-font-display);
  font-size: clamp(20px, 1.8vw, 26px);
  font-weight: 950;
  letter-spacing: -0.04em;
}

.xt-today__identity p {
  margin: 0;
  color: rgba(226, 240, 255, 0.58);
  font-size: 12px;
  font-weight: 760;
}

.xt-today__top-actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  min-width: 0;
}

.xt-today__quick-nav {
  justify-content: center;
  min-width: 0;
  padding: 6px;
  border-color: rgba(48, 137, 218, 0.22);
  border-radius: 12px;
  background: rgba(2, 19, 34, 0.68);
}

.xt-today__quick-link {
  padding: 7px 10px;
  border-color: rgba(68, 154, 231, 0.22);
  border-radius: 999px;
  background: rgba(6, 28, 48, 0.78);
  color: rgba(225, 241, 255, 0.64);
  font-size: 12px;
}

.xt-today__quick-link:hover,
.xt-today__quick-link.router-link-active {
  border-color: rgba(55, 151, 243, 0.72);
  background: rgba(18, 93, 153, 0.32);
}

.xt-today__filer-badge {
  min-height: 34px;
  white-space: nowrap;
}

.xt-today__command-wall {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(280px, 310px);
  gap: 10px;
  min-height: 630px;
  min-width: 0;
}

.xt-today__command-main {
  display: grid;
  gap: 10px;
  min-width: 0;
}

.xt-today__panel,
.xt-today__event-rail,
.xt-today__bottom-status {
  border: 1px solid rgba(70, 157, 238, 0.24);
  border-radius: 12px;
  background:
    linear-gradient(180deg, rgba(18, 57, 88, 0.66), rgba(5, 24, 42, 0.92)),
    rgba(4, 21, 37, 0.94);
  box-shadow: inset 0 1px 0 rgba(189, 225, 255, 0.08), 0 10px 24px rgba(0, 8, 16, 0.28);
}

.xt-today__panel {
  gap: 10px;
  padding: 12px;
}

.xt-today__panel-head {
  align-items: center;
  min-height: 24px;
}

.xt-today__panel-head h2,
.xt-today__rail-head h2 {
  margin: 0;
  color: #f3f8ff;
  font-family: var(--xt-font-display);
  font-size: 15px;
  font-weight: 930;
  letter-spacing: -0.015em;
}

.xt-today__panel-head h3 {
  margin: 0;
  color: #f3f8ff;
  font-size: 13px;
  font-weight: 900;
}

.xt-today__panel-head span,
.xt-today__rail-head span {
  color: rgba(225, 241, 255, 0.54);
  font-size: 11px;
  font-weight: 780;
}

.xt-today__flow {
  min-height: 198px;
}

.xt-today__flow-steps {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 8px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.xt-today__flow-step {
  position: relative;
  display: grid;
  align-content: start;
  gap: 5px;
  min-width: 0;
  min-height: 148px;
  padding: 8px;
  border: 1px solid rgba(70, 157, 238, 0.22);
  border-radius: 10px;
  background:
    linear-gradient(160deg, rgba(17, 73, 116, 0.52), rgba(4, 20, 35, 0.9)),
    rgba(4, 20, 35, 0.88);
  overflow: hidden;
}

.xt-today__flow-step:not(:last-child)::after {
  content: '→';
  position: absolute;
  top: 35px;
  right: -13px;
  z-index: 3;
  color: rgba(36, 149, 255, 0.9);
  font-size: 24px;
  font-weight: 900;
}

.xt-today__flow-icon {
  position: relative;
  display: grid;
  place-items: center;
  width: 108px;
  height: 70px;
  margin: -2px auto 2px;
  border: 0;
  border-radius: 0;
  background:
    radial-gradient(ellipse at 50% 92%, rgba(35, 151, 255, 0.24), transparent 62%);
  box-shadow: none;
}

.xt-today__flow-title {
  color: rgba(244, 249, 255, 0.92);
  font-size: 12px;
  font-weight: 900;
  text-align: center;
  white-space: nowrap;
}

.xt-today__flow-metric {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 6px;
  color: rgba(225, 241, 255, 0.58);
  font-size: 11px;
  font-weight: 760;
}

.xt-today__flow-metric b {
  color: #f7fbff;
  font-family: var(--xt-font-number);
  font-size: 13px;
  font-weight: 930;
  font-variant-numeric: tabular-nums;
}

.xt-today__flow-metric.is-muted b {
  color: rgba(216, 234, 255, 0.7);
}

.xt-today__flow-sub {
  display: grid;
  gap: 3px;
  margin: 1px 0 0;
  padding: 0;
  list-style: none;
}

.xt-today__flow-sub li {
  display: flex;
  justify-content: space-between;
  gap: 5px;
  color: rgba(216, 234, 255, 0.55);
  font-size: 10px;
  font-weight: 760;
}

.xt-today__flow-sub b {
  color: rgba(244, 249, 255, 0.82);
  font-family: var(--xt-font-number);
  font-weight: 900;
}

.xt-today__lower-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(0, 1.2fr);
  gap: 10px;
}

.xt-today__workshop,
.xt-today__wip {
  min-height: 190px;
}

.xt-today__table {
  font-size: 12px;
}

.xt-today__table th,
.xt-today__table td {
  padding: 6px 8px;
  border-color: rgba(74, 159, 235, 0.16);
}

.xt-today__table th {
  background: rgba(24, 78, 120, 0.32);
  color: rgba(224, 240, 255, 0.58);
}

.xt-today__table tbody tr:nth-child(even) {
  background: rgba(255, 255, 255, 0.02);
}

.xt-today__wip-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.xt-today__wip-card {
  min-height: 58px;
  padding: 9px;
  border-color: rgba(58, 164, 221, 0.22);
  background:
    radial-gradient(circle at 100% 100%, rgba(20, 183, 191, 0.16), transparent 58%),
    rgba(3, 24, 42, 0.78);
}

.xt-today__wip-card span {
  color: rgba(224, 240, 255, 0.64);
}

.xt-today__wip-card b {
  color: #9bd8ff;
  font-size: 18px;
}

.xt-today__metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.xt-today__compare-card {
  min-height: 76px;
  padding: 10px;
  border: 1px solid rgba(68, 154, 231, 0.22);
  border-radius: 10px;
  background:
    radial-gradient(circle at 92% 80%, rgba(38, 141, 255, 0.2), transparent 52%),
    rgba(4, 22, 38, 0.88);
}

.xt-today__compare-card span {
  color: rgba(224, 240, 255, 0.62);
  font-size: 12px;
  font-weight: 850;
}

.xt-today__compare-card strong {
  display: block;
  margin-top: 5px;
  color: #f7fbff;
  font-family: var(--xt-font-number);
  font-size: 20px;
  font-weight: 950;
  font-variant-numeric: tabular-nums;
}

.xt-today__compare-card small {
  display: block;
  margin-top: 3px;
  color: rgba(224, 240, 255, 0.52);
  font-size: 11px;
  font-weight: 760;
}

.xt-today__compare-card.tone-warning {
  border-color: rgba(236, 166, 55, 0.42);
}

.xt-today__compare-card.tone-success {
  border-color: rgba(61, 220, 132, 0.34);
}

.xt-today__event-rail {
  display: grid;
  align-content: start;
  gap: 10px;
  min-width: 0;
  padding: 12px;
}

.xt-today__rail-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.xt-today__shift-card {
  display: grid;
  gap: 8px;
  padding: 10px;
  border: 1px solid rgba(70, 157, 238, 0.2);
  border-radius: 10px;
  background: rgba(3, 22, 39, 0.78);
}

.xt-today__shift-list {
  display: grid;
  gap: 6px;
}

.xt-today__shift-row {
  display: grid;
  grid-template-columns: minmax(54px, 0.9fr) auto;
  gap: 4px 8px;
  align-items: baseline;
  padding: 7px 8px;
  border: 1px solid rgba(70, 157, 238, 0.14);
  border-radius: 8px;
  background: rgba(8, 35, 57, 0.74);
}

.xt-today__shift-row span {
  color: rgba(244, 249, 255, 0.86);
  font-size: 12px;
  font-weight: 900;
}

.xt-today__shift-row b {
  color: #65c7ff;
  font-family: var(--xt-font-number);
  font-size: 13px;
  font-weight: 930;
}

.xt-today__shift-row small {
  grid-column: 1 / -1;
  color: rgba(224, 240, 255, 0.48);
  font-size: 10px;
  font-weight: 760;
}

.xt-today__event-card {
  display: grid;
  gap: 7px;
  padding: 11px;
  border: 1px solid rgba(70, 157, 238, 0.18);
  border-radius: 10px;
  background: rgba(5, 24, 42, 0.86);
}

.xt-today__event-card.tone-danger {
  border-color: rgba(255, 91, 91, 0.42);
}

.xt-today__event-card.tone-warning {
  border-color: rgba(236, 166, 55, 0.44);
}

.xt-today__event-card.tone-success {
  border-color: rgba(61, 220, 132, 0.34);
}

.xt-today__event-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.xt-today__event-top span {
  color: #69c8ff;
  font-size: 12px;
  font-weight: 920;
}

.xt-today__event-top time {
  color: rgba(224, 240, 255, 0.48);
  font-family: var(--xt-font-number);
  font-size: 11px;
}

.xt-today__event-card strong {
  color: rgba(244, 249, 255, 0.9);
  font-size: 13px;
  font-weight: 900;
}

.xt-today__event-card p {
  display: -webkit-box;
  margin: 0;
  overflow: hidden;
  color: rgba(224, 240, 255, 0.62);
  font-size: 12px;
  font-weight: 720;
  line-height: 1.55;
  -webkit-box-orient: vertical;
  -webkit-line-clamp: 2;
}

.xt-today__event-rail :deep(.xt-missing-report) {
  min-height: 0;
  padding: 10px;
  border-radius: 10px;
  background: rgba(5, 24, 42, 0.86);
}

.xt-today__event-rail :deep(.xt-missing-report__body) {
  max-height: 112px;
  overflow: auto;
}

.xt-today__bottom-status {
  justify-content: space-between;
  min-height: 44px;
  padding: 8px 12px;
  border-radius: 10px;
  background:
    linear-gradient(90deg, rgba(17, 80, 127, 0.5), rgba(4, 22, 38, 0.94)),
    rgba(4, 22, 38, 0.94);
}

.xt-today__status-pill {
  flex: 1 1 170px;
  justify-content: center;
  min-height: 28px;
  padding: 5px 10px;
  background: rgba(3, 17, 30, 0.52);
}

.xt-today__below-fold {
  display: grid;
  gap: 10px;
  margin-top: 58px;
}

.xt-today__fact-strip {
  display: grid;
  grid-template-columns: repeat(5, minmax(168px, 1fr));
  overflow-x: auto;
  border-top: 1px solid rgba(70, 157, 238, 0.28);
  border-bottom: 1px solid rgba(70, 157, 238, 0.28);
  background: rgba(3, 17, 29, 0.72);
}

.xt-today__fact-actions {
  display: grid;
  grid-template-columns: minmax(120px, 1.25fr) repeat(4, minmax(92px, 1fr)) 36px;
  align-items: stretch;
  border-bottom: 1px solid rgba(70, 157, 238, 0.28);
  background: rgba(4, 24, 40, 0.9);
}

.xt-today__fact-actions > div {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  min-width: 0;
  min-height: 38px;
  padding: 7px 10px;
  border-right: 1px solid rgba(70, 157, 238, 0.16);
}

.xt-today__fact-actions span {
  overflow: hidden;
  color: rgba(225, 240, 255, 0.58);
  font-size: 11px;
  font-weight: 760;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.xt-today__fact-actions strong {
  color: #ffd27a;
  font-family: var(--xt-font-number);
  font-size: 15px;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
}

.xt-today__fact-action-lead strong {
  color: #ff9d8c;
}

.xt-today__fact-action-link {
  display: grid;
  place-items: center;
  min-width: 36px;
  color: #8acbff;
  text-decoration: none;
}

.xt-today__fact-action-link:hover,
.xt-today__fact-action-link:focus-visible {
  background: rgba(45, 143, 225, 0.16);
  color: #d9efff;
}

.xt-today__fact-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 4px 8px;
  min-width: 0;
  padding: 9px 11px;
  border: 0;
  border-right: 1px solid rgba(70, 157, 238, 0.18);
  color: rgba(225, 240, 255, 0.76);
  text-align: left;
  background: transparent;
  cursor: pointer;
}

.xt-today__fact-item:last-child {
  border-right: 0;
}

.xt-today__fact-item:focus-visible {
  outline: 2px solid rgba(71, 171, 255, 0.92);
  outline-offset: -2px;
}

.xt-today__fact-item:disabled {
  cursor: default;
}

.xt-today__fact-label,
.xt-today__fact-source,
.xt-today__fact-window {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.xt-today__fact-label {
  color: rgba(225, 240, 255, 0.68);
  font-size: 11px;
  font-weight: 760;
}

.xt-today__fact-item strong {
  grid-column: 1;
  color: #f3f9ff;
  font-family: var(--xt-font-number);
  font-size: 19px;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
}

.xt-today__fact-item strong small {
  margin-left: 4px;
  color: rgba(225, 240, 255, 0.52);
  font-size: 10px;
}

.xt-today__fact-status {
  grid-column: 2;
  grid-row: 1 / span 2;
  align-self: center;
  color: #8acbff;
  font-size: 10px;
  font-weight: 850;
}

.xt-today__fact-item.is-confirmed .xt-today__fact-status {
  color: #7ce0a0;
}

.xt-today__fact-item.is-missing .xt-today__fact-status,
.xt-today__fact-item.is-mismatch .xt-today__fact-status {
  color: #ff9d8c;
}

.xt-today__fact-item.is-needs_evidence .xt-today__fact-status {
  color: #ffd27a;
}

.xt-today__fact-source,
.xt-today__fact-window {
  grid-column: 1 / -1;
  font-size: 10px;
  line-height: 1.35;
}

.xt-today__fact-source {
  color: rgba(144, 204, 250, 0.72);
}

.xt-today__fact-window {
  color: rgba(225, 240, 255, 0.42);
  font-variant-numeric: tabular-nums;
}

@media (max-width: 1360px) {
  .xt-today__command-wall {
    grid-template-columns: 1fr;
  }

  .xt-today__event-rail {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .xt-today__rail-head,
  .xt-today__event-rail :deep(.xt-missing-report) {
    grid-column: 1 / -1;
  }
}

@media (max-width: 1120px) {
  .xt-today__topbar,
  .xt-today__lower-grid,
  .xt-today__metric-grid {
    grid-template-columns: 1fr;
  }

  .xt-today__flow-steps {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .xt-today {
    padding: 8px;
  }

  .xt-today__top-actions,
  .xt-today__quick-nav {
    justify-content: flex-start;
  }

  .xt-today__flow-steps,
  .xt-today__event-rail {
    grid-template-columns: 1fr;
  }

  .xt-today__flow-step:not(:last-child)::after {
    display: none;
  }

  .xt-today__fact-actions {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .xt-today__fact-action-link {
    grid-column: 1 / -1;
    min-height: 34px;
  }
}
</style>
