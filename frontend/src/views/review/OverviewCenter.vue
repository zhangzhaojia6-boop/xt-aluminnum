<template>
  <ReferencePageFrame
    module-number="01"
    title="系统总览主视图"
    :tags="['三端总览', '自动汇总', '异常处置']"
    class="review-overview-center"
    data-testid="review-overview-center"
    v-loading="loading"
  >
    <template #actions>
      <el-date-picker v-model="targetDate" type="date" value-format="YYYY-MM-DD" />
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
    </template>

    <section class="review-overview-center__command">
      <div class="review-overview-center__map">
        <XtFactoryMap
          :nodes="factoryMapNodes"
          :lines="factoryMapLines"
          :alerts="factoryMapAlerts"
          :active-key="factoryActiveKey"
        />
      </div>

      <aside class="review-overview-center__ai-manager">
        <div class="review-overview-center__ai-head">
          <span>AI 总管</span>
          <strong>预测 / 分析 / 执行</strong>
        </div>
        <p>{{ aiManagerBrief }}</p>
        <div class="review-overview-center__ai-actions">
          <button
            v-for="item in aiManagerActions"
            :key="item.key"
            type="button"
            :class="`is-${item.status}`"
            @click="go(item.routeName)"
          >
            <span>{{ item.label }}</span>
            <strong>{{ item.detail }}</strong>
          </button>
        </div>
      </aside>

      <div class="review-overview-center__rail">
        <XtExecutionRail :steps="executionSteps" :active-index="executionActiveIndex" compact />
      </div>
    </section>

    <section class="review-overview-center__kpi-grid">
      <ReferenceKpiTile
        v-for="card in overviewCards"
        :key="card.label"
        :icon="card.icon"
        :label="card.label"
        :value="card.value"
        :unit="card.unit"
        :trend="card.trend"
        :status="card.status"
      />
    </section>

    <section class="review-overview-center__main-grid">
      <ReferenceModuleCard module-number="02" title="快捷入口" density="dense">
        <div class="review-overview-center__quick-grid">
          <button
            v-for="item in quickEntries"
            :key="item.name"
            type="button"
            class="review-overview-center__quick"
            @click="go(item.name)"
          >
            <span>{{ item.label }}</span>
            <strong>{{ item.hint }}</strong>
          </button>
        </div>
      </ReferenceModuleCard>
    </section>

    <section class="review-overview-center__module-grid">
      <XtModuleTile
        v-for="item in referenceModules"
        :key="item.number"
        :module="item"
        :status="item.status"
        :status-text="item.statusLabel"
        :metrics="moduleMetrics(item)"
        action-label="进入"
        compact
        @action="openReferenceModule"
      />
    </section>

    <section class="review-overview-center__ai-grid">
      <ReferenceModuleCard module-number="11" title="AI 今日摘要" density="dense">
        <ul class="review-overview-center__list">
          <li v-for="item in aiTodaySummary" :key="item">{{ item }}</li>
        </ul>
      </ReferenceModuleCard>

      <ReferenceModuleCard module-number="09" title="AI 风险摘要" density="dense">
        <ul class="review-overview-center__list">
          <li v-for="item in aiRiskSummary" :key="item">{{ item }}</li>
        </ul>
      </ReferenceModuleCard>

      <ReferenceModuleCard module-number="05" title="生产系统在制料" density="dense" data-testid="overview-mes-wip">
        <div class="review-overview-center__wip">
          <div class="review-overview-center__wip-row">
            <span>在制料总计</span>
            <strong>{{ mesWipSummary.wipTotalTon }} t</strong>
          </div>
          <div class="review-overview-center__wip-row">
            <span>当日投料量</span>
            <strong>{{ mesWipSummary.dailyFeedTon }} t</strong>
          </div>
          <div class="review-overview-center__wip-meta">
            <span class="source-badge is-fallback">fallback</span>
            <button type="button" class="review-overview-center__wip-link" @click="go('review-brain-center')">查看详情</button>
          </div>
        </div>
      </ReferenceModuleCard>
    </section>
  </ReferencePageFrame>
</template>

