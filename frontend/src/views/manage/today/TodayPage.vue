<template>
  <section
    class="xt-today"
    data-testid="manage-today"
    data-visual-pass="light-workspace"
    :data-stitch-project-id="stitchSurface.stitch.projectId"
    :data-stitch-screen-id="stitchSurface.stitch.screenId"
  >
    <header class="xt-today__topbar">
      <div class="xt-today__identity">
        <h1>经营总览</h1>
        <p>{{ businessDateLabel }}</p>
      </div>

      <div class="xt-today__top-actions">
        <button
          v-if="reportingStatus.length"
          type="button"
          class="xt-today__filer-badge"
          :class="`tone-${rosterTone}`"
          @click="rosterOpen = !rosterOpen"
          :aria-expanded="rosterOpen"
        >
          填报 <b>{{ rosterCounts.reported }}</b>/{{ rosterCounts.total }} 车间
          <span v-if="rosterCounts.unreported > 0" class="xt-today__filer-pending">未报 {{ rosterCounts.unreported }}</span>
        </button>
        <DateSwitcher
          :model-value="snapshot.targetDate.value"
          :loading="snapshot.loading.value"
          :freshness="snapshot.freshnessStatus.value"
          @step="snapshot.stepDate"
          @refresh="refreshAll"
          @pick="onDatePick"
        />
      </div>
    </header>

    <section
      v-if="factActionSummary.openCount"
      class="xt-today__fact-actions"
      data-testid="today-fact-actions"
      aria-label="事实行动摘要"
    >
      <strong>还缺 {{ factActionSummary.openCount }} 项事实，日报暂不发送</strong>
      <span>人工补录 {{ factActionSummary.actionableCount }}</span>
      <span>来源复查 {{ factActionSummary.sourceRecheckCount }}</span>
      <span>依赖补齐 {{ factActionSummary.dependencyCount }}</span>
      <span>入口已发送 {{ factActionSummary.notifiedCount }}</span>
      <RouterLink
        class="xt-today__fact-action-link"
        :to="factActionRoute"
        :aria-label="compactClient ? '查看日报事实' : '打开事实待办'"
      >
        查看 <el-icon><ArrowRight /></el-icon>
      </RouterLink>
    </section>

    <div :aria-busy="snapshot.pending.value.daily" class="xt-today__kpis">
      <ul class="xt-today__kpi-grid" data-testid="manage-kpi-bar">
        <li v-for="item in kpiItems" :key="item.key" :class="{ 'is-hero': item.hero }">
          <XtMetric
            :label="item.label"
            :value="item.value"
            :unit="item.unit"
            :state="item.state"
            :sub="item.sub"
            :size="item.hero ? 'lg' : 'md'"
          />
        </li>
      </ul>
      <span v-if="snapshot.pending.value.daily" class="xt-today__loading" role="status">正在读取日报</span>
    </div>

    <details class="xt-today__sources">
      <summary>事实来源与业务时间 <span>{{ factClosureSurface.criticalFields.length }} 项关键事实</span></summary>
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
        <span class="xt-today__fact-source">{{ factSourceLabel(fact.source) }}</span>
        <span class="xt-today__fact-window">{{ fact.businessWindow || '--' }}</span>
      </button>
    </section>
    </details>

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
                <small>{{ row.detailText }}</small>
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
            <strong>{{ item.value ?? item.primaryValue }}</strong>
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
          <h2>异常与待办</h2>
          <RouterLink class="xt-today__quick-link" to="/manage/alerts">全部异常</RouterLink>
        </header>

        <RouterLink class="xt-today__live-link" to="/manage/live">
          <span><strong>当天生产动态</strong><small>{{ currentBusinessDate }} · 生产业务日</small></span>
          <el-icon><ArrowRight /></el-icon>
        </RouterLink>

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

    <section ref="chartsRoot" class="xt-today__below-fold" aria-label="历史趋势">
      <template v-if="chartsVisible">
      <div class="xt-today__row">
        <OutputTrendLine :series="trendSeries" :days="14" class="xt-today__row-trend" />
        <CostLine
          :estimate="snapshot.managementEstimate.value"
          :series="trendSeries"
          :days="14"
          :cost-label="`${snapshot.targetDate.value} 估算成本`"
          class="xt-today__row-cost"
        />
      </div>

      <WorkshopBarChart :rows="snapshot.productionLane.value" :target-date="snapshot.targetDate.value" />
      </template>
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
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { ArrowRight } from '@element-plus/icons-vue'
import dayjs from 'dayjs'

