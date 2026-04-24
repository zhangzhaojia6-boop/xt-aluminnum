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
      <ReferenceModuleCard module-number="01" title="生产全景" density="dense">
        <ReferenceFlowGraphic :nodes="flowNodes" :active-index="3" />
        <div class="review-overview-center__line-map">
          <span v-for="line in productionLines" :key="line.name" :class="`is-${line.status}`">
            {{ line.name }}
          </span>
        </div>
      </ReferenceModuleCard>

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
      <ReferenceModuleCard
        v-for="item in referenceModules"
        :key="item.number"
        :module-number="item.number"
        :title="item.title"
        density="dense"
      >
        <div class="review-overview-center__module-card">
          <ReferenceStatusTag :status="item.status" :label="item.statusLabel" />
          <span>{{ item.owner }}</span>
        </div>
      </ReferenceModuleCard>
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
    </section>
  </ReferencePageFrame>
</template>

<script setup>
import dayjs from 'dayjs'
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import ReferenceFlowGraphic from '../../components/reference/ReferenceFlowGraphic.vue'
import ReferenceKpiTile from '../../components/reference/ReferenceKpiTile.vue'
import ReferenceModuleCard from '../../components/reference/ReferenceModuleCard.vue'
import ReferencePageFrame from '../../components/reference/ReferencePageFrame.vue'
import ReferenceStatusTag from '../../components/reference/ReferenceStatusTag.vue'
import { fetchDeliveryStatus, fetchFactoryDashboard } from '../../api/dashboard'
import { formatNumber } from '../../utils/display'

const router = useRouter()
const targetDate = ref(dayjs().format('YYYY-MM-DD'))
const loading = ref(false)
const dashboard = ref({})
const delivery = ref({})

const flowNodes = [
  { key: 'entry', title: '现场直录', status: 'success' },
  { key: 'merge', title: '自动汇总', status: 'success' },
  { key: 'review', title: '异常处置', status: 'warning' },
  { key: 'delivery', title: '日报交付', status: 'success' }
]

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
  { number: '01', title: '系统总览主视图', owner: '审阅端', status: 'success', statusLabel: '已接入' },
  { number: '02', title: '登录与角色入口', owner: '公共入口', status: 'success', statusLabel: '已接入' },
  { number: '03', title: '独立填报端', owner: '录入端', status: 'success', statusLabel: '已接入' },
  { number: '04', title: '填报流程页', owner: '录入端', status: 'success', statusLabel: '已接入' },
  { number: '05', title: '工厂作业看板', owner: '审阅端', status: 'success', statusLabel: '已接入' },
  { number: '06', title: '数据接入与字段映射中心', owner: '管理端', status: 'warning', statusLabel: '改造中' },
  { number: '07', title: '审阅中心', owner: '审阅端', status: 'success', statusLabel: '已接入' },
  { number: '08', title: '日报与交付中心', owner: '审阅端', status: 'success', statusLabel: '已接入' },
  { number: '09', title: '质量与告警中心', owner: '审阅端', status: 'success', statusLabel: '已接入' },
  { number: '10', title: '成本核算与效益中心', owner: '审阅端', status: 'success', statusLabel: '已接入' },
  { number: '11', title: 'AI 总大脑中心', owner: '审阅端', status: 'success', statusLabel: '已接入' },
  { number: '12', title: '系统运维与可观测', owner: '管理端', status: 'warning', statusLabel: '改造中' },
  { number: '13', title: '权限治理中心', owner: '管理端', status: 'warning', statusLabel: '改造中' },
  { number: '14', title: '主数据与模板中心', owner: '管理端', status: 'warning', statusLabel: '改造中' },
  { number: '15', title: '响应式录入体验', owner: '全局验收', status: 'success', statusLabel: '替代预览' },
  { number: '16', title: '路线图与下一步', owner: '管理端', status: 'pending', statusLabel: '排期中' }
]

const overviewCards = computed(() => {
  const leader = dashboard.value.leader_metrics || {}
  const exceptionLane = dashboard.value.exception_lane || {}
  const runtimeTrace = dashboard.value.runtime_trace || {}
  const activeLines = Number(runtimeTrace?.source_lanes?.length || 0)
  const abnormalCount = Number(exceptionLane.mobile_exception_count || 0) + Number(exceptionLane.returned_shift_count || 0)
  const pendingReview = Number(exceptionLane.pending_report_publish_count || 0) + Number(exceptionLane.reconciliation_open_count || 0)
  const delivered = Number(delivery.value.reports_published_count || 0)
  const orderRate = Number(leader.order_completion_rate ?? dashboard.value.order_completion_rate ?? 0)
  const yieldRate = Number(leader.comprehensive_yield_rate ?? dashboard.value.comprehensive_yield_rate ?? 0)
  return [
    { label: '今日产量', value: formatNumber(leader.today_total_output), unit: '吨', trend: '+8.6%', status: 'success', icon: '产' },
    { label: '订单达成率', value: formatNumber(orderRate, 2), unit: '%', trend: '+2.1%', status: 'success', icon: '单' },
    { label: '综合成品率', value: formatNumber(yieldRate, 2), unit: '%', trend: '+1.3%', status: 'success', icon: '品' },
    { label: '运行产线数', value: String(activeLines || 0), unit: '条', trend: '在线', status: 'success', icon: '线' },
    { label: '异常数量', value: String(abnormalCount || 0), unit: '项', trend: '待处置', status: abnormalCount ? 'danger' : 'success', icon: '异' },
    { label: '待审数量', value: String(pendingReview || 0), unit: '项', trend: '待审', status: pendingReview ? 'warning' : 'success', icon: '审' },
    { label: '已交付数量', value: String(delivered || 0), unit: '份', trend: '今日', status: 'success', icon: '报' }
  ]
})

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

function go(routeName) {
  router.push({ name: routeName })
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
.review-overview-center__main-grid {
  display: grid;
  gap: 10px;
}

.review-overview-center__kpi-grid {
  grid-template-columns: repeat(7, minmax(120px, 1fr));
}

.review-overview-center__main-grid {
  grid-template-columns: minmax(0, 1.1fr) minmax(360px, 0.9fr);
}

.review-overview-center__quick-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.review-overview-center__module-grid {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.review-overview-center__ai-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.review-overview-center__line-map {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 8px;
  margin-top: 10px;
}

.review-overview-center__line-map span,
.review-overview-center__quick {
  border: 1px solid var(--reference-line);
  border-radius: 14px;
  background: rgba(248, 251, 255, 0.94);
}

.review-overview-center__line-map span {
  min-height: 42px;
  display: grid;
  place-items: center;
  color: #0f172a;
  font-size: 13px;
  font-weight: 900;
}

.review-overview-center__line-map span.is-warning {
  color: #b45309;
  background: rgba(254, 243, 199, 0.88);
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
  color: #64748b;
  font-size: 12px;
  font-weight: 800;
}

.review-overview-center__quick strong {
  color: #0f172a;
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

  .review-overview-center__main-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 780px) {
  .review-overview-center__kpi-grid,
  .review-overview-center__module-grid,
  .review-overview-center__quick-grid,
  .review-overview-center__ai-grid,
  .review-overview-center__line-map {
    grid-template-columns: 1fr;
  }
}
</style>