<script setup>
import dayjs from 'dayjs'
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import ReferenceKpiTile from '../../components/reference/ReferenceKpiTile.vue'
import ReferenceModuleCard from '../../components/reference/ReferenceModuleCard.vue'
import ReferencePageFrame from '../../components/reference/ReferencePageFrame.vue'
import ReferenceStatusTag from '../../components/reference/ReferenceStatusTag.vue'
import { XtExecutionRail, XtFactoryMap, XtModuleTile } from '../../components/xt'
import { fetchDeliveryStatus, fetchFactoryDashboard } from '../../api/dashboard'
import { mesWipSnapshotMock } from '../../mocks/centerMockData.js'
import { formatDeliveryMissingSteps, formatNumber } from '../../utils/display'

const router = useRouter()
const targetDate = ref(dayjs().format('YYYY-MM-DD'))
const loading = ref(false)
const dashboard = ref({})
const delivery = ref({})

const productionLines = [
  { name: '铸轧区', status: 'success' },
  { name: '精整区', status: 'success' },
  { name: '热轧区', status: 'warning' },
  { name: '拉矫区', status: 'success' },
  { name: '成品库', status: 'success' }
]

const quickEntries = [
  { name: 'factory-dashboard', label: '看板', hint: '厂级 / 车间' },
  { name: 'review-task-center', label: '审阅', hint: '待审任务' },
  { name: 'review-report-center', label: '日报', hint: '交付与发布' },
  { name: 'review-quality-center', label: '质量', hint: '告警与处理' },
  { name: 'review-cost-accounting', label: '成本', hint: '策略核算' },
  { name: 'review-brain-center', label: 'AI', hint: '摘要与问答' },
  { name: 'admin-ingestion-center', label: '接入', hint: '导入 / 映射' },
  { name: 'admin-ops-reliability', label: '运维', hint: '健康与探针' }
]

const referenceModules = [
  { number: '01', title: '系统总览主视图', shortTitle: '总览', subtitle: '全局链路', owner: '审阅端', variant: 'overview', routeName: 'review-overview-home', status: 'success', statusLabel: '在线' },
  { number: '02', title: '登录与角色入口', shortTitle: '入口', subtitle: '角色分流', owner: '公共入口', variant: 'entry', routeName: 'login', status: 'success', statusLabel: '在线' },
  { number: '03', title: '独立填报端', shortTitle: '填报端', subtitle: '手机优先', owner: '录入端', variant: 'entry', routeName: 'mobile-entry', status: 'success', statusLabel: '在线' },
  { number: '04', title: '填报流程页', shortTitle: '流程页', subtitle: '一岗一表', owner: '录入端', variant: 'entry', routeName: 'mobile-entry', status: 'success', statusLabel: '在线' },
  { number: '05', title: '工厂作业看板', shortTitle: '工厂', subtitle: '厂级作战图', owner: '审阅端', variant: 'factory', routeName: 'factory-dashboard', status: 'success', statusLabel: '在线' },
  { number: '06', title: '数据接入与字段映射中心', shortTitle: '接入', subtitle: '字段映射', owner: '管理端', variant: 'ingestion', routeName: 'admin-ingestion-center', status: 'warning', statusLabel: '改造中' },
  { number: '07', title: '审阅中心', shortTitle: '审阅', subtitle: '异常处置', owner: '审阅端', variant: 'review', routeName: 'review-task-center', status: 'success', statusLabel: '在线' },
  { number: '08', title: '日报与交付中心', shortTitle: '日报', subtitle: '自动交付', owner: '审阅端', variant: 'report', routeName: 'review-report-center', status: 'success', statusLabel: '在线' },
  { number: '09', title: '质量与告警中心', shortTitle: '质量', subtitle: '阈值预警', owner: '审阅端', variant: 'quality', routeName: 'review-quality-center', status: 'success', statusLabel: '在线' },
  { number: '10', title: '成本核算与效益中心', shortTitle: '成本', subtitle: '收益核算', owner: '审阅端', variant: 'cost', routeName: 'review-cost-accounting', status: 'success', statusLabel: '在线' },
  { number: '11', title: 'AI 总控中心', shortTitle: 'AI 总管', subtitle: '预测执行', owner: '审阅端', variant: 'brain', routeName: 'review-brain-center', status: 'success', statusLabel: '在线' },
  { number: '12', title: '系统运维与观测', shortTitle: '运维', subtitle: '健康探针', owner: '管理端', variant: 'ops', routeName: 'admin-ops-reliability', status: 'warning', statusLabel: '改造中' },
  { number: '13', title: '权限与治理中心', shortTitle: '治理', subtitle: '角色隔离', owner: '管理端', variant: 'governance', routeName: 'admin-governance-center', status: 'warning', statusLabel: '改造中' },
  { number: '14', title: '主数据与模板中心', shortTitle: '主数据', subtitle: '车间模板', owner: '管理端', variant: 'master', routeName: 'admin-master-workshop', status: 'warning', statusLabel: '改造中' }
]

