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
        <span>鑫泰铝业 数据中枢</span>
        <h1>经营总览</h1>
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
          @refresh="refreshAll"
          @pick="onDatePick"
        />
      </div>
    </header>

    <div :aria-busy="snapshot.pending.value.daily" class="xt-today__kpis">
      <KpiBar :items="kpiItems" />
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
        <span class="xt-today__fact-source">{{ fact.source }}</span>
        <span class="xt-today__fact-window">{{ fact.businessWindow || '--' }}</span>
      </button>
    </section>
    </details>

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
          <h2>异常与待办</h2>
          <span>{{ eventRailItems.length }} 条</span>
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
import KpiBar from '../../../components/manage/KpiBar.vue'
const WorkshopBarChart = defineAsyncComponent(() => import('../../../components/manage/WorkshopBarChart.vue'))
const CostLine = defineAsyncComponent(() => import('../../../components/manage/CostLine.vue'))
const OutputTrendLine = defineAsyncComponent(() => import('../../../components/manage/OutputTrendLine.vue'))
const FilerRoster = defineAsyncComponent(() => import('../../../components/manage/FilerRoster.vue'))
import IndustrialProcessIcon from '../../../components/manage/IndustrialProcessIcon.vue'
import MissingReportPanel from '../../../components/manage/MissingReportPanel.vue'
import { rosterStats, buildFilerRoster } from '../../../components/manage/_filerRoster.js'
import { shapeTrendSeries } from '../../../components/manage/_outputTrend.js'
import { shapeEnergyTrend } from '../../../components/manage/_costPanel.js'
import { useDashboardSnapshot } from '../../../composables/useDashboardSnapshot.js'
import { inferBusinessDate } from '../../../utils/shiftClock.js'
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
const currentBusinessDate = ref(inferBusinessDate())
const chartsRoot = ref(null)
const chartsVisible = ref(false)
let chartObserver
let trendRequest = 0
let liveRequest = 0
let usersLoaded = false

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

loadLiveAggregation(snapshot.targetDate.value)
watch(rosterOpen, (open) => { if (open) void loadUsers() })
watch(snapshot.targetDate, (next) => {
  if (chartsVisible.value) void loadTrend(next)
  void loadLiveAggregation(next)
}, { flush: 'sync' })