import DateSwitcher from '../../../components/manage/DateSwitcher.vue'
import XtMetric from '../../../components/xt/XtMetric.vue'
const WorkshopBarChart = defineAsyncComponent(() => import('../../../components/manage/WorkshopBarChart.vue'))
const CostLine = defineAsyncComponent(() => import('../../../components/manage/CostLine.vue'))
const OutputTrendLine = defineAsyncComponent(() => import('../../../components/manage/OutputTrendLine.vue'))
const FilerRoster = defineAsyncComponent(() => import('../../../components/manage/FilerRoster.vue'))
import MissingReportPanel from '../../../components/manage/MissingReportPanel.vue'
import { rosterStats, buildFilerRoster } from '../../../components/manage/_filerRoster.js'
import { useDashboardSnapshot } from '../../../composables/useDashboardSnapshot.js'
import { inferBusinessDate } from '../../../utils/shiftClock.js'
import { fetchTimeseries } from '../../../api/dashboard.js'
import { fetchLiveAggregation } from '../../../api/realtime.js'
import { fetchUsersPage } from '../../../api/users.js'
import { isCompactClient } from '../../../router/guardRules.js'
import { buildTodayStitchSurface } from '../../../utils/stitchManageSurface.js'
import {
  buildFactActionSummary,
  buildFactClosureSurface,
  factSourceLabel,
  MISSING_DAILY_VALUE,
  openFactTrace,
  sumWipWeight,
} from '../../../utils/manageDailyReportSurface.js'

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
const currentBusinessDate = ref(inferBusinessDate())
const chartsRoot = ref(null)
const chartsVisible = ref(false)
let chartObserver
let trendRequest = 0
let liveRequest = 0
let usersLoaded = false
let dailyRefreshTimer
let liveDate = ''

function syncCompactClient() {
  compactClient.value = isCompactClient()
}

async function loadTrend(targetDate) {
  const request = ++trendRequest
  trendSeries.value = []
  try {
    const data = await fetchTimeseries({ target_date: targetDate, days: 14 })
    if (request !== trendRequest) return
    trendSeries.value = Array.isArray(data) ? data : []
  } catch (_e) {
    if (request === trendRequest) trendSeries.value = []
  }
}

async function loadUsers() {
  if (usersLoaded) return
  usersLoaded = true
  try {
    const page = await fetchUsersPage({ limit: 300 })
    userList.value = page.items || []
  } catch (_e) {
    userList.value = []
    usersLoaded = false
  }
}

async function loadLiveAggregation(targetDate) {
  const request = ++liveRequest
  liveLoading.value = true
  liveLoadError.value = ''
  liveAggregation.value = {}
  try {
    const data = await fetchLiveAggregation({ business_date: targetDate })
    if (request !== liveRequest) return
    liveAggregation.value = data
  } catch (err) {
    if (request !== liveRequest) return
    liveAggregation.value = {}
    liveLoadError.value = err?.message || '实时聚合加载失败'
  } finally {
    if (request === liveRequest) liveLoading.value = false
  }
}

watch([snapshot.targetDate, () => snapshot.pending.value.daily], ([next, pending]) => {
  if (pending || liveDate === next) return
  liveDate = next
  void loadLiveAggregation(next)
}, { immediate: true })
watch(rosterOpen, (open) => { if (open) void loadUsers() })
watch(snapshot.targetDate, (next) => {
  if (chartsVisible.value) void loadTrend(next)
  liveRequest++
  liveAggregation.value = {}
  liveLoadError.value = ''
  liveDate = ''
}, { flush: 'sync' })

