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

    <TodayFactBand
      v-if="factActionSummary.openCount"
      :open="factActionSummary.openCount"
      :manual="factActionSummary.actionableCount"
      :recheck="factActionSummary.sourceRecheckCount"
      :dependency="factActionSummary.dependencyCount"
      :to="factActionRoute"
      :link-label="compactClient ? '查看日报事实' : '打开事实待办'"
    />

    <div :aria-busy="snapshot.pending.value.daily" class="xt-today__kpis">
      <ul class="xt-today__kpi-grid" data-testid="manage-kpi-bar">
        <li v-for="item in kpiItems" :key="item.key" :class="`is-${item.size}`">
          <XtMetric
            :label="item.label"
            :value="item.value"
            :unit="item.unit"
            :state="item.state"
            :sub="item.sub"
            :size="item.size"
          />
          <XtSparkArea
            v-if="item.size === 'xl' && outputTrend.length"
            class="xt-today__kpi-trend"
            :points="outputTrend"
            label="近 14 天包装产量走势"
          />
        </li>
      </ul>
      <span v-if="snapshot.pending.value.daily" class="xt-today__loading" role="status">正在读取日报</span>
    </div>

    <article class="xt-today__flow" data-testid="today-production-flow">
      <h2>生产流转</h2>
      <TodayProcessFlow :stages="productionFlowStages" />
    </article>

    <section id="daily-report" class="xt-today__command-wall" data-testid="today-command-wall">
      <div class="xt-today__command-main">
        <article class="xt-today__panel xt-today__workshop">
          <header class="xt-today__panel-head">
            <h2>车间产量</h2>
            <span>过站下机参考</span>
          </header>
          <TodayWorkshopBars v-if="workshopRows.length" :rows="workshopRows" />
          <div v-else class="xt-today__empty">暂无车间过站数据</div>
        </article>

        <article class="xt-today__panel xt-today__wip">
          <header class="xt-today__panel-head">
            <h2>在制料</h2>
            <span>{{ wipRows.length }} 个位置</span>
          </header>
          <TodayWipDonut v-if="wipRows.length" :rows="wipRows" :total-text="wipTotalText" />
          <div v-else class="xt-today__empty">暂无在制料数据</div>
        </article>
      </div>

      <aside class="xt-today__event-rail" data-testid="today-event-rail">
        <header class="xt-today__rail-head">
          <h2>异常与待办</h2>
          <RouterLink class="xt-today__quick-link" to="/manage/alerts">全部异常</RouterLink>
        </header>

        <article
          v-for="item in eventRailItems"
          :key="item.key"
          class="xt-today__event-card"
          :class="`tone-${item.tone}`"
        >
          <span class="xt-today__event-dot" aria-hidden="true" />
          <div>
            <strong>{{ item.title }}</strong>
            <p v-if="item.body">{{ item.body }}</p>
          </div>
        </article>

        <RouterLink class="xt-today__live-link" to="/manage/live">
          <span>当天生产动态</span>
          <el-icon><ArrowRight /></el-icon>
        </RouterLink>

        <section class="xt-today__shift-card">
          <h3>三班填报</h3>
          <div class="xt-today__shift-list">
            <div v-for="shift in shiftTiles" :key="shift.key" class="xt-today__shift-row">
              <span>{{ shift.name }}</span>
              <b>{{ shift.reported }}</b>
            </div>
          </div>
        </section>

        <MissingReportPanel title="缺报明细" :rows="missingRows" :loading="liveLoading" compact />
      </aside>
    </section>

    <section class="xt-today__month" aria-label="本月累计">
      <div v-for="item in highlightMetrics" :key="item.key" class="xt-today__month-item">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
        <small>{{ item.subText }}</small>
      </div>
    </section>

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
import XtSparkArea from '../../../components/xt/XtSparkArea.vue'
import TodayFactBand from './TodayFactBand.vue'
import TodayProcessFlow from './TodayProcessFlow.vue'
import TodayWorkshopBars from './TodayWorkshopBars.vue'
import TodayWipDonut from './TodayWipDonut.vue'
import { shapeTrendSeries } from '../../../components/manage/_outputTrend.js'
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
  void loadTrend(next)
  liveRequest++
  liveAggregation.value = {}
  liveLoadError.value = ''
  liveDate = ''
}, { flush: 'sync' })