function refreshAll() {
  currentBusinessDate.value = inferBusinessDate()
  void snapshot.load()
  void loadLiveAggregation(snapshot.targetDate.value)
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

const outputTonsSpark = computed(() => {
  const points = shapeTrendSeries(trendSeries.value, 7).map(row => row.output)
  return points.every(Number.isFinite) ? points : []
})
const energyPerTonSpark = computed(() => {
  const points = shapeEnergyTrend(trendSeries.value, 7).map(row => row.energyPerTon)
  return points.every(Number.isFinite) ? points : []
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
    value: item.value === '暂无可信数据' ? '--' : item.value,
    hint: item.value === '暂无可信数据' ? item.value : item.hint,
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
      label: snapshot.loading.value ? '读取中' : '待核验',
      title: snapshot.loading.value ? '正在读取经营数据' : '暂无可用待办',
      body: '',
      tone: 'muted',
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
  chartObserver?.disconnect()
  trendRequest++
  liveRequest++
  window.removeEventListener('resize', syncCompactClient)
})
</script>

<style scoped>
.xt-today {
  --xt-primary: #236958;
  --xt-primary-hover: #195342;
  --xt-text: #252a30;
  --xt-text-secondary: #616b75;
  --xt-text-muted: #737d86;
  --xt-text-soft: #56616a;
  --xt-bg-page: #fafafa;
  --xt-bg-panel: #fff;
  --xt-bg-panel-soft: #f6f7f7;
  --xt-bg-panel-muted: #f0f3f2;
  --xt-border: #dfe4e3;
  --xt-border-light: #eaeded;
  --xt-success: #21745c;
  --xt-danger: #b64646;
  --xt-warning: #926919;
  --xt-font-display: var(--xt-font-body);
  display: flex;
  flex-direction: column;
  gap: 20px;
  min-width: 0;
  color: var(--xt-text);
  font-size: 13px;
  letter-spacing: 0;
}
.xt-today__topbar { display: flex; flex-wrap: wrap; align-items: center; gap: 18px; }
.xt-today__identity { flex: 1; min-width: 160px; }
.xt-today__identity > span { font-size: 11px; color: #737b83; }
.xt-today__identity h1 { margin: 6px 0; font-size: 27px; font-weight: 650; line-height: 1.25; letter-spacing: 0; }
.xt-today__identity p { margin: 0; font-size: 12px; color: #77818a; }
.xt-today__top-actions { display: flex; align-items: center; justify-content: flex-end; flex-wrap: wrap; gap: 12px; }
.xt-today__quick-nav { order: 3; flex: 1 0 100%; display: flex; gap: 24px; border-bottom: 1px solid #e0e5e3; overflow-x: auto; }
.xt-today__quick-link { display: block; padding: 10px 0 13px; color: #6b747d; font-size: 12px; white-space: nowrap; }
.xt-today__quick-link:hover { color: #236958; }
.xt-today__quick-link[href*="section=daily-report"] { color: #236958; border-bottom: 2px solid #236958; font-weight: 600; }
.xt-today__filer-badge { display: inline-flex; gap: 7px; align-items: center; padding: 8px 0; border: 0; background: transparent; color: #69736e; font: inherit; font-size: 11px; cursor: pointer; }
.xt-today__filer-dot { width: 6px; height: 6px; border-radius: 50%; background: #2e8064; }
.xt-today__filer-badge.tone-danger .xt-today__filer-dot { background: #b36b28; }
.xt-today__filer-pending { color: #a36429; }
.xt-today__filer-chev { font-size: 18px; transform: rotate(90deg); }
.xt-today__filer-chev.is-open { transform: rotate(-90deg); }
.xt-today__kpis { position: relative; }
.xt-today__loading { display: block; height: 20px; margin-top: 6px; color: #64716a; font-size: 11px; }
.xt-today__kpis:has(.xt-today__loading) { margin-bottom: -26px; padding-bottom: 26px; }
:deep(.xt-kpi-bar) { gap: 0; grid-template-columns: repeat(7, minmax(0, 1fr)); border-bottom: 1px solid #e3e7e5; }
:deep(.xt-kpi-bar__card) { display: block; min-height: 140px; padding: 14px 18px; border: 0; border-right: 1px solid #e3e7e5; border-radius: 0; background: transparent; box-shadow: none; min-width: 0; }
:deep(.xt-kpi-bar__card:last-child) { border-right: 0; }
:deep(.xt-kpi-bar__card::before), :deep(.xt-kpi-bar__card::after), :deep(.xt-kpi-bar__icon) { display: none; }
:deep(.xt-kpi-bar__top) { display: flex; flex-wrap: wrap; gap: 4px; min-height: 18px; }
:deep(.xt-kpi-bar__label) { color: #5c6670; font-size: 12px; font-weight: 500; }
:deep(.xt-kpi-bar__value) { margin: 12px 0 6px; font-family: 'Segoe UI', sans-serif; font-size: 28px; font-weight: 600; letter-spacing: 0; flex-wrap: wrap; gap: 5px; }
:deep(.xt-kpi-bar__value span) { color: #242d31; }
:deep(.xt-kpi-bar__value small) { color: #727d83; font-size: 11px; font-weight: 400; }
:deep(.xt-kpi-bar__source), :deep(.xt-kpi-bar__hint) { color: #748078; font-size: 10px; font-weight: 400; overflow-wrap: anywhere; }
:deep(.xt-kpi-bar__hint--placeholder) { height: 0; }
:deep(.xt-kpi-bar__delta) { font-size: 10px; color: #297359; }
.xt-today__sources { border-bottom: 1px solid #e6e9e7; padding-bottom: 12px; }
.xt-today__sources summary { cursor: pointer; color: #4e5d55; font-size: 12px; }
.xt-today__sources summary span { margin-left: 14px; color: #7e8781; font-size: 11px; }
.xt-today__fact-strip { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; padding-top: 12px; }
.xt-today__fact-item { display: flex; flex-direction: column; gap: 4px; padding: 12px; border: 1px solid #e3e7e4; border-radius: 6px; background: #fff; color: #59655e; text-align: left; font: inherit; cursor: pointer; min-width: 0; overflow-wrap: anywhere; }
.xt-today__fact-item:disabled { cursor: default; }
.xt-today__fact-item strong { color: #273e32; font-size: 18px; font-variant-numeric: tabular-nums; }
.xt-today__fact-item small, .xt-today__fact-source, .xt-today__fact-window { font-size: 10px; font-weight: 400; }
.xt-today__fact-status { font-size: 11px; }
.xt-today__fact-item.is-missing .xt-today__fact-status, .xt-today__fact-item.is-mismatch .xt-today__fact-status { color: #aa4842; }
.xt-today__fact-actions { display: flex; align-items: center; gap: 22px; flex-wrap: wrap; padding: 14px 18px; background: #f1f5f2; border-left: 3px solid #81a794; }
.xt-today__fact-actions > div { display: flex; align-items: center; gap: 8px; font-size: 11px; color: #657168; }
.xt-today__fact-actions strong { font-size: 16px; color: #315740; font-variant-numeric: tabular-nums; }
.xt-today__fact-action-link { margin-left: auto; display: grid; place-items: center; width: 32px; height: 32px; color: #236958; }
.xt-today__command-wall { display: grid; grid-template-columns: minmax(0, 1fr) 290px; gap: 28px; align-items: start; }
.xt-today__command-main { display: flex; flex-direction: column; gap: 28px; min-width: 0; }
.xt-today__lower-grid { display: grid; grid-template-columns: minmax(0, 1.2fr) minmax(0, 1fr); gap: 24px; order: 1; }
.xt-today__panel { min-width: 0; }
.xt-today__panel-head, .xt-today__rail-head { display: flex; justify-content: space-between; align-items: baseline; gap: 10px; flex-wrap: wrap; margin-bottom: 16px; }
.xt-today__panel-head h2, .xt-today__rail-head h2 { margin: 0; font-size: 15px; font-weight: 600; color: #2c3530; }
.xt-today__panel-head h3 { margin: 0; font-size: 12px; font-weight: 600; }
.xt-today__panel-head > span, .xt-today__rail-head > span { color: #828b85; font-size: 10px; }
.xt-today__table { width: 100%; border-collapse: collapse; font-size: 12px; }
.xt-today__table th { color: #899087; font-weight: 400; font-size: 10px; padding: 10px 6px; text-align: left; border-bottom: 1px solid #e2e7e3; }
.xt-today__table td { padding: 14px 6px; border-bottom: 1px solid #ecefed; color: #525f56; }
.xt-today__table .is-num { text-align: right; font-variant-numeric: tabular-nums; white-space: nowrap; }
.xt-today__table tbody tr:hover { background: #f2f5f3; }
.xt-today__wip-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 18px; }
.xt-today__wip-card { display: grid; gap: 5px; padding: 12px 0; border-bottom: 1px solid #e5eae6; min-width: 0; }
.xt-today__wip-card > span { color: #748075; font-size: 11px; }
.xt-today__wip-card b { color: #344c3d; font-size: 19px; font-weight: 500; font-variant-numeric: tabular-nums; }
.xt-today__wip-card small { color: #8a948b; font-size: 10px; overflow-wrap: anywhere; }
.xt-today__flow { order: 2; border-top: 1px solid #e3e8e4; padding-top: 20px; }
.xt-today__flow-steps { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 16px 20px; list-style: none; padding: 0; margin: 0; }
.xt-today__flow-step { display: grid; align-content: start; gap: 6px; min-width: 0; padding: 0 0 12px; border-bottom: 1px solid #e8ece8; }
.xt-today__flow-icon { width: 34px; height: 34px; color: #6a9180; }
.xt-today__flow-title { font-size: 12px; font-weight: 600; }
.xt-today__flow-metric { display: flex; justify-content: space-between; gap: 6px; font-size: 11px; }
.xt-today__flow-metric span { color: #7f8a80; }
.xt-today__flow-metric b { font-weight: 500; font-variant-numeric: tabular-nums; }
.xt-today__flow-metric.is-muted { color: #798579; font-size: 10px; }
.xt-today__flow-sub { list-style: none; margin: 4px 0 0; padding: 0; }
.xt-today__flow-sub li { display: flex; justify-content: space-between; gap: 5px; padding: 3px 0; font-size: 10px; color: #819084; }
.xt-today__flow-sub b { font-weight: 400; white-space: nowrap; }
.xt-today__metric-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 20px; order: 3; }
.xt-today__compare-card { display: flex; flex-direction: column; gap: 7px; min-width: 0; padding: 12px 0; border-top: 1px solid #e3e8e4; }
.xt-today__compare-card > span { color: #7c877e; font-size: 11px; }
.xt-today__compare-card strong { color: #354b3a; font-size: 20px; font-weight: 500; font-variant-numeric: tabular-nums; }
.xt-today__compare-card small { color: #849187; font-size: 10px; }
.xt-today__event-rail { min-width: 0; border-left: 1px solid #e1e7e2; padding-left: 24px; }
.xt-today__live-link { display: flex; align-items: center; justify-content: space-between; gap: 12px; color: #306a50; padding: 14px 0 18px; border-bottom: 1px solid #e2e8e3; margin-bottom: 18px; }
.xt-today__live-link span { display: flex; flex-direction: column; gap: 4px; }
.xt-today__live-link strong { font-size: 12px; font-weight: 600; }
.xt-today__live-link small { color: #828e82; font-size: 10px; }
.xt-today__shift-card { margin-bottom: 18px; }
.xt-today__shift-list { display: grid; gap: 9px; }
.xt-today__shift-row { display: grid; grid-template-columns: 1fr 40px 1fr; gap: 8px; font-size: 11px; color: #627363; }
.xt-today__shift-row b { text-align: center; font-weight: 500; }
.xt-today__shift-row small { text-align: right; font-size: 10px; color: #8a948a; }
.xt-today__event-card { padding: 14px 0; border-top: 1px solid #e4e9e5; overflow-wrap: anywhere; }
.xt-today__event-top { display: flex; justify-content: space-between; gap: 8px; font-size: 10px; margin-bottom: 7px; color: #3c765b; }
.xt-today__event-top time { color: #919a92; }
.xt-today__event-card.tone-warning .xt-today__event-top { color: #9d6b25; }
.xt-today__event-card.tone-danger .xt-today__event-top { color: #b24a45; }
.xt-today__event-card > strong { font-size: 12px; font-weight: 500; line-height: 1.6; }
.xt-today__event-card p { font-size: 11px; line-height: 1.8; margin: 6px 0 0; color: #849084; }
.xt-today__empty { padding: 28px 0; font-size: 12px; color: #7d887f; }
.xt-today__bottom-status { display: flex; flex-wrap: wrap; gap: 20px; border-top: 1px solid #e2e7e3; padding-top: 12px; }
.xt-today__status-pill { display: inline-flex; align-items: center; gap: 6px; color: #89948b; font-size: 10px; }
.xt-today__status-pill b, .xt-today__status-pill strong { font-weight: 400; }
.xt-today__status-pill i { width: 5px; height: 5px; border-radius: 50%; background: #729d82; }
.xt-today__status-pill.tone-warning i { background: #b48c50; }
.xt-today__status-pill.tone-danger i { background: #b7625b; }
.xt-today__below-fold { min-height: 240px; display: grid; gap: 24px; padding-top: 12px; }
.xt-today__row { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 24px; }
:deep(.xt-date-switcher button) { color: #56645b; background: #fff; border-color: #dce4df; box-shadow: none; font-weight: 500; }
:deep(.xt-cal-pop) { background: #fff; border-color: #dce4df; box-shadow: 0 8px 24px #152f201a; left: auto; right: 0; max-width: calc(100vw - 32px); }
:deep(.xt-cal-pop__title), :deep(.xt-cal-pop__weekdays) { color: #516659; }
:deep(.xt-cal-pop__cell.is-selected) { background: #236958; color: #fff; }
:deep(.xt-cal-pop__cell.is-out), :deep(.xt-cal-pop__cell.is-future) { color: #909c94; }
:deep(.xt-date-switcher button:hover:not(:disabled)) { background: #edf4ef; color: #236958; }
:deep(.xt-date-switcher__label) { font-family: inherit; font-size: 12px; }
:deep(.xt-missing-report) { background: #f1f5f2; color: #546b5d; box-shadow: none; border-color: #dce5de; border-radius: 6px; padding: 12px; }
:deep(.xt-missing-report__head h2), :deep(.xt-missing-report__head strong), :deep(.xt-missing-report__stats b) { color: #466251; }
:deep(.xt-missing-report__head small), :deep(.xt-missing-report__chip) { color: #697b6d; }
:deep(.xt-missing-report__chip.is-muted) { color: #697b6d; }
button:focus-visible, summary:focus-visible, a:focus-visible { outline: 2px solid #397b69; outline-offset: 3px; }
@media (max-width: 1280px) {
  .xt-today__command-wall { grid-template-columns: minmax(0, 1fr) 260px; gap: 20px; }
  .xt-today__lower-grid { grid-template-columns: 1fr; }
  .xt-today__event-rail { padding-left: 18px; }
  :deep(.xt-kpi-bar__card) { padding: 12px; }
  :deep(.xt-kpi-bar__value) { font-size: 24px; }
  :deep(.xt-kpi-bar) { grid-template-columns: repeat(4, minmax(0, 1fr)); }
}
@media (max-width: 960px) {
  :deep(.xt-kpi-bar) { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  :deep(.xt-kpi-bar__card) { border-bottom: 1px solid #e3e7e5; }
  .xt-today__top-actions { justify-content: flex-start; }
  .xt-today__fact-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 700px) {
  .xt-today { gap: 18px; }
  .xt-today__identity h1 { font-size: 24px; }
  .xt-today__top-actions { width: 100%; gap: 4px; }
  .xt-today__filer-badge { flex: 1 0 100%; }
  .xt-today__command-wall { grid-template-columns: minmax(0, 1fr); gap: 24px; }
  .xt-today__event-rail { grid-row: 1; padding: 0; border-left: 0; }
  .xt-today__flow-steps, .xt-today__metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .xt-today__quick-nav { gap: 20px; }
  .xt-today__row { grid-template-columns: 1fr; }
  .xt-today__fact-actions { gap: 12px; padding: 12px; }
}
@media (max-width: 480px) {
  :deep(.xt-kpi-bar) { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  :deep(.xt-kpi-bar__card) { min-height: 120px; }
  .xt-today__fact-strip { grid-template-columns: 1fr; }
  :deep(.xt-date-switcher) { gap: 5px; max-width: 100%; }
  :deep(.xt-date-switcher button) { padding-inline: 9px; min-height: 40px; }
}
</style>
