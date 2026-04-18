<template>
  <div class="page-stack" data-testid="factory-dashboard">
    <div class="page-header">
      <div>
        <h1>厂长驾驶舱</h1>
        <p>聚焦岗位直录、智能体联动、月累计产量与异常闭环，前台不再铺陈 MES 接入过程。</p>
      </div>
      <div class="header-actions">
        <el-date-picker v-model="targetDate" type="date" value-format="YYYY-MM-DD" />
        <span class="note">数据更新于 {{ lastRefreshLabel }}</span>
      </div>
    </div>

    <section class="dashboard-command panel" v-loading="loading">
      <div class="dashboard-command__hero">
        <div class="dashboard-command__copy">
          <span>智能体联动</span>
          <h2>把原始值收口到一套运行壳层里，让采集清洗小队和分析决策小队像专业经理班子一样接力。</h2>
          <p>这一阶段先守住日产量、入库、发货、合同和能耗，再往后接成本核算、排产规划和经营自动化。</p>
          <div class="dashboard-command__pills">
            <span v-for="pill in commandPills" :key="pill">{{ pill }}</span>
          </div>
        </div>
        <div class="dashboard-command__rail">
          <div class="dashboard-hero__metric">
            <span>今日产量</span>
            <strong>{{ formatNumber(leaderMetrics.today_total_output) }}</strong>
          </div>
          <div class="dashboard-hero__metric">
            <span>月累计产量</span>
            <strong>{{ formatNumber(monthToDateOutput) }}</strong>
          </div>
          <div class="dashboard-hero__metric">
            <span>数据留存</span>
            <strong>{{ retentionSummary }}</strong>
          </div>
        </div>
      </div>

      <div class="agent-orchestra-grid">
        <article class="agent-orchestra-card">
          <div class="agent-orchestra-card__top">
            <span>采集清洗小队</span>
            <strong>把主操、成品库、水电气、计划科原始值先接住</strong>
          </div>
          <p>负责字段校验、缺报提醒、异常退回和岗位归档，让数据先变干净，再进入经营视图。</p>
          <div class="agent-orchestra-card__stats">
            <div v-for="item in collectionSquadStats" :key="item.label" class="agent-orchestra-stat">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </div>
          </div>
        </article>

        <article class="agent-orchestra-card is-accent">
          <div class="agent-orchestra-card__top">
            <span>分析决策小队</span>
            <strong>把日数据转成摘要、预警、趋势和归档</strong>
          </div>
          <p>负责驾驶舱、日报、异常闭环和历史留存，让领导直接看结果，不再等人工统计拼总表。</p>
          <div class="agent-orchestra-card__stats">
            <div v-for="item in decisionSquadStats" :key="item.label" class="agent-orchestra-stat">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </div>
          </div>
        </article>
      </div>

      <div class="agent-flow">
        <div v-for="step in pipelineSteps" :key="step.title" class="agent-flow__step">
          <span>{{ step.stage }}</span>
          <strong>{{ step.title }}</strong>
          <p>{{ step.summary }}</p>
        </div>
      </div>
    </section>

    <div class="dashboard-secondary-grid" v-loading="loading">
      <el-card class="panel">
        <template #header>今日摘要</template>
        <div class="text-summary">{{ leaderSummaryText }}</div>
      </el-card>

      <el-card class="panel">
        <template #header>交付与闭环</template>
        <div class="ops-digest-grid">
          <div class="ops-digest-card">
            <span>交付状态</span>
            <strong>{{ delivery.delivery_ready ? '可交付' : '未就绪' }}</strong>
            <p>当前缺口：{{ formatDeliveryMissingSteps(delivery.missing_steps).join('；') }}</p>
          </div>
          <div class="ops-digest-card">
            <span>最新刷新</span>
            <strong>{{ lastRefreshLabel }}</strong>
            <p>当前驾驶舱按 30 秒自动刷新，保持日内运行态。</p>
          </div>
        </div>
      </el-card>
    </div>

    <div class="stat-grid" v-loading="loading">
      <div class="stat-card">
        <div class="stat-label">今日产量</div>
        <div class="stat-value">{{ formatNumber(leaderMetrics.today_total_output) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">估算收入</div>
        <div class="stat-value">{{ formatMoney(leaderMetrics.estimated_revenue) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">估算成本</div>
        <div class="stat-value">{{ formatMoney(leaderMetrics.estimated_cost) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">估算毛差</div>
        <div class="stat-value">{{ formatMoney(leaderMetrics.estimated_margin) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">单吨能耗</div>
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
        <div class="stat-value">{{ formatNumber(leaderMetrics.shipment_weight) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">入库面积</div>
        <div class="stat-value">{{ formatNumber(leaderMetrics.storage_inbound_area) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">合同量</div>
        <div class="stat-value">{{ formatNumber(leaderMetrics.contract_weight) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">活跃合同</div>
        <div class="stat-value">{{ leaderMetrics.active_contract_count ?? 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">停滞合同</div>
        <div class="stat-value">{{ leaderMetrics.stalled_contract_count ?? 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">活跃卷数</div>
        <div class="stat-value">{{ leaderMetrics.active_coil_count ?? 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">成品率</div>
        <div class="stat-value">{{ formatNumber(leaderMetrics.yield_rate) }}%</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">出勤</div>
        <div class="stat-value">{{ leaderMetrics.total_attendance ?? 0 }}</div>
      </div>
      <div class="stat-card" data-testid="delivery-ready-card">
        <div class="stat-label">交付状态</div>
        <div class="stat-value">{{ delivery.delivery_ready ? '可交付' : '未就绪' }}</div>
      </div>
    </div>

    <el-card class="panel" v-loading="loading">
      <template #header>今日上报状态</template>
      <div class="reporting-status-grid">
        <div
          v-for="item in data.workshop_reporting_status || []"
          :key="item.workshop_id"
          class="reporting-status-card"
        >
          <div class="reporting-status-name">{{ item.workshop_name }}</div>
          <el-tag :type="reportStatusTagType(item.report_status)" effect="plain" size="large">
            {{ reportStatusLabel(item.report_status) }}
          </el-tag>
          <div v-if="item.output_weight != null" class="reporting-status-weight">
            {{ formatNumber(item.output_weight) }} 吨
          </div>
        </div>
        <div v-if="!(data.workshop_reporting_status || []).length" class="template-empty">
          暂无车间数据
        </div>
      </div>
    </el-card>

    <el-card class="panel" v-loading="loading">
      <template #header>今日关注</template>
      <el-descriptions :column="4" border>
        <el-descriptions-item label="未报班次">{{ data.exception_lane?.unreported_shift_count ?? 0 }}</el-descriptions-item>
        <el-descriptions-item label="迟报班次">{{ data.exception_lane?.reminder_late_count ?? 0 }}</el-descriptions-item>
        <el-descriptions-item label="待处理差异">{{ data.exception_lane?.reconciliation_open_count ?? 0 }}</el-descriptions-item>
        <el-descriptions-item label="待处理日报">{{ data.exception_lane?.pending_report_publish_count ?? 0 }}</el-descriptions-item>
      </el-descriptions>
      <div class="note" data-testid="delivery-missing-steps">交付缺口：{{ formatDeliveryMissingSteps(delivery.missing_steps).join('；') }}</div>
    </el-card>

    <el-card class="panel" v-loading="loading">
      <template #header>近 7 日留存趋势</template>
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
    </el-card>

    <el-card class="panel" v-loading="loading">
      <template #header>数据留存与归档</template>
      <div class="archive-grid">
        <div class="archive-card">
          <span>月度归档</span>
          <strong>{{ formatNumber(monthArchive.total_output) }} 吨</strong>
          <p>已留存 {{ monthArchive.reported_days ?? 0 }} 天，日均 {{ formatNumber(monthArchive.average_daily_output) }} 吨。</p>
        </div>
        <div class="archive-card">
          <span>年度归档</span>
          <strong>{{ formatNumber(yearArchive.total_output) }} 吨</strong>
          <p>已覆盖 {{ yearArchive.active_months ?? 0 }} 个月，月均 {{ formatNumber(yearArchive.average_monthly_output) }} 吨。</p>
        </div>
        <div class="archive-card archive-card--accent">
          <span>当日留存</span>
          <strong>{{ targetDate }}</strong>
          <p>原始值、摘要、趋势快照都按天沉淀，后续可直接接月结、年结、成本和排产。</p>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'

import { fetchDeliveryStatus, fetchFactoryDashboard } from '../../api/dashboard'
import { formatDeliveryMissingSteps, formatNumber } from '../../utils/display'

function reportStatusLabel(status) {
  const map = {
    submitted: '已上报',
    reviewed: '已接收',
    auto_confirmed: '自动确认',
    returned: '已退回',
    draft: '填报中',
    unreported: '未上报',
    late: '迟报'
  }
  return map[status] || status || '未上报'
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

const targetDate = ref(dayjs().format('YYYY-MM-DD'))
const loading = ref(false)
const data = ref({})
const delivery = ref({})
const lastRefreshAt = ref('')
const leaderMetrics = computed(() => data.value.leader_metrics || {})
const historyDigest = computed(() => data.value.history_digest || {})
const dailySnapshots = computed(() => historyDigest.value.daily_snapshots || [])
const monthArchive = computed(() => historyDigest.value.month_archive || {})
const yearArchive = computed(() => historyDigest.value.year_archive || {})
const maxTrendOutput = computed(() => Math.max(...dailySnapshots.value.map((item) => Number(item.output_weight) || 0), 1))
const commandPills = computed(() => ['主操直录', '专项 owner 补录', '企业微信主入口', '自动归档', '自动预警'])
const monthToDateOutput = computed(() => data.value.month_to_date_output ?? data.value.leader_metrics?.month_to_date_output ?? null)
const leaderSummaryText = computed(() =>
  data.value.leader_summary?.summary_text || data.value.final_text_summary || data.value.boss_summary || '暂无摘要。'
)
const lastRefreshLabel = computed(() => (lastRefreshAt.value ? dayjs(lastRefreshAt.value).format('HH:mm:ss') : '--:--:--'))
const retentionSummary = computed(() => `${monthArchive.value.reported_days ?? 0} 天归档`)
const collectionSquadStats = computed(() => [
  { label: '已报率', value: `${data.value.mobile_reporting_summary?.reporting_rate ?? 0}%` },
  { label: '未报班次', value: `${data.value.exception_lane?.unreported_shift_count ?? 0} 个` },
  { label: '退回班次', value: `${data.value.exception_lane?.returned_shift_count ?? 0} 个` },
  { label: '今日催报', value: `${data.value.reminder_summary?.today_reminder_count ?? 0} 次` }
])
const decisionSquadStats = computed(() => [
  { label: '开放差异', value: `${data.value.exception_lane?.reconciliation_open_count ?? 0} 个` },
  { label: '待发布日报', value: `${data.value.exception_lane?.pending_report_publish_count ?? 0} 份` },
  { label: '月度归档', value: `${monthArchive.value.reported_days ?? 0} 天` },
  { label: '年度归档', value: `${yearArchive.value.active_months ?? 0} 个月` }
])
const pipelineSteps = computed(() => [
  {
    stage: '01',
    title: '岗位直录',
    summary: '主操、成品库、水电气、计划科把原始值按岗位直接录入。'
  },
  {
    stage: '02',
    title: '自动校验',
    summary: '采集清洗小队做字段完整性、范围校验、缺报提醒和异常退回。'
  },
  {
    stage: '03',
    title: '自动汇总',
    summary: '分析决策小队生成摘要、预警、趋势、归档和驾驶舱视图。'
  },
  {
    stage: '04',
    title: '领导直达',
    summary: '管理层直接看结果和异常闭环，不再等待中间人工汇总。'
  }
])
let refreshTimer = null

function formatMoney(value) {
  if (value === null || value === undefined || value === '') return '--'
  return `¥${formatNumber(value)}`
}

function trendBarWidth(value) {
  const safeValue = Number(value) || 0
  return `${Math.max((safeValue / maxTrendOutput.value) * 100, safeValue > 0 ? 12 : 0)}%`
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
  } catch {
    ElMessage.error('数据加载失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

watch(targetDate, () => load())

onMounted(() => {
  load()
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
.dashboard-command,
.dashboard-command__hero,
.dashboard-command__copy,
.dashboard-command__rail,
.dashboard-hero__metric,
.agent-orchestra-card,
.agent-orchestra-card__top,
.agent-orchestra-card__stats,
.agent-orchestra-stat,
.agent-flow__step,
.ops-digest-card {
  display: grid;
  gap: 12px;
}

.dashboard-command {
  padding: 24px;
  overflow: hidden;
  background:
    radial-gradient(circle at top right, rgba(37, 99, 235, 0.14), transparent 28%),
    radial-gradient(circle at bottom left, rgba(16, 185, 129, 0.12), transparent 30%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(244, 247, 251, 0.98));
}

.dashboard-command__hero {
  grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.95fr);
  align-items: start;
}

.dashboard-command__copy span,
.agent-orchestra-card__top span,
.agent-flow__step span,
.ops-digest-card span {
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--app-muted);
}

.dashboard-command__copy h2 {
  margin: 0;
  font-size: 34px;
  line-height: 1.18;
  color: var(--app-text);
}

.dashboard-command__copy p {
  margin: 0;
  color: var(--app-muted);
  line-height: 1.7;
  max-width: 720px;
}

.dashboard-command__pills {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.dashboard-command__pills span,
.top-pulse {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 0 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.9);
  border: 1px solid rgba(148, 163, 184, 0.16);
  color: var(--app-text);
  font-size: 13px;
  font-weight: 600;
}

.dashboard-command__rail {
  grid-template-columns: repeat(3, minmax(0, 1fr));
  align-content: start;
}

.dashboard-hero__metric {
  padding: 18px;
  border-radius: 24px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(255, 255, 255, 0.86);
  box-shadow: 0 18px 38px rgba(148, 163, 184, 0.14);
  animation: dashboard-float 5.6s ease-in-out infinite;
}

.dashboard-hero__metric:nth-child(2) {
  animation-delay: 0.18s;
}

.dashboard-hero__metric:nth-child(3) {
  animation-delay: 0.36s;
}

.dashboard-hero__metric span {
  font-size: 12px;
  color: var(--app-muted);
}

.dashboard-hero__metric strong {
  font-size: 24px;
  color: var(--app-text);
}

.agent-orchestra-grid,
.dashboard-secondary-grid,
.ops-digest-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.agent-orchestra-card {
  padding: 18px;
  border-radius: 24px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  background: rgba(255, 255, 255, 0.8);
  animation: dashboard-float 6.2s ease-in-out infinite;
}

.agent-orchestra-card.is-accent {
  background:
    radial-gradient(circle at top right, rgba(15, 118, 110, 0.14), transparent 36%),
    rgba(255, 255, 255, 0.82);
  animation-delay: 0.24s;
}

.agent-orchestra-card__top strong,
.agent-flow__step strong,
.ops-digest-card strong {
  font-size: 20px;
  color: var(--app-text);
  line-height: 1.35;
}

.agent-orchestra-card p,
.agent-flow__step p,
.ops-digest-card p {
  margin: 0;
  color: var(--app-muted);
  line-height: 1.7;
}

.agent-orchestra-card__stats {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.agent-orchestra-stat {
  padding: 14px;
  border-radius: 18px;
  background: rgba(248, 250, 252, 0.92);
  border: 1px solid rgba(148, 163, 184, 0.14);
}

.agent-orchestra-stat strong {
  font-size: 18px;
  color: var(--app-text);
}

.agent-flow {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.agent-flow__step {
  padding: 16px;
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.84);
  border: 1px solid rgba(148, 163, 184, 0.16);
  position: relative;
  overflow: hidden;
}

.agent-flow__step::after {
  content: '';
  position: absolute;
  inset: auto 12px 0 12px;
  height: 3px;
  border-radius: 999px;
  background: linear-gradient(90deg, rgba(37, 99, 235, 0.72), rgba(16, 185, 129, 0.72));
}

.agent-flow__step::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(120deg, transparent 0%, rgba(255, 255, 255, 0.55) 48%, transparent 100%);
  transform: translateX(-130%);
  animation: dashboard-sheen 7.2s ease-in-out infinite;
}

.ops-digest-card {
  padding: 18px;
  border-radius: 22px;
  background: rgba(248, 250, 252, 0.92);
  border: 1px solid rgba(148, 163, 184, 0.14);
}

@keyframes dashboard-float {
  0%,
  100% {
    transform: translateY(0);
  }

  50% {
    transform: translateY(-3px);
  }
}

@keyframes dashboard-sheen {
  0%,
  70%,
  100% {
    transform: translateX(-130%);
  }

  85% {
    transform: translateX(130%);
  }
}

.reporting-status-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.reporting-status-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 12px 16px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  min-width: 100px;
}

.reporting-status-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.reporting-status-weight {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.history-trend-grid,
.archive-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.history-trend-card,
.archive-card {
  display: grid;
  gap: 12px;
  padding: 18px;
  border-radius: 22px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  background:
    radial-gradient(circle at top right, rgba(14, 165, 233, 0.08), transparent 34%),
    rgba(255, 255, 255, 0.92);
  box-shadow: 0 18px 36px rgba(148, 163, 184, 0.12);
}

.history-trend-card__top,
.history-trend-card__meta,
.history-trend-card__meta > div,
.archive-card {
  display: grid;
  gap: 8px;
}

.history-trend-card__top strong,
.archive-card strong {
  font-size: 22px;
  color: var(--app-text);
}

.history-trend-card__top span,
.history-trend-card__meta span,
.archive-card span {
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
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
  font-size: 15px;
  color: var(--app-text);
}

.archive-card p {
  margin: 0;
  color: var(--app-muted);
  line-height: 1.7;
}

.archive-card--accent {
  background:
    radial-gradient(circle at top right, rgba(37, 99, 235, 0.14), transparent 34%),
    linear-gradient(135deg, rgba(239, 246, 255, 0.96), rgba(240, 249, 255, 0.96));
}

@media (max-width: 900px) {
  .dashboard-command__hero,
  .dashboard-secondary-grid,
  .ops-digest-grid {
    grid-template-columns: 1fr;
  }

  .dashboard-command__rail,
  .agent-orchestra-grid,
  .agent-flow,
  .agent-orchestra-card__stats {
    grid-template-columns: 1fr;
  }

  .history-trend-grid,
  .archive-grid {
    grid-template-columns: 1fr;
  }
}
</style>