function refreshAll() {
  currentBusinessDate.value = inferBusinessDate()
  liveDate = ''
  void snapshot.load()
  void loadTrend(snapshot.targetDate.value)
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

const outputTrend = computed(() => {
  const points = shapeTrendSeries(trendSeries.value, 14).map((row) => row.output)
  return points.some((value) => value !== null) ? points : []
})

const KPI_ORDER = ['plant-output', 'finished-inbound', 'yield-rate', 'feeding-input', 'contract-tonnage', 'energy-per-ton', 'process-throughput']
const KPI_SIZES = { 'plant-output': 'xl', 'finished-inbound': 'lg', 'yield-rate': 'lg' }
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
      size: KPI_SIZES[item.key] || 'md',
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
  void loadTrend(snapshot.targetDate.value)
  dailyRefreshTimer = window.setInterval(() => {
    if (document.visibilityState === 'visible') void snapshot.refreshDaily()
  }, 30000)
  const showCharts = () => {
    chartsVisible.value = true
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
  gap: 64px;
  min-width: 0;
  color: var(--xt-text);
  font-size: 14px;
  line-height: 1.6;
}
.xt-today > * { animation: xt-today-rise 600ms cubic-bezier(0.16, 1, 0.3, 1) backwards; }
.xt-today > :nth-child(2) { animation-delay: 60ms; }
.xt-today > :nth-child(3) { animation-delay: 120ms; }
.xt-today > :nth-child(4) { animation-delay: 180ms; }
.xt-today > :nth-child(n + 5) { animation-delay: 240ms; }
@keyframes xt-today-rise { from { opacity: 0; transform: translateY(12px); } }

.xt-today__topbar { display: flex; flex-wrap: wrap; align-items: flex-end; justify-content: space-between; gap: 16px 32px; margin-bottom: -32px; }
.xt-today__identity h1 { margin: 0; font-size: 28px; font-weight: 600; line-height: 1.25; }
.xt-today__identity p { margin: 4px 0 0; color: var(--xt-text-muted); }
.xt-today__top-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 16px; }
.xt-today__filer-badge { padding: 8px 0; border: 0; background: transparent; color: var(--xt-text-secondary); font: inherit; cursor: pointer; }
.xt-today__filer-badge b { color: var(--xt-text); font-weight: 600; font-variant-numeric: tabular-nums; }
.xt-today__filer-pending { margin-left: 8px; color: var(--xt-warning); }

.xt-today__kpis { position: relative; }
.xt-today__loading { display: block; margin-top: 8px; color: var(--xt-text-muted); font-size: 12px; }
.xt-today__kpi-grid { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 48px 40px; margin: 0; padding: 0; list-style: none; }
.xt-today__kpi-grid > li { grid-column: span 3; min-width: 0; }
.xt-today__kpi-grid > li.is-xl { display: grid; grid-column: span 6; grid-template-columns: auto minmax(0, 1fr); align-items: end; gap: 32px; }
.xt-today__kpi-trend { align-self: end; margin-bottom: 24px; }

.xt-today__flow { padding: 40px; border-radius: 4px; background: var(--xt-bg-panel-soft); }
.xt-today__flow :deep(.xt-flow__node) { background: var(--xt-bg-panel-soft); }
.xt-today__flow > h2 { margin: 0 0 32px; font-size: 20px; font-weight: 600; }

.xt-today__command-wall { display: grid; grid-template-columns: minmax(0, 1fr) 280px; gap: 64px; align-items: start; }
.xt-today__command-main { display: grid; gap: 64px; min-width: 0; }
.xt-today__panel { min-width: 0; }
.xt-today__panel-head, .xt-today__rail-head { display: flex; flex-wrap: wrap; align-items: baseline; justify-content: space-between; gap: 8px; margin-bottom: 24px; }
.xt-today__panel-head h2, .xt-today__rail-head h2 { margin: 0; font-size: 20px; font-weight: 600; }
.xt-today__panel-head > span { color: var(--xt-text-muted); }
.xt-today__quick-link { color: var(--xt-primary); text-decoration: none; }

