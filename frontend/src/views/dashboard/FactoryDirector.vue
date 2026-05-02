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
          <h2>鑫泰铝业 数据中枢</h2>
        </div>
        <div class="review-home-hero__toolbar">
          <div class="review-home-hero__controls">
            <el-date-picker v-model="targetDate" type="date" value-format="YYYY-MM-DD" />
            <span class="note">最近更新：{{ lastRefreshLabel }}</span>
          </div>
        </div>
      </div>

      <div class="review-home-hero__war-room" style="display:none">
        <XtFactoryMap
          compact
          :nodes="factoryMapNodes"
          :lines="factoryMapLines"
          :alerts="factoryMapAlerts"
          :active-key="factoryActiveKey"
        />
        <div class="review-home-hero__execution">
          <div class="review-home-hero__execution-head">
            <span>AI 总管执行链</span>
            <strong>{{ factoryDirectorBrief }}</strong>
          </div>
          <XtExecutionRail :steps="factoryExecutionSteps" :active-index="factoryExecutionActiveIndex" compact />
        </div>
      </div>

      <div class="review-home-hero__workshop-ribbon" style="display:none">
        <button
          v-for="workshop in workshopGlyphs"
          :key="workshop.key"
          type="button"
          class="review-home-hero__workshop-card"
          :class="{ 'is-active': workshop.active }"
        >
          <XtWorkshopGlyph :workshop-type="workshop.type" :active="workshop.active" compact />
          <span>{{ workshop.name }}</span>
          <strong>{{ workshop.status }}</strong>
        </button>
      </div>

      <div class="review-home-hero__core-metrics">
        <div class="core-metric-card">
          <div class="core-metric-card__label">今日产量</div>
          <div class="core-metric-card__value">{{ formatNumber(leaderMetrics.today_total_output) }}</div>
          <div class="core-metric-card__unit">吨</div>
        </div>
        <div class="core-metric-card">
          <div class="core-metric-card__label">缺报班次</div>
          <div
            class="core-metric-card__value"
            :class="{ 'core-metric-card__value--alert': (data.exception_lane?.unreported_shift_count ?? 0) > 0 }"
          >
            {{ data.exception_lane?.unreported_shift_count ?? 0 }}
          </div>
        </div>
        <div class="core-metric-card">
          <div class="core-metric-card__label">异常与退回</div>
          <div
            class="core-metric-card__value"
            :class="{ 'core-metric-card__value--alert': factoryAbnormalCount > 0 }"
          >
            {{ factoryAbnormalCount }}
          </div>
        </div>
      </div>

      <div class="review-home-hero__secondary-metrics">
        <div class="secondary-metric">
          <span class="secondary-metric__label">交付进度</span>
          <strong class="secondary-metric__value" :class="delivery.delivery_ready ? 'is-ok' : 'is-gap'">
            {{ delivery.delivery_ready ? '可交付' : '待补齐' }}
          </strong>
        </div>
        <div class="secondary-metric">
          <span class="secondary-metric__label">单吨能耗</span>
          <strong class="secondary-metric__value">{{ formatNumber(leaderMetrics.energy_per_ton) }}</strong>
        </div>
        <div class="secondary-metric">
          <span class="secondary-metric__label">月累计</span>
          <strong class="secondary-metric__value">{{ formatNumber(monthToDateOutput) }} 吨</strong>
        </div>
      </div>

      <div class="review-home-hero__grid" style="display:none">
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
import { computed, ref } from 'vue'
import dayjs from 'dayjs'
import { TrendCharts } from '@element-plus/icons-vue'
import { useRoute } from 'vue-router'

import AgentRuntimeFlow from '../../components/review/AgentRuntimeFlow.vue'
import ReviewAssistantDock from '../../components/review/ReviewAssistantDock.vue'
import ReviewAssistantWorkbench from '../../components/review/ReviewAssistantWorkbench.vue'
import ReviewCommandDeck from '../../components/review/ReviewCommandDeck.vue'
import ReferencePageFrame from '../../components/reference/ReferencePageFrame.vue'
import { XtExecutionRail, XtFactoryMap, XtWorkshopGlyph } from '../../components/xt'
import { useAssistantIntegration } from '../../composables/useAssistantIntegration'
import { useFactoryDashboard } from '../../composables/useFactoryDashboard'
import { formatDeliveryMissingSteps, formatNumber } from '../../utils/display'
import {
  reportStatusLabel,
  reportStatusTagType,
  reportStatusHint,
  reportingSourceClass,
  toFactoryStatus,
  workshopTypeFromName
} from '../../utils/reportStatus'