const overviewCards = computed(() => {
  const leader = dashboard.value.leader_metrics || {}
  const runtimeTrace = dashboard.value.runtime_trace || {}
  const activeLines = Number(runtimeTrace?.source_lanes?.length || 0)
  const delivered = Number(delivery.value.reports_published_count || 0)
  const orderRate = Number(leader.order_completion_rate ?? dashboard.value.order_completion_rate ?? 0)
  const yieldRate = Number(leader.comprehensive_yield_rate ?? dashboard.value.comprehensive_yield_rate ?? 0)
  return [
    { label: '今日产量', value: formatNumber(leader.today_total_output), unit: '吨', trend: '+8.6%', status: 'success', icon: '产' },
    { label: '订单达成率', value: formatNumber(orderRate, 2), unit: '%', trend: '+2.1%', status: 'success', icon: '单' },
    { label: '综合成品率', value: formatNumber(yieldRate, 2), unit: '%', trend: '+1.3%', status: 'success', icon: '品' },
    { label: '运行产线数', value: String(activeLines || 0), unit: '条', trend: '在线', status: 'success', icon: '线' },
    { label: '异常数量', value: String(abnormalCount.value || 0), unit: '项', trend: '待处置', status: abnormalCount.value ? 'danger' : 'success', icon: '异' },
    { label: '待审数量', value: String(pendingReviewCount.value || 0), unit: '项', trend: '待审', status: pendingReviewCount.value ? 'warning' : 'success', icon: '审' },
    { label: '已交付数量', value: String(delivered || 0), unit: '份', trend: '今日', status: 'success', icon: '报' }
  ]
})

const exceptionCounts = computed(() => {
  const exceptionLane = dashboard.value.exception_lane || {}
  return {
    unreported: Number(exceptionLane.unreported_shift_count || 0),
    returned: Number(exceptionLane.returned_shift_count || 0),
    mobile: Number(exceptionLane.mobile_exception_count || 0),
    reconciliation: Number(exceptionLane.reconciliation_open_count || 0),
    pendingPublish: Number(exceptionLane.pending_report_publish_count || 0),
    late: Number(exceptionLane.reminder_late_count || 0)
  }
})

const abnormalCount = computed(() => exceptionCounts.value.mobile + exceptionCounts.value.returned)
const pendingReviewCount = computed(() => exceptionCounts.value.pendingPublish + exceptionCounts.value.reconciliation)
const deliveryMissingSteps = computed(() => formatDeliveryMissingSteps(delivery.value.missing_steps || []))

const factoryActiveKey = computed(() => {
  if (exceptionCounts.value.unreported || exceptionCounts.value.mobile || exceptionCounts.value.returned) return 'entry'
  if (exceptionCounts.value.reconciliation) return 'ai'
  if (!delivery.value.delivery_ready) return 'publish'
  return 'ai'
})