function refreshAll() {
  currentBusinessDate.value = inferBusinessDate()
  liveDate = ''
  void snapshot.load()
  if (chartsVisible.value) void loadTrend(snapshot.targetDate.value)
}
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
  const total = sumWipWeight(wipRows.value)
  return total === null ? MISSING_DAILY_VALUE : `${fmt(total)} 吨`
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

const KPI_ORDER = ['plant-output', 'finished-inbound', 'yield-rate', 'feeding-input', 'contract-tonnage', 'energy-per-ton', 'process-throughput']
const KPI_HERO_KEYS = new Set(['plant-output', 'finished-inbound', 'yield-rate'])
const KPI_EMPTY_VALUES = new Set(['', '--', '—', MISSING_DAILY_VALUE])
const KPI_STATES = { confirmed: 'confirmed', needs_evidence: 'candidate', mismatch: 'conflict' }

const kpiItems = computed(() => {
  const rank = (item) => {
    const index = KPI_ORDER.indexOf(item.key)
    return index === -1 ? KPI_ORDER.length : index
  }
  return [...settlementCards.value].sort((a, b) => rank(a) - rank(b)).map((item) => {
    const value = KPI_EMPTY_VALUES.has(String(item.value ?? '')) ? null : item.value
    return {
      key: item.key,
      label: item.label,
      value,
      unit: value === null ? '' : item.unit,
      state: KPI_STATES[item.status] || '',
      sub: value === null ? '' : (item.deltaText || item.hint || item.sourceLabel || ''),
      hero: KPI_HERO_KEYS.has(item.key),
    }
  })
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

function sumKnownField(rows, field) {
  const values = rows.map((row) => (row?.[field] == null ? null : toFinite(row[field]))).filter((value) => value !== null)
  return values.length ? values.reduce((sum, value) => sum + value, 0) : null
}

function rowsByName(matchers) {
  return workshopRows.value.filter((row) => {
    const name = String(row.workshop || '')
    return matchers.some((matcher) => name.includes(matcher))
  })
}

function buildWorkshopStage(key, label, matchers) {
  const rows = rowsByName(matchers)
  const daily = sumKnownField(rows, 'daily_output')
  const monthly = sumKnownField(rows, 'monthly_output')
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
      label: snapshot.loading.value ? '读取中' : '待核验',
      title: snapshot.loading.value ? '正在读取经营数据' : '暂无可用待办',
      body: '',
      tone: 'muted',
      time: nowText,
    })
  }
  return items.slice(0, 5)
})

onMounted(() => {
  syncCompactClient()
  dailyRefreshTimer = window.setInterval(() => {
    if (document.visibilityState === 'visible') void snapshot.refreshDaily()
  }, 30000)
  const showCharts = () => {
    chartsVisible.value = true
    void loadTrend(snapshot.targetDate.value)
    chartObserver?.disconnect()
  }
  if (typeof IntersectionObserver === 'undefined') showCharts()
  else {
    chartObserver = new IntersectionObserver((entries) => {
      if (entries.some((entry) => entry.isIntersecting)) showCharts()
    }, { rootMargin: '120px' })
    if (chartsRoot.value) chartObserver.observe(chartsRoot.value)
  }
  window.addEventListener('resize', syncCompactClient, { passive: true })
})
onBeforeUnmount(() => {
  window.clearInterval(dailyRefreshTimer)
  chartObserver?.disconnect()
  trendRequest++
  liveRequest++
  window.removeEventListener('resize', syncCompactClient)
})
</script>