const route = useRoute()

function prefersExpandedDetail() {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return true
  return window.matchMedia('(min-width: 1080px)').matches
}

function resolveInitialTargetDate() {
  const value = typeof route.query.target_date === 'string' ? route.query.target_date : ''
  if (/^\d{4}-\d{2}-\d{2}$/.test(value) && dayjs(value).isValid()) return value
  return dayjs().format('YYYY-MM-DD')
}

const targetDate = ref(resolveInitialTargetDate())
const {
  loading, data, delivery,
  leaderMetrics, runtimeTrace,
  dailySnapshots, monthArchive, yearArchive,
  monthToDateOutput, lastRefreshLabel, retentionSummary,
  load
} = useFactoryDashboard(targetDate)
const {
  assistantOpen, assistantLoading,
  assistantSeedQuery, assistantShortcutSeed,
  assistantCapabilities, assistantQuickActions,
  handleAssistantOpen, handleAssistantShortcut
} = useAssistantIntegration()
const detailTab = ref('reporting')
const detailExpanded = ref(prefersExpandedDetail())
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
const maxTrendOutput = computed(() => Math.max(...dailySnapshots.value.map((item) => Number(item.output_weight) || 0), 1))
const exceptionCounts = computed(() => {
  const lane = data.value.exception_lane || {}
  return {
    unreported: Number(lane.unreported_shift_count || 0),
    returned: Number(lane.returned_shift_count || 0),
    mobile: Number(lane.mobile_exception_count || 0),
    late: Number(lane.reminder_late_count || 0),
    reconciliation: Number(lane.reconciliation_open_count || 0),
    pendingPublish: Number(lane.pending_report_publish_count || 0)
  }
})
const factoryAbnormalCount = computed(() => exceptionCounts.value.mobile + exceptionCounts.value.returned + exceptionCounts.value.late)
const factoryPendingCount = computed(() => exceptionCounts.value.reconciliation + exceptionCounts.value.pendingPublish)
const factoryMissingSteps = computed(() => formatDeliveryMissingSteps(delivery.value.missing_steps || []))
const factoryActiveKey = computed(() => {
  if (exceptionCounts.value.unreported || factoryAbnormalCount.value) return 'entry'
  if (exceptionCounts.value.reconciliation) return 'ai'
  if (!delivery.value.delivery_ready) return 'publish'
  return 'ai'
})
const factoryMapNodes = computed(() => [
  {
    key: 'entry',
    label: '现场直录',
    short: '录',
    status: exceptionCounts.value.unreported || factoryAbnormalCount.value ? 'warning' : 'normal',
    x: '13%',
    y: '34%'
  },
  {
    key: 'casting',
    label: '铸锭产线',
    short: '锭',
    status: factoryAbnormalCount.value ? 'warning' : 'normal',
    x: '36%',
    y: '64%'
  },
  {
    key: 'storage',
    label: '成品入库',
    short: '库',
    status: 'normal',
    x: '58%',
    y: '35%'
  },
  {
    key: 'ai',
    label: 'AI 调度',
    short: 'AI',
    status: factoryPendingCount.value ? 'warning' : 'normal',
    x: '74%',
    y: '58%'
  },
  {
    key: 'publish',
    label: '日报交付',
    short: '报',
    status: delivery.value.delivery_ready ? 'normal' : 'warning',
    x: '88%',
    y: '28%'
  }
])
const factoryMapLines = computed(() => {
  const lanes = runtimeTrace.value.source_lanes || []
  if (lanes.length) {
    return lanes.slice(0, 5).map((lane, index) => ({
      key: lane.key || `${lane.label || 'lane'}-${index}`,
      label: lane.label || lane.key || `数据源 ${index + 1}`,
      value: lane.stage_label || lane.status_label || '同步',
      status: toFactoryStatus(lane.status)
    }))
  }
  return [
    { key: 'zd', label: '铸锭车间', value: '在线', status: 'normal' },
    { key: 'sync', label: '生产系统', value: '同步', status: 'normal' },
    { key: 'report', label: '日报', value: delivery.value.delivery_ready ? '就绪' : '待补齐', status: delivery.value.delivery_ready ? 'normal' : 'warning' }
  ]
})
const factoryMapAlerts = computed(() => [
  { key: 'unreported', label: '缺报班次', value: exceptionCounts.value.unreported, status: 'warning' },
  { key: 'late', label: '迟报班次', value: exceptionCounts.value.late, status: 'warning' },
  { key: 'returned', label: '退回补录', value: exceptionCounts.value.returned, status: 'danger' },
  { key: 'reconciliation', label: '差异待核', value: exceptionCounts.value.reconciliation, status: 'warning' },
  { key: 'publish', label: '日报待发', value: exceptionCounts.value.pendingPublish, status: 'warning' }
].filter((item) => Number(item.value || 0) > 0).slice(0, 4))
const factoryExecutionSteps = computed(() => {
  const sourceCount = runtimeTrace.value.source_lanes?.length || factoryMapLines.value.length
  const missingText = factoryMissingSteps.value.join('、')
  return [
    { key: 'discover', label: '发现', detail: `${sourceCount || 0} 条数据源在线`, status: 'done' },
    {
      key: 'judge',
      label: '判断',
      detail: factoryAbnormalCount.value ? `${factoryAbnormalCount.value} 项异常需优先闭环` : '校验规则通过',
      status: factoryAbnormalCount.value ? 'warning' : 'done'
    },
    {
      key: 'execute',
      label: '执行',
      detail: exceptionCounts.value.unreported ? `自动催报 ${exceptionCounts.value.unreported} 个班次` : '汇总、核对、补差动作就绪',
      status: exceptionCounts.value.unreported ? 'running' : 'done'
    },
    {
      key: 'audit',
      label: '留痕',
      detail: factoryPendingCount.value ? `${factoryPendingCount.value} 项等待闭环记录` : '审计链路完整',
      status: factoryPendingCount.value ? 'warning' : 'done'
    },
    {
      key: 'publish',
      label: '发布',
      detail: delivery.value.delivery_ready ? '日报可以交付' : `缺口：${missingText || '等待交付条件'}`,
      status: delivery.value.delivery_ready ? 'done' : 'warning'
    }
  ]
})
const factoryExecutionActiveIndex = computed(() => {
  const index = factoryExecutionSteps.value.findIndex((item) => ['warning', 'danger', 'running'].includes(item.status))
  return index >= 0 ? index : factoryExecutionSteps.value.length - 1
})
const factoryDirectorBrief = computed(() => {
  if (factoryMapAlerts.value.length) return `当前 ${factoryMapAlerts.value.length} 类风险会影响日报节奏，AI 已按优先级推进。`
  if (delivery.value.delivery_ready) return '现场采集、自动汇总、日报交付均处于可交付状态。'
  return '交付链路仍有缺口，AI 正把缺口拆成可执行动作。'
})
const workshopGlyphs = computed(() => {
  const rows = data.value.workshop_reporting_status || []
  const source = rows.length
    ? rows
    : [
        { workshop_name: '铸锭车间', report_status: 'submitted' },
        { workshop_name: '热轧车间', report_status: 'submitted' },
        { workshop_name: '冷轧车间', report_status: 'submitted' },
        { workshop_name: '拉矫车间', report_status: 'submitted' },
        { workshop_name: '在线退火', report_status: 'submitted' },
        { workshop_name: '成品库', report_status: 'submitted' }
      ]
  return source.slice(0, 8).map((item, index) => {
    const name = item.workshop_name || item.name || `车间 ${index + 1}`
    const status = item.report_status || item.status || 'submitted'
    return {
      key: item.workshop_id || item.id || `${name}-${index}`,
      name,
      status: reportStatusLabel(status),
      type: workshopTypeFromName(name),
      active: ['returned', 'late', 'unreported'].includes(String(status).toLowerCase())
    }
  })
})
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
  border-radius: var(--xt-radius-lg);
  border: 1px solid var(--xt-border);
  box-shadow: var(--xt-shadow-sm);
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
  border-radius: var(--xt-radius-md);
  font-weight: 600;
}