const factoryMapNodes = computed(() => [
  {
    key: 'entry',
    label: '岗位直录',
    short: '录',
    status: exceptionCounts.value.unreported || exceptionCounts.value.mobile ? 'warning' : 'normal',
    x: '13%',
    y: '32%'
  },
  {
    key: 'casting',
    label: '铸锭试点',
    short: '锭',
    status: abnormalCount.value ? 'warning' : 'normal',
    x: '36%',
    y: '66%'
  },
  {
    key: 'sync',
    label: '生产系统同步',
    short: '数',
    status: 'normal',
    x: '58%',
    y: '35%'
  },
  {
    key: 'ai',
    label: 'AI 总管',
    short: 'AI',
    status: pendingReviewCount.value ? 'warning' : 'normal',
    x: '75%',
    y: '57%'
  },
  {
    key: 'publish',
    label: '日报发布',
    short: '报',
    status: delivery.value.delivery_ready ? 'normal' : 'warning',
    x: '88%',
    y: '27%'
  }
])

const factoryMapLines = computed(() => {
  const lanes = dashboard.value.runtime_trace?.source_lanes || []
  if (lanes.length) {
    return lanes.slice(0, 5).map((lane, index) => ({
      key: lane.key || `${lane.label || 'lane'}-${index}`,
      label: lane.label || lane.key || `数据源 ${index + 1}`,
      value: lane.stage_label || lane.status_label || '同步',
      status: toFactoryStatus(lane.status)
    }))
  }
  return productionLines.map((line) => ({
    key: line.name,
    label: line.name,
    value: line.status === 'warning' ? '关注' : '在线',
    status: toFactoryStatus(line.status)
  }))
})

const factoryMapAlerts = computed(() => {
  const alerts = [
    { key: 'unreported', label: '缺报班次', value: exceptionCounts.value.unreported, status: 'warning' },
    { key: 'returned', label: '退回补录', value: exceptionCounts.value.returned, status: 'danger' },
    { key: 'mobile', label: '字段异常', value: exceptionCounts.value.mobile, status: 'danger' },
    { key: 'reconciliation', label: '差异待核', value: exceptionCounts.value.reconciliation, status: 'warning' },
    { key: 'publish', label: '日报待发', value: exceptionCounts.value.pendingPublish, status: 'warning' }
  ]
  return alerts.filter((item) => Number(item.value || 0) > 0).slice(0, 4)
})

const executionSteps = computed(() => {
  const activeLines = dashboard.value.runtime_trace?.source_lanes?.length || factoryMapLines.value.length
  const missingText = deliveryMissingSteps.value.join('、')
  return [
    { key: 'discover', label: '发现', detail: `${activeLines || 0} 条现场数据源接入`, status: 'done' },
    {
      key: 'judge',
      label: '判断',
      detail: abnormalCount.value ? `${abnormalCount.value} 项异常进入规则判定` : '字段与阈值校验通过',
      status: abnormalCount.value ? 'warning' : 'done'
    },
    {
      key: 'execute',
      label: '执行',
      detail: exceptionCounts.value.unreported ? `催报 ${exceptionCounts.value.unreported} 个班次` : '自动汇总与补差动作就绪',
      status: exceptionCounts.value.unreported || exceptionCounts.value.returned ? 'running' : 'done'
    },
    {
      key: 'audit',
      label: '留痕',
      detail: pendingReviewCount.value ? `${pendingReviewCount.value} 项待闭环留痕` : '处理链路已写入审计',
      status: pendingReviewCount.value ? 'warning' : 'done'
    },
    {
      key: 'publish',
      label: '发布',
      detail: delivery.value.delivery_ready ? `已交付 ${delivery.value.reports_published_count || 0} 份日报` : `缺口：${missingText || '等待交付条件'}`,
      status: delivery.value.delivery_ready ? 'done' : 'warning'
    }
  ]
})

const executionActiveIndex = computed(() => {
  const index = executionSteps.value.findIndex((item) => ['warning', 'danger', 'running'].includes(item.status))
  return index >= 0 ? index : executionSteps.value.length - 1
})

const aiManagerBrief = computed(() => {
  if (factoryMapAlerts.value.length) return `已发现 ${factoryMapAlerts.value.length} 类风险，优先处理会阻塞日报的缺报、差异和退回。`
  if (delivery.value.delivery_ready) return '今日采集、汇总、交付链路顺畅，AI 继续盯守波动与异常趋势。'
  return '日报仍有交付缺口，AI 正按缺口清单推进自动催报、核对和发布准备。'
})