<style scoped>
.xt-today {
  display: flex;
  flex-direction: column;
  gap: 40px;
  min-width: 0;
  color: var(--xt-text);
  font-size: 14px;
}
.xt-today__topbar { display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 16px 32px; }
.xt-today__identity h1 { margin: 0; font-size: 28px; font-weight: 600; line-height: 1.25; }
.xt-today__identity p { margin: 4px 0 0; color: var(--xt-text-muted); font-size: 14px; }
.xt-today__top-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 16px; }
.xt-today__filer-badge { padding: 8px 0; border: 0; background: transparent; color: var(--xt-text-secondary); font: inherit; font-size: 14px; cursor: pointer; }
.xt-today__filer-badge b { color: var(--xt-text); font-weight: 600; font-variant-numeric: tabular-nums; }
.xt-today__filer-pending { margin-left: 8px; color: var(--xt-warning); }

.xt-today__fact-actions { display: flex; flex-wrap: wrap; align-items: baseline; gap: 8px 24px; margin-top: -16px; padding: 16px 0; border-block: 1px solid var(--xt-border); color: var(--xt-text-secondary); font-variant-numeric: tabular-nums; }
.xt-today__fact-actions strong { color: var(--xt-text); font-size: 16px; font-weight: 600; }
.xt-today__fact-action-link { display: inline-flex; align-items: center; gap: 4px; margin-left: auto; color: var(--xt-primary); text-decoration: none; }

.xt-today__kpis { position: relative; }
.xt-today__loading { display: block; margin-top: 8px; color: var(--xt-text-muted); font-size: 12px; }
.xt-today__kpi-grid { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 40px 32px; margin: 0; padding: 0; list-style: none; }
.xt-today__kpi-grid > li { grid-column: span 3; min-width: 0; }
.xt-today__kpi-grid > li.is-hero { grid-column: span 4; }

.xt-today__sources { padding-top: 16px; border-top: 1px solid var(--xt-border); }
.xt-today__sources summary { color: var(--xt-text-secondary); cursor: pointer; }
.xt-today__sources summary span { margin-left: 12px; color: var(--xt-text-muted); font-size: 12px; }
.xt-today__fact-strip { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 24px; padding-top: 16px; }
.xt-today__fact-item { display: flex; flex-direction: column; gap: 4px; min-width: 0; padding: 0; border: 0; background: transparent; color: var(--xt-text-muted); font: inherit; font-size: 12px; text-align: left; overflow-wrap: anywhere; cursor: pointer; }
.xt-today__fact-item:disabled { cursor: default; }
.xt-today__fact-label { color: var(--xt-text-secondary); font-size: 14px; }
.xt-today__fact-item strong { color: var(--xt-text); font-size: 20px; font-weight: 600; font-variant-numeric: tabular-nums; }
.xt-today__fact-item small { font-size: 12px; font-weight: 400; }
.xt-today__fact-item.is-confirmed .xt-today__fact-status { color: var(--xt-success); }
.xt-today__fact-item.is-needs_evidence .xt-today__fact-status { color: var(--xt-primary); }
.xt-today__fact-item.is-mismatch .xt-today__fact-status { color: var(--xt-warning); }

.xt-today__command-wall { display: grid; grid-template-columns: minmax(0, 1fr) 300px; gap: 56px; align-items: start; }
.xt-today__command-main { display: flex; flex-direction: column; gap: 40px; min-width: 0; }
.xt-today__lower-grid { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr); gap: 40px; }
.xt-today__panel { min-width: 0; }
.xt-today__panel-head, .xt-today__rail-head { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 8px; margin-bottom: 16px; }
.xt-today__panel-head h2, .xt-today__rail-head h2 { margin: 0; font-size: 16px; font-weight: 600; }
.xt-today__panel-head h3 { margin: 0; font-size: 14px; font-weight: 600; }
.xt-today__panel-head > span { color: var(--xt-text-muted); font-size: 12px; }
.xt-today__quick-link { color: var(--xt-primary); font-size: 14px; text-decoration: none; }