.review-factory-tabs :deep(.el-tabs__active-bar) {
  border-radius: var(--xt-radius-sm);
}

.review-home-hero,
.review-home-hero__meta,
.review-home-hero__copy,
.review-home-hero__toolbar,
.review-home-hero__controls,
.review-home-hero__grid,
.review-home-hero__war-room,
.review-home-hero__workshop-ribbon,
.review-home-hero__execution,
.review-home-hero__execution-head,
.review-home-hero__metrics,
.review-home-hero__runtime {
  display: grid;
  gap: 8px;
}

.review-home-hero {
  padding: 16px;
  background: var(--xt-bg-panel);
}

.review-home-hero__meta {
  grid-template-columns: minmax(0, 1fr) auto;
  gap: 14px;
  align-items: start;
}

.review-home-hero__copy h2 {
  margin: 0;
  font-size: clamp(22px, 1.7vw, 28px);
  line-height: 1.14;
  letter-spacing: 0;
  color: var(--xt-text);
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
  border-radius: var(--xt-radius-lg);
}

.review-home-hero__controls .note,
.review-home-hero__section-title,
.review-home-hero__execution-head span {
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
  border-radius: var(--xt-radius-md);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--xt-primary-light);
  border: 1px solid var(--xt-primary-border);
  color: var(--xt-primary);
}