const aiManagerActions = computed(() => [
  {
    key: 'predict',
    label: '预测',
    detail: aiRiskSummary.value[0] || '当前无突出风险。',
    status: factoryMapAlerts.value.length ? 'warning' : 'normal',
    routeName: 'review-quality-center'
  },
  {
    key: 'analysis',
    label: '分析',
    detail: aiTodaySummary.value[0],
    status: 'normal',
    routeName: 'factory-dashboard'
  },
  {
    key: 'execute',
    label: '执行',
    detail: delivery.value.delivery_ready ? '保持自动发布节奏' : '进入 AI 工作台生成动作',
    status: delivery.value.delivery_ready ? 'normal' : 'warning',
    routeName: 'review-brain-center'
  }
])

const aiTodaySummary = computed(() => {
  const leader = dashboard.value.leader_metrics || {}
  const text = dashboard.value.leader_summary?.summary_text
  const output = formatNumber(leader.today_total_output)
  const yieldRate = formatNumber(leader.yield_rate ?? leader.comprehensive_yield_rate, 2)
  return [
    text || `今日产量 ${output} 吨，综合成品率 ${yieldRate}%。`,
    `已交付 ${delivery.value.reports_published_count || 0} 份，待审 ${overviewCards.value.find((item) => item.label === '待审数量')?.value || 0} 项。`
  ]
})

const aiRiskSummary = computed(() => {
  const exceptionLane = dashboard.value.exception_lane || {}
  const risks = []
  if (Number(exceptionLane.unreported_shift_count || 0) > 0) {
    risks.push(`缺报班次 ${exceptionLane.unreported_shift_count} 项，优先催报。`)
  }
  if (Number(exceptionLane.returned_shift_count || 0) > 0) {
    risks.push(`退回班次 ${exceptionLane.returned_shift_count} 项，需补异常说明。`)
  }
  if (Number(exceptionLane.reconciliation_open_count || 0) > 0) {
    risks.push(`差异待处理 ${exceptionLane.reconciliation_open_count} 项，建议先看高风险差异。`)
  }
  if (!risks.length) risks.push('当前无突出风险，保持日报交付节奏。')
  return risks.slice(0, 3)
})

const mesWipSummary = mesWipSnapshotMock.summary

function toFactoryStatus(status) {
  const value = String(status || '').toLowerCase()
  if (['danger', 'error', 'failed', 'blocked', 'returned', 'late'].includes(value)) return 'danger'
  if (['warning', 'alert', 'pending', 'fallback', 'mixed', 'unreported'].includes(value)) return 'warning'
  return 'normal'
}

function go(routeName) {
  router.push({ name: routeName })
}

function openReferenceModule(item) {
  if (item?.routeName) go(item.routeName)
}

function moduleMetrics(item) {
  return [
    { label: '归属', value: item.owner },
    { label: '编号', value: item.number },
    { label: '状态', value: item.statusLabel }
  ]
}

async function load() {
  loading.value = true
  try {
    const [dashboardPayload, deliveryPayload] = await Promise.all([
      fetchFactoryDashboard({ target_date: targetDate.value }),
      fetchDeliveryStatus({ target_date: targetDate.value })
    ])
    dashboard.value = dashboardPayload || {}
    delivery.value = deliveryPayload || {}
  } finally {
    loading.value = false
  }
}

watch(targetDate, load)
onMounted(load)
</script>

<style scoped>
.review-overview-center__kpi-grid,
.review-overview-center__module-grid,
.review-overview-center__quick-grid,
.review-overview-center__ai-grid,
.review-overview-center__main-grid,
.review-overview-center__command,
.review-overview-center__ai-actions {
  display: grid;
  gap: 10px;
}

.review-overview-center__command {
  grid-template-columns: minmax(0, 1.45fr) minmax(320px, 0.55fr);
  align-items: stretch;
  gap: 14px;
}

.review-overview-center__map {
  min-width: 0;
}