.xt-today__table { width: 100%; border-collapse: collapse; }
.xt-today__table th { padding: 8px 0; border-bottom: 1px solid var(--xt-border); color: var(--xt-text-muted); font-size: 12px; font-weight: 400; text-align: left; }
.xt-today__table td { padding: 12px 0; border-bottom: 1px solid var(--xt-border); }
.xt-today__table .is-num { padding-left: 16px; text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.xt-today__wip-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 24px; }
.xt-today__wip-card { display: grid; gap: 4px; min-width: 0; padding: 12px 0; border-bottom: 1px solid var(--xt-border); }
.xt-today__wip-card > span { color: var(--xt-text-secondary); }
.xt-today__wip-card b { font-size: 20px; font-weight: 600; font-variant-numeric: tabular-nums; }
.xt-today__wip-card small { color: var(--xt-text-muted); font-size: 12px; overflow-wrap: anywhere; }

.xt-today__flow-steps { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 24px 32px; margin: 0; padding: 0; list-style: none; }
.xt-today__flow-step { display: grid; align-content: start; gap: 8px; min-width: 0; padding-top: 12px; border-top: 1px solid var(--xt-border); }
.xt-today__flow-title { font-weight: 600; }
.xt-today__flow-metric, .xt-today__flow-sub li { display: flex; justify-content: space-between; gap: 8px; color: var(--xt-text-secondary); }
.xt-today__flow-metric b { color: var(--xt-text); font-weight: 400; font-variant-numeric: tabular-nums; }
.xt-today__flow-metric.is-muted, .xt-today__flow-metric.is-muted b { color: var(--xt-text-muted); }
.xt-today__flow-sub { margin: 0; padding: 0; list-style: none; font-size: 12px; }
.xt-today__flow-sub li { color: var(--xt-text-muted); padding: 2px 0; }
.xt-today__flow-sub b { font-weight: 400; white-space: nowrap; font-variant-numeric: tabular-nums; }

.xt-today__metric-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 24px 32px; }
.xt-today__compare-card { display: flex; flex-direction: column; gap: 4px; min-width: 0; padding-top: 12px; border-top: 1px solid var(--xt-border); }
.xt-today__compare-card > span { color: var(--xt-text-secondary); }
.xt-today__compare-card strong { font-size: 20px; font-weight: 600; font-variant-numeric: tabular-nums; }
.xt-today__compare-card small { color: var(--xt-text-muted); font-size: 12px; }

.xt-today__event-rail { min-width: 0; }
.xt-today__live-link { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 12px 0; border-block: 1px solid var(--xt-border); color: var(--xt-primary); text-decoration: none; }
.xt-today__live-link span { display: flex; flex-direction: column; gap: 2px; }
.xt-today__live-link strong { font-weight: 400; }
.xt-today__live-link small { color: var(--xt-text-muted); font-size: 12px; }
.xt-today__shift-card { padding: 16px 0; border-bottom: 1px solid var(--xt-border); }
.xt-today__shift-card .xt-today__panel-head { margin-bottom: 8px; }
.xt-today__shift-list { display: grid; gap: 4px; }
.xt-today__shift-row { display: grid; grid-template-columns: 1fr auto 96px; gap: 8px; color: var(--xt-text-secondary); font-variant-numeric: tabular-nums; }
.xt-today__shift-row b { font-weight: 400; }
.xt-today__shift-row small { color: var(--xt-text-muted); font-size: 12px; text-align: right; }
.xt-today__event-card { padding: 16px 0; border-bottom: 1px solid var(--xt-border); overflow-wrap: anywhere; }
.xt-today__event-top { display: flex; justify-content: space-between; gap: 8px; margin-bottom: 4px; color: var(--xt-text-muted); font-size: 12px; }
.xt-today__event-card.tone-warning .xt-today__event-top span { color: var(--xt-warning); }
.xt-today__event-card.tone-danger .xt-today__event-top span { color: var(--xt-danger); }
.xt-today__event-card > strong { font-weight: 600; }
.xt-today__event-card p { margin: 4px 0 0; color: var(--xt-text-secondary); line-height: 1.6; }
.xt-today__empty { padding: 24px 0; color: var(--xt-text-muted); }