.review-home-hero__grid {
  grid-template-columns: minmax(0, 1.1fr) minmax(400px, 0.9fr);
  align-items: start;
  gap: 12px;
}

.review-home-hero__core-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--xt-space-4);
  margin-top: var(--xt-space-2);
}

.core-metric-card {
  background: var(--xt-bg-panel-soft);
  border-radius: var(--xt-radius-xl);
  border: 1px solid var(--xt-border-light);
  padding: var(--xt-space-5) var(--xt-space-4);
  text-align: center;
  box-shadow: var(--xt-shadow-sm);
  transition: transform var(--app-motion-fast) var(--app-motion-curve),
    box-shadow var(--app-motion-fast) var(--app-motion-curve);
}

.core-metric-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--xt-shadow-md);
}

.core-metric-card__label {
  font-size: 13px;
  font-weight: 700;
  color: var(--xt-text-secondary);
  letter-spacing: 0.02em;
}

.core-metric-card__value {
  font-family: var(--xt-font-number);
  font-size: clamp(28px, 3vw, 40px);
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.02em;
  line-height: 1.1;
  margin-top: var(--xt-space-2);
  color: var(--xt-text);
}

.core-metric-card__value--alert {
  color: var(--xt-danger);
}

.core-metric-card__unit {
  font-size: 13px;
  color: var(--xt-text-muted);
  margin-top: 2px;
}

.review-home-hero__secondary-metrics {
  display: flex;
  gap: var(--xt-space-3);
  margin-top: var(--xt-space-2);
}

.secondary-metric {
  flex: 1;
  display: flex;
  align-items: baseline;
  gap: var(--xt-space-2);
  padding: var(--xt-space-3) var(--xt-space-4);
  background: var(--xt-bg-panel-soft);
  border-radius: var(--xt-radius-lg);
  border: 1px solid var(--xt-border-light);
}

.secondary-metric__label {
  font-size: 13px;
  color: var(--xt-text-muted);
  white-space: nowrap;
}

.secondary-metric__value {
  font-family: var(--xt-font-number);
  font-size: 18px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.01em;
}

.secondary-metric__value.is-ok {
  color: var(--xt-success);
}

.secondary-metric__value.is-gap {
  color: var(--xt-warning);
}

.review-home-hero__war-room {
  grid-template-columns: minmax(0, 1.25fr) minmax(340px, 0.75fr);
  align-items: stretch;
  gap: 12px;
}

.review-home-hero__workshop-ribbon {
  grid-template-columns: repeat(auto-fit, minmax(132px, 1fr));
  gap: 10px;
}

.review-home-hero__workshop-card {
  min-width: 0;
  display: grid;
  gap: 5px;
  padding: 10px;
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-lg);
  background: var(--xt-bg-panel-soft);
  text-align: left;
  cursor: default;
  box-shadow: var(--xt-shadow-xs);
}

.review-home-hero__workshop-card :deep(.xt-workshop-glyph) {
  min-height: 58px;
}

.review-home-hero__workshop-card span {
  overflow: hidden;
  color: var(--xt-text);
  font-size: 13px;
  font-weight: 850;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.review-home-hero__workshop-card strong {
  color: var(--xt-text-muted);
  font-size: 12px;
  font-weight: 800;
}

.review-home-hero__workshop-card.is-active {
  border-color: var(--xt-warning-border);
  background: var(--xt-warning-light);
}

.review-home-hero__execution {
  align-content: start;
  gap: 12px;
  padding: 14px;
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-2xl);
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-md);
}