.review-overview-center__ai-manager {
  min-width: 0;
  display: grid;
  align-content: start;
  gap: 14px;
  padding: 18px;
  overflow: hidden;
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-2xl);
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-md);
}

.review-overview-center__ai-head {
  display: grid;
  gap: 6px;
}

.review-overview-center__ai-head span {
  color: var(--xt-primary);
  font-size: 12px;
  font-weight: 900;
}

.review-overview-center__ai-head strong {
  color: var(--xt-text);
  font-family: var(--xt-font-display);
  font-size: 25px;
  line-height: 1.16;
}

.review-overview-center__ai-manager p {
  margin: 0;
  color: var(--xt-text-secondary);
  font-size: 14px;
  line-height: 1.65;
}

.review-overview-center__ai-actions button {
  min-width: 0;
  display: grid;
  gap: 6px;
  padding: 12px;
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-xl);
  background: var(--xt-bg-panel-soft);
  text-align: left;
  cursor: pointer;
  transition:
    transform var(--xt-motion-fast) var(--xt-ease),
    border-color var(--xt-motion-fast) ease,
    box-shadow var(--xt-motion-fast) var(--xt-ease);
}

.review-overview-center__ai-actions button:active {
  transform: scale(0.98);
}

@media (hover: hover) {
  .review-overview-center__ai-actions button:hover {
    transform: translateY(-1px);
    border-color: rgba(11, 99, 246, 0.2);
    box-shadow: var(--xt-shadow-sm);
  }
}

.review-overview-center__ai-actions button.is-warning {
  border-color: rgba(183, 121, 31, 0.22);
  background: var(--xt-warning-light);
}

.review-overview-center__ai-actions span {
  color: var(--xt-text-muted);
  font-size: 12px;
  font-weight: 900;
}

.review-overview-center__ai-actions strong {
  overflow: hidden;
  color: var(--xt-text);
  font-size: 13px;
  line-height: 1.45;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.review-overview-center__rail {
  grid-column: 1 / -1;
  min-width: 0;
}

.review-overview-center__kpi-grid {
  grid-template-columns: repeat(7, minmax(120px, 1fr));
}

.review-overview-center__main-grid {
  grid-template-columns: 1fr;
}

.review-overview-center__quick-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.review-overview-center__module-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.review-overview-center__ai-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.review-overview-center__wip {
  display: grid;
  gap: 10px;
}

.review-overview-center__wip-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.review-overview-center__wip-row span {
  color: var(--text-muted);
  font-size: 13px;
}

.review-overview-center__wip-row strong {
  color: var(--text-main);
  font-family: var(--font-number);
  font-size: 20px;
  font-weight: 700;
}

.review-overview-center__wip-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding-top: 4px;
}

.review-overview-center__wip-link {
  border: 0;
  background: none;
  color: var(--primary);
  font-size: 13px;
  cursor: pointer;
  padding: 0;
}

.review-overview-center__wip-link:hover {
  text-decoration: underline;
}

.review-overview-center__quick {
  border: 1px solid var(--reference-line);
  border-radius: 14px;
  background: rgba(248, 251, 255, 0.94);
}

.review-overview-center__quick {
  min-height: 72px;
  padding: 10px;
  display: grid;
  gap: 4px;
  text-align: left;
  cursor: pointer;
}

.review-overview-center__quick span,
.review-overview-center__module-card span {
  color: var(--text-secondary);
  font-size: 12px;
  font-weight: 800;
}

.review-overview-center__quick strong {
  color: var(--text-main);
  font-size: 15px;
}

.review-overview-center__module-card {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  align-items: center;
}

.review-overview-center__list {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 8px;
}

@media (max-width: 1320px) {
  .review-overview-center__kpi-grid,
  .review-overview-center__module-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .review-overview-center__command,
  .review-overview-center__main-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 780px) {
  .review-overview-center__kpi-grid,
  .review-overview-center__module-grid,
  .review-overview-center__quick-grid,
  .review-overview-center__ai-grid {
    grid-template-columns: 1fr;
  }

  .review-overview-center__ai-head strong {
    font-size: 21px;
  }
}
</style>