.xt-today__bottom-status { display: flex; flex-wrap: wrap; gap: 8px 24px; padding-top: 16px; border-top: 1px solid var(--xt-border); color: var(--xt-text-muted); font-size: 12px; }
.xt-today__status-pill { display: inline-flex; align-items: center; gap: 6px; }
.xt-today__status-pill b, .xt-today__status-pill strong { font-weight: 400; }
.xt-today__status-pill i { width: 6px; height: 6px; border-radius: 50%; background: var(--xt-success); }
.xt-today__status-pill.tone-warning i { background: var(--xt-warning); }
.xt-today__status-pill.tone-danger i { background: var(--xt-danger); }
.xt-today__below-fold { display: grid; gap: 40px; min-height: 240px; }
.xt-today__row { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 40px; }

:deep(.xt-date-switcher button) { border-color: var(--xt-border); border-radius: 4px; background: var(--xt-bg-page); box-shadow: none; color: var(--xt-text); font-weight: 400; }
:deep(.xt-date-switcher button:hover:not(:disabled)) { background: var(--xt-primary-soft); color: var(--xt-primary); }
:deep(.xt-date-switcher__label) { font-family: inherit; font-size: 14px; }
:deep(.xt-cal-pop) { right: 0; left: auto; max-width: calc(100vw - 32px); border-color: var(--xt-border); border-radius: 4px; background: var(--xt-bg-page); box-shadow: var(--xt-shadow-md); }
:deep(.xt-cal-pop__cell.is-selected) { background: var(--xt-primary); color: #fff; }
:deep(.xt-missing-report)::before, :deep(.xt-missing-report)::after { display: none; }
:deep(.xt-missing-report__head span) { display: none; }
:deep(.xt-missing-report__head h2) { font-size: 14px; font-weight: 600; }
:deep(.xt-missing-report__stats b) { font-size: 12px; font-weight: 400; }
:deep(.xt-missing-report__chip) { font-size: 12px; }
:deep(.xt-missing-report) { margin-top: 16px; padding: 0; border: 0; border-radius: 0; background: transparent; box-shadow: none; color: var(--xt-text-secondary); }
:deep(.xt-missing-report__head h2), :deep(.xt-missing-report__head strong), :deep(.xt-missing-report__stats b) { color: var(--xt-text); }
:deep(.xt-missing-report__head small), :deep(.xt-missing-report__chip), :deep(.xt-missing-report__chip.is-muted) { color: var(--xt-text-muted); }
button:focus-visible, summary:focus-visible, a:focus-visible { outline: 2px solid var(--xt-primary); outline-offset: 3px; }

@media (max-width: 1280px) {
  .xt-today__command-wall { grid-template-columns: minmax(0, 1fr) 260px; gap: 32px; }
  .xt-today__lower-grid { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 960px) {
  .xt-today__fact-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 700px) {
  .xt-today { gap: 32px; }
  .xt-today__top-actions { width: 100%; }
  .xt-today__fact-actions { margin-top: -8px; }
  .xt-today__fact-action-link { margin-left: 0; }
  .xt-today__kpi-grid { gap: 28px 16px; }
  .xt-today__kpi-grid > li { grid-column: span 6; }
  .xt-today__kpi-grid > li.is-hero { grid-column: span 12; }
  .xt-today__command-wall { grid-template-columns: minmax(0, 1fr); gap: 32px; }
  .xt-today__event-rail { grid-row: 1; }
  .xt-today__flow-steps, .xt-today__metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .xt-today__row { grid-template-columns: minmax(0, 1fr); }
}
@media (max-width: 480px) {
  .xt-today__fact-strip { grid-template-columns: minmax(0, 1fr); }
  :deep(.xt-date-switcher) { gap: 5px; max-width: 100%; }
  :deep(.xt-date-switcher button) { min-height: 40px; padding-inline: 9px; }
}
</style>