.review-home-hero__execution-head {
  gap: 6px;
}

.review-home-hero__execution-head span {
  color: var(--xt-primary);
  font-weight: 900;
}

.review-home-hero__execution-head strong {
  color: var(--xt-text);
  font-family: var(--xt-font-display);
  font-size: 19px;
  line-height: 1.35;
}

.review-factory .stat-grid {
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--xt-space-3);
}

.review-factory-detail-toggle {
  display: flex;
  justify-content: center;
}

.review-factory-detail-toggle__btn {
  min-height: 36px;
  padding: 0 16px;
  border-radius: var(--xt-radius-lg);
  border: 1px solid var(--xt-border);
  background: var(--xt-bg-panel);
  color: var(--xt-text-soft);
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
  border-color: var(--xt-primary-border);
  box-shadow: var(--xt-shadow-sm);
  background: var(--xt-bg-panel-soft);
}

.review-factory-detail-toggle__btn:focus-visible {
  outline: none;
  box-shadow: var(--app-focus-ring);
}

.review-factory .stat-card {
  padding: var(--xt-space-4);
}

.review-home-hero__metrics,
.review-home-hero__runtime {
  padding: 14px;
  border-radius: var(--xt-radius-lg);
  border: 1px solid var(--xt-border-light);
  background: var(--xt-bg-panel-soft);
  box-shadow: none;
}
.review-factory-tabs {
  border: 1px solid var(--xt-border-light);
  box-shadow: var(--xt-shadow-sm);
}

@keyframes review-factory-reveal {
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.reporting-status-table {
  border: 1px solid var(--xt-border-light);
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
  color: var(--xt-gray-600);
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
  background: var(--xt-gray-200);
  color: var(--xt-gray-700);
}

.reporting-status-pill.is-submitted,
.reporting-status-pill.is-reviewed,
.reporting-status-pill.is-auto_confirmed {
  color: var(--xt-success);
  background: var(--xt-success-light);
  border-color: var(--xt-success-border);
}

.reporting-status-pill.is-draft {
  color: var(--xt-primary);
  background: var(--xt-primary-light);
  border-color: var(--xt-primary-border);
}

.reporting-status-pill.is-unreported {
  color: var(--xt-warning);
  background: var(--xt-warning-light);
  border-color: var(--xt-warning-border);
}

.reporting-status-pill.is-late,
.reporting-status-pill.is-returned {
  color: var(--xt-danger);
  background: var(--xt-danger-light);
  border-color: var(--xt-danger-border);
}

.reporting-status-note {
  display: inline-block;
  color: var(--xt-gray-500);
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
  border-radius: var(--xt-radius-lg);
  border: 1px solid var(--xt-border-light);
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-sm);
  transition:
    transform var(--app-motion-fast) var(--app-motion-curve),
    border-color var(--app-motion-fast) ease,
    box-shadow var(--app-motion-fast) var(--app-motion-curve);
}

.history-trend-card:hover,
.archive-card:hover {
  transform: translateY(-2px);
  border-color: var(--xt-primary-border);
  box-shadow: var(--xt-shadow-md);
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
  background: var(--xt-bg-panel-muted);
}

.history-trend-card__bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: var(--xt-primary);
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
  border-color: var(--xt-primary-border);
  background: var(--xt-primary-light);
}

.review-home-tabs :deep(.el-tabs__header) {
  margin-bottom: 14px;
}

.template-empty {
  padding: 18px 16px;
  border-radius: 12px;
  border: 1px dashed var(--xt-border);
  color: var(--app-muted);
  text-align: center;
}

@media (max-width: 900px) {
  .review-home-hero__meta,
  .review-home-hero__war-room,
  .review-home-hero__grid,
  .review-factory .stat-grid {
    grid-template-columns: 1fr;
  }

  .review-home-hero__core-metrics {
    grid-template-columns: repeat(3, 1fr);
    gap: var(--xt-space-2);
  }

  .core-metric-card {
    padding: var(--xt-space-3) var(--xt-space-2);
  }

  .core-metric-card__value {
    font-size: 24px;
  }

  .review-home-hero__secondary-metrics {
    flex-direction: column;
    gap: var(--xt-space-2);
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
    font-size: 24px;
  }
}
</style>
