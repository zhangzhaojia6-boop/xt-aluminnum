<template>
  <ReferencePageFrame
    module-number="05"
    title="工厂作业看板"
    :tags="['审阅端', '厂级']"
    class="page-stack review-factory"
    data-testid="factory-dashboard"
  >
    <section
      class="review-home-hero panel review-factory-hero review-factory-reveal review-factory-reveal--1"
      data-testid="review-home-hero"
      v-loading="loading"
    >
      <div class="review-home-hero__meta">
        <div class="review-home-hero__copy">
          <h2>鑫泰铝业协同运营平台</h2>
        </div>
        <div class="review-home-hero__toolbar">
          <div class="review-home-hero__controls">
            <el-date-picker v-model="targetDate" type="date" value-format="YYYY-MM-DD" />
            <span class="note">最近更新：{{ lastRefreshLabel }}</span>
          </div>
        </div>
      </div>

      <div class="review-home-hero__grid">
        <div class="review-home-hero__metrics">
          <div class="review-home-hero__section-title">
            <el-icon><TrendCharts /></el-icon>
            <span>核心指标</span>
          </div>
          <ReviewCommandDeck :cards="heroCards" />
        </div>
        <div class="review-home-hero__runtime">
          <AgentRuntimeFlow
            title=""
            :trace="runtimeTrace"
            :risks="data.exception_lane || {}"
            compact
          />
        </div>
      </div>
    </section>

    <div class="review-factory-dock review-factory-reveal review-factory-reveal--2">
      <ReviewAssistantDock
        :quick-actions="assistantQuickActions"
        :capabilities="assistantCapabilities"
        :loading="assistantLoading"
        @run="handleAssistantShortcut"
        @open="handleAssistantOpen"
      />
    </div>

    <ReviewAssistantWorkbench
      v-model="assistantOpen"
      :capabilities="assistantCapabilities"
      :loading="assistantLoading"
      :seed-query="assistantSeedQuery"
      :shortcut-seed="assistantShortcutSeed"
    />

    <section class="review-factory-detail-toggle review-factory-reveal review-factory-reveal--3">
      <button type="button" class="review-factory-detail-toggle__btn" @click="detailExpanded = !detailExpanded">
        {{ detailExpanded ? '收起运行详情' : '展开运行详情' }}
      </button>
    </section>

    <div v-show="detailExpanded" class="stat-grid review-factory-reveal review-factory-reveal--3" v-loading="loading">
      <div class="stat-card">
        <div class="stat-label">今日产量</div>
        <div v-if="sourceTagsFor('今日产量').length" class="stat-source-tags">
          <span
            v-for="lane in sourceTagsFor('今日产量')"
            :key="`today-output-${lane.key}`"
            :class="['stat-source-tag', sourceTagClass(lane)]"
          >
            {{ sourceTagText(lane) }}
          </span>
        </div>
        <div class="stat-value">{{ formatNumber(leaderMetrics.today_total_output) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">单吨能耗</div>
        <div v-if="sourceTagsFor('单吨能耗').length" class="stat-source-tags">
          <span
            v-for="lane in sourceTagsFor('单吨能耗')"
            :key="`energy-per-ton-${lane.key}`"
            :class="['stat-source-tag', sourceTagClass(lane)]"
          >
            {{ sourceTagText(lane) }}
          </span>
        </div>
        <div class="stat-value">{{ formatNumber(leaderMetrics.energy_per_ton) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">在制料</div>
        <div class="stat-value">{{ formatNumber(leaderMetrics.in_process_weight) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">成品入库</div>
        <div class="stat-value">{{ formatNumber(leaderMetrics.storage_finished_weight) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">今日发货</div>
        <div v-if="sourceTagsFor('今日发货').length" class="stat-source-tags">
          <span
            v-for="lane in sourceTagsFor('今日发货')"
            :key="`shipment-${lane.key}`"
            :class="['stat-source-tag', sourceTagClass(lane)]"
          >
            {{ sourceTagText(lane) }}
          </span>
        </div>
        <div class="stat-value">{{ formatNumber(leaderMetrics.shipment_weight) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">入库面积</div>
        <div v-if="sourceTagsFor('入库面积').length" class="stat-source-tags">
          <span
            v-for="lane in sourceTagsFor('入库面积')"
            :key="`inbound-area-${lane.key}`"
            :class="['stat-source-tag', sourceTagClass(lane)]"
          >
            {{ sourceTagText(lane) }}
          </span>
        </div>
        <div class="stat-value">{{ formatNumber(leaderMetrics.storage_inbound_area) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">合同量</div>
        <div v-if="sourceTagsFor('合同量').length" class="stat-source-tags">
          <span
            v-for="lane in sourceTagsFor('合同量')"
            :key="`contract-${lane.key}`"
            :class="['stat-source-tag', sourceTagClass(lane)]"
          >
            {{ sourceTagText(lane) }}
          </span>
        </div>
        <div class="stat-value">{{ formatNumber(leaderMetrics.contract_weight) }}</div>
      </div>
      <div class="stat-card" data-testid="delivery-ready-card">
        <div class="stat-label">交付状态</div>
        <div class="stat-value">{{ delivery.delivery_ready ? '可交付' : '未就绪' }}</div>
        <div class="note" data-testid="delivery-missing-steps">缺口：{{ formatDeliveryMissingSteps(delivery.missing_steps).join('；') }}</div>
      </div>
    </div>

    <el-card
      v-show="detailExpanded"
      class="panel review-home-tabs review-factory-tabs review-factory-reveal review-factory-reveal--4"
      v-loading="loading"
    >
      <el-tabs v-model="detailTab">
        <el-tab-pane label="上报" name="reporting">
          <div class="panel-header-shell">
            <span>今日上报状态</span>
            <div v-if="sourceTagsFor('今日上报状态').length" class="panel-source-tags">
              <span
                v-for="lane in sourceTagsFor('今日上报状态')"
                :key="`reporting-${lane.key}`"
                :class="['panel-source-tag', sourceTagClass(lane)]"
              >
                {{ sourceTagText(lane) }}
              </span>
            </div>
          </div>
          <el-table
            v-if="(data.workshop_reporting_status || []).length"
            :data="data.workshop_reporting_status || []"
            class="reporting-status-table"
            stripe
            size="small"
          >
            <el-table-column prop="workshop_name" label="车间" min-width="150" />
            <el-table-column label="状态" width="130">
              <template #default="{ row }">
                <span :class="['reporting-status-pill', `is-${row.report_status || 'unreported'}`, `tone-${reportStatusTagType(row.report_status)}`]">
                  {{ reportStatusLabel(row.report_status) }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="来源" width="130">
              <template #default="{ row }">
                <span :class="['lane-source-pill', reportingSourceClass(row)]">
                  {{ row.source_label || '主操直录' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="产量(吨)" width="120" align="right">
              <template #default="{ row }">
                {{ row.output_weight == null ? '--' : formatNumber(row.output_weight) }}
              </template>
            </el-table-column>
            <el-table-column label="说明" min-width="220">
              <template #default="{ row }">
                <span class="reporting-status-note">{{ row.status_hint || reportStatusHint(row.report_status) }}</span>
              </template>
            </el-table-column>
          </el-table>
          <div v-else class="template-empty">
            暂无车间数据
          </div>
        </el-tab-pane>

        <el-tab-pane label="关注" name="attention">
          <div class="panel-header-shell">
            <span>今日关注</span>
            <div v-if="sourceTagsFor('今日关注').length" class="panel-source-tags">
              <span
                v-for="lane in sourceTagsFor('今日关注')"
                :key="`attention-${lane.key}`"
                :class="['panel-source-tag', sourceTagClass(lane)]"
              >
                {{ sourceTagText(lane) }}
              </span>
            </div>
          </div>
          <el-descriptions :column="4" border>
            <el-descriptions-item label="未报班次">{{ data.exception_lane?.unreported_shift_count ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="迟报班次">{{ data.exception_lane?.reminder_late_count ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="待处理差异">{{ data.exception_lane?.reconciliation_open_count ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="待处理日报">{{ data.exception_lane?.pending_report_publish_count ?? 0 }}</el-descriptions-item>
          </el-descriptions>
          <div class="note">缺口：{{ formatDeliveryMissingSteps(delivery.missing_steps).join('；') }}</div>
        </el-tab-pane>

        <el-tab-pane label="趋势" name="trend">
          <div class="panel-header-shell">
            <span>近 7 日留存趋势</span>
            <div v-if="sourceTagsFor('近 7 日留存趋势').length" class="panel-source-tags">
              <span
                v-for="lane in sourceTagsFor('近 7 日留存趋势')"
                :key="`trend-${lane.key}`"
                :class="['panel-source-tag', sourceTagClass(lane)]"
              >
                {{ sourceTagText(lane) }}
              </span>
            </div>
          </div>
          <div class="history-trend-grid">
            <div v-for="item in dailySnapshots" :key="item.date" class="history-trend-card">
              <div class="history-trend-card__top">
                <strong>{{ item.label }}</strong>
                <span>{{ item.date }}</span>
              </div>
              <div class="history-trend-card__bar">
                <span :style="{ width: trendBarWidth(item.output_weight) }" />
              </div>
              <div class="history-trend-card__meta">
                <div>
                  <span>产量</span>
                  <strong>{{ formatNumber(item.output_weight) }} 吨</strong>
                </div>
                <div>
                  <span>入库</span>
                  <strong>{{ formatNumber(item.storage_finished_weight) }} 吨</strong>
                </div>
                <div>
                  <span>发货</span>
                  <strong>{{ formatNumber(item.shipment_weight) }} 吨</strong>
                </div>
                <div>
                  <span>入库面积</span>
                  <strong>{{ formatNumber(item.storage_inbound_area) }} ㎡</strong>
                </div>
                <div>
                  <span>合同</span>
                  <strong>{{ formatNumber(item.contract_weight) }} 吨</strong>
                </div>
                <div>
                  <span>单吨能耗</span>
                  <strong>{{ formatNumber(item.energy_per_ton) }}</strong>
                </div>
              </div>
            </div>
            <div v-if="!dailySnapshots.length" class="template-empty">
              暂无趋势数据
            </div>
          </div>
        </el-tab-pane>

        <el-tab-pane label="归档" name="archive">
          <div class="panel-header-shell">
            <span>数据留存与归档</span>
            <div v-if="sourceTagsFor('数据留存与归档').length" class="panel-source-tags">
              <span
                v-for="lane in sourceTagsFor('数据留存与归档')"
                :key="`archive-${lane.key}`"
                :class="['panel-source-tag', sourceTagClass(lane)]"
              >
                {{ sourceTagText(lane) }}
              </span>
            </div>
          </div>
          <div class="archive-grid">
            <div class="archive-card">
              <span>月度归档</span>
              <strong>{{ formatNumber(monthArchive.total_output) }} 吨</strong>
              <p>日均 {{ formatNumber(monthArchive.average_daily_output) }} 吨</p>
            </div>
            <div class="archive-card">
              <span>年度归档</span>
              <strong>{{ formatNumber(yearArchive.total_output) }} 吨</strong>
              <p>月均 {{ formatNumber(yearArchive.average_monthly_output) }} 吨</p>
            </div>
            <div class="archive-card archive-card--accent">
              <span>当日留存</span>
              <strong>{{ targetDate }}</strong>
              <p>归档完成</p>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </ReferencePageFrame>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import dayjs from 'dayjs'
import { TrendCharts } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

import { buildAssistantFallback, fetchAssistantCapabilities } from '../../api/assistant'
import { fetchDeliveryStatus, fetchFactoryDashboard } from '../../api/dashboard'
import AgentRuntimeFlow from '../../components/review/AgentRuntimeFlow.vue'
import ReviewAssistantDock from '../../components/review/ReviewAssistantDock.vue'
import ReviewAssistantWorkbench from '../../components/review/ReviewAssistantWorkbench.vue'
import ReviewCommandDeck from '../../components/review/ReviewCommandDeck.vue'
import ReferencePageFrame from '../../components/reference/ReferencePageFrame.vue'
import { formatDeliveryMissingSteps, formatNumber } from '../../utils/display'

function reportStatusLabel(status) {
  const map = {
    submitted: '主操已报',
    reviewed: '系统处理中',
    auto_confirmed: '已入汇总',
    returned: '退回补录',
    draft: '填报中',
    unreported: '待上报',
    late: '迟报'
  }
  return map[status] || status || '待上报'
}

function reportStatusTagType(status) {
  const map = {
    submitted: 'success',
    reviewed: 'success',
    auto_confirmed: 'success',
    returned: 'danger',
    draft: 'primary',
    unreported: 'warning',
    late: 'danger'
  }
  return map[status] || 'info'
}

function reportStatusHint(status) {
  const map = {
    submitted: '主操已报',
    reviewed: '系统处理中',
    auto_confirmed: '已入汇总',
    returned: '退回补录',
    draft: '填报中',
    unreported: '待上报',
    late: '迟报'
  }
  return map[status] || '同步中'
}

function reportingSourceClass(item) {
  const normalized = String(item?.source_variant || '').toLowerCase()
  if (normalized === 'owner') return 'is-owner'
  if (normalized === 'mobile') return 'is-mobile'
  return 'is-import'
}

function prefersExpandedDetail() {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return true
  return window.matchMedia('(min-width: 1080px)').matches
}

const targetDate = ref(dayjs().format('YYYY-MM-DD'))
const loading = ref(false)
const data = ref({})
const delivery = ref({})
const lastRefreshAt = ref('')
const assistantOpen = ref(false)
const assistantLoading = ref(false)
const assistantSeedQuery = ref('')
const assistantShortcutSeed = ref(null)
const assistantCapabilities = ref(buildAssistantFallback())
const detailTab = ref('reporting')
const detailExpanded = ref(prefersExpandedDetail())
const lastLoadErrorMessage = ref('')
const leaderMetrics = computed(() => data.value.leader_metrics || {})
const historyDigest = computed(() => data.value.history_digest || {})
const runtimeTrace = computed(() => data.value.runtime_trace || {})
const runtimeSourceIndex = computed(() => {
  const index = {}
  for (const lane of runtimeTrace.value.source_lanes || []) {
    for (const target of lane.result_targets || []) {
      if (!index[target]) index[target] = []
      index[target].push(lane)
    }
  }
  return index
})
const dailySnapshots = computed(() => historyDigest.value.daily_snapshots || [])
const monthArchive = computed(() => historyDigest.value.month_archive || {})
const yearArchive = computed(() => historyDigest.value.year_archive || {})
const maxTrendOutput = computed(() => Math.max(...dailySnapshots.value.map((item) => Number(item.output_weight) || 0), 1))
const monthToDateOutput = computed(() => data.value.month_to_date_output ?? data.value.leader_metrics?.month_to_date_output ?? null)
const lastRefreshLabel = computed(() => (lastRefreshAt.value ? dayjs(lastRefreshAt.value).format('HH:mm:ss') : '--:--:--'))
const retentionSummary = computed(() => `${monthArchive.value.reported_days ?? 0} 天归档`)
const assistantQuickActions = computed(() => assistantCapabilities.value.quick_actions || buildAssistantFallback().quick_actions)
let assistantShortcutSequence = 0
const heroCards = computed(() => [
  {
    key: 'today-output',
    label: '产量合计',
    value: `${formatNumber(leaderMetrics.value.today_total_output)} 吨`,
    hint: '主线指标。',
    tone: 'success'
  },
  {
    key: 'unreported',
    label: '缺报班次',
    value: `${data.value.exception_lane?.unreported_shift_count ?? 0}`,
    hint: '先补原始值。',
    tone: (data.value.exception_lane?.unreported_shift_count ?? 0) > 0 ? 'danger' : 'success'
  },
  {
    key: 'exceptions',
    label: '异常与退回',
    value: `${(data.value.exception_lane?.mobile_exception_count ?? 0) + (data.value.exception_lane?.returned_shift_count ?? 0)}`,
    hint: '先清异常。',
    tone:
      (data.value.exception_lane?.mobile_exception_count ?? 0) + (data.value.exception_lane?.returned_shift_count ?? 0) > 0
        ? 'alert'
        : 'success'
  },
  {
    key: 'delivery',
    label: '交付进度',
    value: delivery.value.delivery_ready ? '已具备' : '待补齐',
    hint: formatDeliveryMissingSteps(delivery.value.missing_steps).join('；') || '关键链路已具备。',
    tone: delivery.value.delivery_ready ? 'success' : 'alert'
  },
  {
    key: 'energy',
    label: '单吨能耗',
    value: `${formatNumber(leaderMetrics.value.energy_per_ton)}`,
    hint: '盯住波动。',
    tone: 'primary'
  },
  {
    key: 'retention',
    label: '数据留存',
    value: retentionSummary.value,
    hint: `月累计 ${formatNumber(monthToDateOutput.value)} 吨。`,
    tone: 'primary'
  }
])
let refreshTimer = null

function mergeAssistantCapabilities(payload = {}) {
  return {
    ...buildAssistantFallback(),
    ...payload,
    groups: payload.groups || buildAssistantFallback().groups
  }
}

function trendBarWidth(value) {
  const safeValue = Number(value) || 0
  return `${Math.max((safeValue / maxTrendOutput.value) * 100, safeValue > 0 ? 12 : 0)}%`
}

function sourceTagsFor(target) {
  return runtimeSourceIndex.value[target] || []
}

function sourceTagText(lane) {
  if (!lane?.stage_label) return `来自 ${lane?.label || ''}`.trim()
  return `${lane.label} · ${lane.stage_label}`
}

function sourceTagClass(lane) {
  return lane?.status ? `is-${lane.status}` : ''
}

function requestErrorMessage(error, fallback = '数据加载失败，请稍后重试') {
  const detail = error?.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || item).join('；')
  }
  if (detail && typeof detail === 'object') {
    return detail.message || detail.msg || fallback
  }
  if (typeof detail === 'string' && detail.trim()) {
    return detail.trim()
  }
  return error?.message || fallback
}

function handleAssistantOpen() {
  assistantSeedQuery.value = ''
  assistantShortcutSeed.value = null
  assistantOpen.value = true
}

function handleAssistantShortcut(action) {
  const query = action?.query || action?.label || ''
  assistantShortcutSequence += 1
  assistantSeedQuery.value = query
  assistantShortcutSeed.value = {
    key: action?.key || `assistant-shortcut-${assistantShortcutSequence}`,
    mode: action?.mode || 'answer',
    query,
    token: `assistant-shortcut-${assistantShortcutSequence}`
  }
  assistantOpen.value = true
}

async function load() {
  loading.value = true
  try {
    const [dashboardPayload, deliveryPayload] = await Promise.all([
      fetchFactoryDashboard({ target_date: targetDate.value }),
      fetchDeliveryStatus({ target_date: targetDate.value })
    ])
    data.value = dashboardPayload
    delivery.value = deliveryPayload
    lastRefreshAt.value = new Date().toISOString()
    lastLoadErrorMessage.value = ''
  } catch (error) {
    const message = requestErrorMessage(error, '数据加载失败，请稍后重试')
    if (message !== lastLoadErrorMessage.value) {
      ElMessage.error(message)
      lastLoadErrorMessage.value = message
    }
  } finally {
    loading.value = false
  }
}

async function loadAssistant() {
  assistantLoading.value = true
  try {
    const payload = await fetchAssistantCapabilities()
    assistantCapabilities.value = mergeAssistantCapabilities(payload)
  } catch {
    assistantCapabilities.value = buildAssistantFallback()
  } finally {
    assistantLoading.value = false
  }
}

watch(targetDate, () => load())

onMounted(() => {
  load()
  loadAssistant()
  refreshTimer = setInterval(load, 30000)
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})
</script>

<style scoped>
.review-factory {
  position: relative;
}

.review-factory-reveal {
  opacity: 0;
  transform: translateY(4px);
  animation: review-factory-reveal 0.2s ease forwards;
}

.review-factory-reveal--1 {
  animation-delay: 0.02s;
}

.review-factory-reveal--2 {
  animation-delay: 0.04s;
}

.review-factory-reveal--3 {
  animation-delay: 0.06s;
}

.review-factory-reveal--4 {
  animation-delay: 0.08s;
}

.review-factory-hero {
  border-radius: 18px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  box-shadow: var(--app-shadow-sm);
}

.review-factory-dock {
  margin: 0;
}

.review-factory-tabs :deep(.el-tabs__header) {
  margin-bottom: 14px;
}

.review-factory-tabs :deep(.el-tabs__nav-wrap::after) {
  height: 1px;
}

.review-factory-tabs :deep(.el-tabs__item) {
  margin: 0 4px 6px 0;
  border-radius: 999px;
  font-weight: 600;
}

.review-factory-tabs :deep(.el-tabs__active-bar) {
  border-radius: 999px;
}

.review-home-hero,
.review-home-hero__meta,
.review-home-hero__copy,
.review-home-hero__toolbar,
.review-home-hero__controls,
.review-home-hero__grid,
.review-home-hero__metrics,
.review-home-hero__runtime {
  display: grid;
  gap: 8px;
}

.review-home-hero {
  padding: 16px;
  background:
    radial-gradient(circle at top right, rgba(37, 99, 235, 0.08), transparent 38%),
    rgba(255, 255, 255, 0.96);
}

.review-home-hero__meta {
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 14px;
  align-items: start;
}

.review-home-hero__copy h2 {
  margin: 0;
  font-size: clamp(26px, 2.3vw, 36px);
  line-height: 1.1;
  letter-spacing: -0.02em;
  color: var(--app-text);
}

.review-home-hero__toolbar {
  align-items: start;
  justify-items: end;
}

.review-home-hero__controls {
  width: min(280px, 100%);
  justify-items: end;
  gap: 8px;
}

.review-home-hero__controls :deep(.el-input__wrapper) {
  border-radius: 10px;
}

.review-home-hero__controls .note,
.review-home-hero__section-title {
  font-size: 12px;
  color: var(--app-muted);
}

.review-home-hero__section-title {
  font-weight: 700;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.review-home-hero__section-title :deep(.el-icon) {
  width: 20px;
  height: 20px;
  border-radius: 8px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: rgba(219, 234, 254, 0.86);
  border: 1px solid rgba(59, 130, 246, 0.24);
  color: #1d4ed8;
}

.review-home-hero__grid {
  grid-template-columns: minmax(0, 1.1fr) minmax(400px, 0.9fr);
  align-items: start;
  gap: 12px;
}

.review-factory .stat-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.review-factory-detail-toggle {
  display: flex;
  justify-content: center;
}

.review-factory-detail-toggle__btn {
  min-height: 36px;
  padding: 0 16px;
  border-radius: 999px;
  border: 1px solid rgba(148, 163, 184, 0.24);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(247, 250, 255, 0.96));
  color: #334155;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
  transition:
    transform var(--app-motion-fast) var(--app-motion-curve),
    box-shadow var(--app-motion-fast) var(--app-motion-curve),
    border-color var(--app-motion-fast) ease,
    background-color var(--app-motion-fast) ease;
}

.review-factory-detail-toggle__btn:hover {
  transform: translateY(-1px);
  border-color: rgba(59, 130, 246, 0.28);
  box-shadow: var(--app-shadow-xs);
  background: linear-gradient(180deg, rgba(239, 246, 255, 0.96), rgba(247, 252, 255, 0.96));
}

.review-factory-detail-toggle__btn:focus-visible {
  outline: none;
  box-shadow: var(--app-focus-ring);
}

.review-factory .stat-card {
  min-height: 116px;
  padding: 15px;
}

.review-home-hero__metrics,
.review-home-hero__runtime {
  padding: 14px;
  border-radius: 14px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: rgba(248, 250, 252, 0.94);
  box-shadow: var(--app-shadow-xs);
}
.review-factory-tabs {
  border: 1px solid rgba(148, 163, 184, 0.18);
  box-shadow: var(--app-shadow-xs);
}

@keyframes review-factory-reveal {
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.reporting-status-table {
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 12px;
  overflow: hidden;
}

.reporting-status-table :deep(.el-table__cell) {
  padding-top: 8px;
  padding-bottom: 8px;
}

.reporting-status-table :deep(.cell) {
  font-size: 12px;
}

.reporting-status-table :deep(thead .cell) {
  font-size: 11px;
  letter-spacing: 0.02em;
  color: #475569;
}

.reporting-status-pill {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 0 9px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 600;
  border: 1px solid transparent;
  background: rgba(226, 232, 240, 0.8);
  color: #334155;
}

.reporting-status-pill.is-submitted,
.reporting-status-pill.is-reviewed,
.reporting-status-pill.is-auto_confirmed {
  color: #0f766e;
  background: rgba(209, 250, 229, 0.7);
  border-color: rgba(16, 185, 129, 0.26);
}

.reporting-status-pill.is-draft {
  color: #1d4ed8;
  background: rgba(219, 234, 254, 0.76);
  border-color: rgba(59, 130, 246, 0.28);
}

.reporting-status-pill.is-unreported {
  color: #92400e;
  background: rgba(254, 243, 199, 0.78);
  border-color: rgba(245, 158, 11, 0.3);
}

.reporting-status-pill.is-late,
.reporting-status-pill.is-returned {
  color: #991b1b;
  background: rgba(254, 226, 226, 0.82);
  border-color: rgba(239, 68, 68, 0.3);
}

.reporting-status-note {
  display: inline-block;
  color: #64748b;
  line-height: 1.45;
}

.history-trend-grid,
.archive-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 12px;
}

.history-trend-card,
.archive-card {
  display: grid;
  gap: 8px;
  padding: 13px;
  border-radius: 14px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(248, 251, 255, 0.95));
  box-shadow: var(--app-shadow-xs);
  transition:
    transform var(--app-motion-fast) var(--app-motion-curve),
    border-color var(--app-motion-fast) ease,
    box-shadow var(--app-motion-fast) var(--app-motion-curve);
}

.history-trend-card:hover,
.archive-card:hover {
  transform: translateY(-2px);
  border-color: rgba(59, 130, 246, 0.2);
  box-shadow: var(--app-shadow-sm);
}

.history-trend-card__top,
.history-trend-card__meta,
.history-trend-card__meta > div,
.archive-card {
  display: grid;
  gap: 8px;
}

.review-factory-tabs :deep(.el-card__body) {
  padding-top: 4px;
}

.history-trend-card__top strong,
.archive-card strong {
  font-size: 18px;
  color: var(--app-text);
}

.history-trend-card__top span,
.history-trend-card__meta span,
.archive-card span {
  font-size: 12px;
  color: var(--app-muted);
}

.history-trend-card__bar {
  overflow: hidden;
  height: 8px;
  border-radius: 999px;
  background: rgba(148, 163, 184, 0.16);
}

.history-trend-card__bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, #0f766e, #0ea5e9);
}

.history-trend-card__meta strong {
  font-size: 14px;
  color: var(--app-text);
}

.archive-card p {
  margin: 0;
  color: var(--app-muted);
  line-height: 1.55;
}

.archive-card--accent {
  border-color: rgba(59, 130, 246, 0.26);
  background: rgba(239, 246, 255, 0.82);
}

.review-home-tabs :deep(.el-tabs__header) {
  margin-bottom: 14px;
}

.template-empty {
  padding: 18px 16px;
  border-radius: 12px;
  border: 1px dashed rgba(148, 163, 184, 0.4);
  color: var(--app-muted);
  text-align: center;
}

@media (max-width: 1280px) {
  .review-factory .stat-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 1100px) {
  .review-factory .stat-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .review-home-hero__meta,
  .review-home-hero__grid,
  .review-factory .stat-grid {
    grid-template-columns: 1fr;
  }

  .review-home-hero__toolbar,
  .review-home-hero__controls {
    justify-items: start;
    width: 100%;
  }

  .history-trend-grid,
  .archive-grid {
    grid-template-columns: 1fr;
  }

  .review-factory-tabs :deep(.el-tabs__item) {
    margin: 0 2px 6px 0;
  }
}

@media (max-width: 640px) {
  .review-home-hero {
    padding: 12px;
  }

  .review-home-hero__copy h2 {
    font-size: 28px;
  }
}
</style>