.xt-today__event-rail { display: grid; gap: 20px; min-width: 0; }
.xt-today__rail-head { margin-bottom: 4px; }
.xt-today__event-card { display: grid; grid-template-columns: 8px minmax(0, 1fr); gap: 12px; overflow-wrap: anywhere; }
.xt-today__event-dot { width: 8px; height: 8px; margin-top: 8px; border-radius: 50%; background: var(--xt-primary); }
.xt-today__event-card.tone-warning .xt-today__event-dot { background: var(--xt-warning); }
.xt-today__event-card.tone-danger .xt-today__event-dot { background: var(--xt-danger); }
.xt-today__event-card.tone-success .xt-today__event-dot { background: var(--xt-success); }
.xt-today__event-card.tone-muted .xt-today__event-dot { background: var(--xt-border); }
.xt-today__event-card strong { font-weight: 400; }
.xt-today__event-card p { display: -webkit-box; margin: 2px 0 0; overflow: hidden; color: var(--xt-text-muted); -webkit-box-orient: vertical; -webkit-line-clamp: 2; }
.xt-today__live-link { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 16px 0; border-block: 1px solid var(--xt-border); color: var(--xt-primary); text-decoration: none; }
.xt-today__shift-card h3 { margin: 0 0 8px; font-size: 14px; font-weight: 600; }
.xt-today__shift-list { display: grid; gap: 4px; }
.xt-today__shift-row { display: flex; justify-content: space-between; gap: 8px; color: var(--xt-text-secondary); font-variant-numeric: tabular-nums; }
.xt-today__shift-row b { font-weight: 400; }
.xt-today__empty { padding: 24px 0; color: var(--xt-text-muted); }

.xt-today__month { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 40px; padding-top: 32px; border-top: 1px solid var(--xt-border); }
.xt-today__month-item { display: grid; gap: 4px; min-width: 0; }
.xt-today__month-item span { color: var(--xt-text-secondary); }
.xt-today__month-item strong { font-size: 28px; font-weight: 600; font-variant-numeric: tabular-nums; }
.xt-today__month-item small { color: var(--xt-text-muted); font-size: 12px; }

.xt-today__below-fold { display: grid; gap: 48px; min-height: 240px; }
.xt-today__row { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 48px; }
.xt-today__row > :deep(*) { padding: 0; border: 0; border-radius: 0; background: transparent; box-shadow: none; }
.xt-today__row > :deep(*)::before, .xt-today__row > :deep(*)::after { display: none; }

.xt-today__sources { padding-top: 16px; border-top: 1px solid var(--xt-border); }
.xt-today__sources summary { color: var(--xt-text-secondary); cursor: pointer; }
.xt-today__sources summary span { margin-left: 12px; color: var(--xt-text-muted); }
.xt-today__fact-strip { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 24px; padding-top: 24px; }
.xt-today__fact-item { display: flex; flex-direction: column; gap: 4px; min-width: 0; padding: 0; border: 0; background: transparent; color: var(--xt-text-muted); font: inherit; font-size: 12px; text-align: left; overflow-wrap: anywhere; cursor: pointer; }
.xt-today__fact-item:disabled { cursor: default; }
.xt-today__fact-label { color: var(--xt-text-secondary); font-size: 14px; }
.xt-today__fact-item strong { color: var(--xt-text); font-size: 20px; font-weight: 600; font-variant-numeric: tabular-nums; }
.xt-today__fact-item small { font-size: 12px; font-weight: 400; }
.xt-today__fact-item.is-confirmed .xt-today__fact-status { color: var(--xt-success); }
.xt-today__fact-item.is-needs_evidence .xt-today__fact-status { color: var(--xt-primary); }
.xt-today__fact-item.is-mismatch .xt-today__fact-status { color: var(--xt-warning); }

.xt-today__bottom-status { display: flex; flex-wrap: wrap; gap: 8px 24px; margin-top: -40px; color: var(--xt-text-muted); font-size: 12px; }
.xt-today__status-pill { display: inline-flex; align-items: center; gap: 6px; }
.xt-today__status-pill b, .xt-today__status-pill strong { font-weight: 400; }
.xt-today__status-pill i { width: 6px; height: 6px; border-radius: 50%; background: var(--xt-success); }
.xt-today__status-pill.tone-warning i { background: var(--xt-warning); }
.xt-today__status-pill.tone-danger i { background: var(--xt-danger); }

:deep(.xt-date-switcher button) { border-color: var(--xt-border); border-radius: 4px; background: var(--xt-bg-page); box-shadow: none; color: var(--xt-text); font-weight: 400; }
:deep(.xt-date-switcher button:hover:not(:disabled)) { background: var(--xt-primary-soft); color: var(--xt-primary); }
:deep(.xt-date-switcher__label) { font-family: inherit; font-size: 14px; }
:deep(.xt-cal-pop) { right: 0; left: auto; max-width: calc(100vw - 32px); border-color: var(--xt-border); border-radius: 4px; background: var(--xt-bg-page); box-shadow: var(--xt-shadow-md); }
:deep(.xt-cal-pop__cell.is-selected) { background: var(--xt-primary); color: #fff; }
:deep(.xt-missing-report) { padding: 0; border: 0; border-radius: 0; background: transparent; box-shadow: none; color: var(--xt-text-secondary); }
:deep(.xt-missing-report)::before, :deep(.xt-missing-report)::after { display: none; }
:deep(.xt-missing-report__head span) { display: none; }
:deep(.xt-missing-report__head h2) { color: var(--xt-text); font-size: 14px; font-weight: 600; }
:deep(.xt-missing-report__head strong), :deep(.xt-missing-report__stats b) { color: var(--xt-text-secondary); font-size: 12px; font-weight: 400; }
:deep(.xt-missing-report__head small), :deep(.xt-missing-report__chip), :deep(.xt-missing-report__chip.is-muted) { color: var(--xt-text-muted); font-size: 12px; }
button:focus-visible, summary:focus-visible, a:focus-visible { outline: 2px solid var(--xt-primary); outline-offset: 3px; }

@media (max-width: 1280px) {
  .xt-today__command-wall { grid-template-columns: minmax(0, 1fr) 240px; gap: 40px; }
  .xt-today__kpi-grid > li.is-xl { grid-column: span 12; }
  .xt-today__kpi-grid > li.is-lg { grid-column: span 6; }
}
@media (max-width: 960px) {
  .xt-today__fact-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .xt-today__month { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 700px) {
  .xt-today { gap: 40px; }
  .xt-today__topbar { margin-bottom: -16px; }
  .xt-today__top-actions { width: 100%; }
  .xt-today__kpi-grid { gap: 32px 16px; }
  .xt-today__kpi-grid > li { grid-column: span 6; }
  .xt-today__kpi-grid > li.is-xl { grid-template-columns: minmax(0, 1fr); gap: 16px; }
  .xt-today__kpi-trend { margin-bottom: 0; }
  .xt-today__flow { padding: 24px 20px; }
  .xt-today__command-wall { grid-template-columns: minmax(0, 1fr); gap: 40px; }
  .xt-today__command-main { gap: 40px; }
  .xt-today__event-rail { grid-row: 1; }
  .xt-today__row { grid-template-columns: minmax(0, 1fr); }
  .xt-today__bottom-status { margin-top: -16px; }
}
@media (max-width: 480px) {
  .xt-today__fact-strip { grid-template-columns: minmax(0, 1fr); }
  .xt-today__kpi-grid > li.is-lg { grid-column: span 12; }
  :deep(.xt-date-switcher) { gap: 5px; max-width: 100%; }
  :deep(.xt-date-switcher button) { min-height: 40px; padding-inline: 9px; }
}
@media (prefers-reduced-motion: reduce) {
  .xt-today > * { animation: none; }
}
</style>
