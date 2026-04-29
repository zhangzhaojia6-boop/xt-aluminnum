<template>
  <div class="factory-board" data-testid="factory-dashboard">
    <header class="factory-board__header">
      <div>
        <h1>工厂作业看板</h1>
        <div class="factory-board__meta">
          <span>{{ targetDate }}</span>
          <span>更新 {{ lastRefreshLabel }}</span>
        </div>
      </div>
      <el-date-picker v-model="targetDate" type="date" value-format="YYYY-MM-DD" size="small" />
    </header>

    <section class="metric-grid" v-loading="loading">
      <article v-for="card in metricCards" :key="card.label" class="metric-card stat-card">
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value">{{ card.value }}</strong>
        <small v-if="card.unit">{{ card.unit }}</small>
      </article>
      <article class="metric-card metric-card--status stat-card" data-testid="delivery-ready-card">
        <span class="stat-label">交付状态</span>
        <strong class="stat-value">{{ delivery.delivery_ready ? '可交付' : '未就绪' }}</strong>
        <small data-testid="delivery-missing-steps">
          {{ formatDeliveryMissingSteps(delivery.missing_steps).join('；') }}
        </small>
      </article>
    </section>

    <section class="board-grid board-grid--two">
      <el-card class="board-card" shadow="never" v-loading="loading">
        <template #header>
          <div class="card-header">
            <span>今日上报状态</span>
            <small>{{ reportingRows.length }} 个车间</small>
          </div>
        </template>
        <el-table
          v-if="reportingRows.length"
          :data="reportingRows"
          border
          stripe
          size="small"
          class="dense-table"
        >
          <el-table-column prop="workshop_name" label="车间" min-width="120" />
          <el-table-column label="状态" width="104">
            <template #default="{ row }">
              <el-tag :type="reportStatusTagType(row.report_status)" effect="plain" size="small">
                {{ reportStatusLabel(row.report_status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="产量" width="112" align="right">
            <template #default="{ row }">
              {{ row.output_weight == null ? '-' : `${formatNumber(row.output_weight)} 吨` }}
            </template>
          </el-table-column>
        </el-table>
        <div v-else class="empty-line">暂无车间数据</div>
      </el-card>

      <el-card class="board-card" shadow="never" v-loading="loading">
        <template #header>
          <div class="card-header">
            <span>今日关注</span>
            <small>{{ delivery.delivery_ready ? 'ready' : 'blocked' }}</small>
          </div>
        </template>
        <div class="fact-grid">
          <div v-for="item in attentionItems" :key="item.label" class="fact-cell">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
      </el-card>
    </section>

    <el-card class="board-card" shadow="never" v-loading="loading">
      <template #header>
        <div class="card-header">
          <span>近 7 日趋势</span>
          <small>{{ dailySnapshots.length }} 天</small>
        </div>
      </template>
      <div v-if="dailySnapshots.length" class="trend-list">
        <div v-for="item in dailySnapshots" :key="item.date" class="trend-row">
          <div class="trend-row__date">
            <strong>{{ item.label }}</strong>
            <span>{{ item.date }}</span>
          </div>
          <div class="trend-row__bar">
            <span :style="{ width: trendBarWidth(item.output_weight) }" />
          </div>
          <div class="trend-row__metrics">
            <span>产量 {{ formatNumber(item.output_weight) }}</span>
            <span>入库 {{ formatNumber(item.storage_finished_weight) }}</span>
            <span>发货 {{ formatNumber(item.shipment_weight) }}</span>
            <span>面积 {{ formatNumber(item.storage_inbound_area) }}</span>
            <span>合同 {{ formatNumber(item.contract_weight) }}</span>
          </div>
        </div>
      </div>
      <div v-else class="empty-line">暂无趋势数据</div>
    </el-card>

    <section class="board-grid board-grid--three" v-loading="loading">
      <article v-for="item in archiveCards" :key="item.label" class="archive-cell">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
        <small>{{ item.meta }}</small>
      </article>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { useRoute } from 'vue-router'

import { fetchDeliveryStatus, fetchFactoryDashboard } from '../../api/dashboard'
import { formatDeliveryMissingSteps, formatNumber } from '../../utils/display'

const route = useRoute()

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

function resolveInitialTargetDate() {
  const value = typeof route.query.target_date === 'string' ? route.query.target_date : ''
  if (/^\d{4}-\d{2}-\d{2}$/.test(value) && dayjs(value).isValid()) return value
  return dayjs().format('YYYY-MM-DD')
}

const targetDate = ref(resolveInitialTargetDate())
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
const monthToDateOutput = computed(() => data.value.month_to_date_output ?? data.value.leader_metrics?.month_to_date_output ?? null)
const lastRefreshLabel = computed(() => (lastRefreshAt.value ? dayjs(lastRefreshAt.value).format('HH:mm:ss') : '--:--:--'))
const reportingRows = computed(() => data.value.workshop_reporting_status || [])
const metricCards = computed(() => [
  { label: '今日产量', value: formatNumber(leaderMetrics.value.today_total_output), unit: '吨' },
  { label: '月累计', value: formatNumber(monthToDateOutput.value), unit: '吨' },
  { label: '成品入库', value: formatNumber(leaderMetrics.value.storage_finished_weight), unit: '吨' },
  { label: '今日发货', value: formatNumber(leaderMetrics.value.shipment_weight), unit: '吨' },
  { label: '在制料', value: formatNumber(leaderMetrics.value.in_process_weight), unit: '吨' },
  { label: '合同量', value: formatNumber(leaderMetrics.value.contract_weight), unit: '吨' },
  { label: '入库面积', value: formatNumber(leaderMetrics.value.storage_inbound_area), unit: '㎡' },
  { label: '单吨能耗', value: formatNumber(leaderMetrics.value.energy_per_ton), unit: '' },
  { label: '估算收入', value: formatMoney(leaderMetrics.value.estimated_revenue), unit: '' },
  { label: '估算成本', value: formatMoney(leaderMetrics.value.estimated_cost), unit: '' },
  { label: '估算毛差', value: formatMoney(leaderMetrics.value.estimated_margin), unit: '' },
  { label: '成品率', value: `${formatNumber(leaderMetrics.value.yield_rate)}%`, unit: '' }
])
const attentionItems = computed(() => [
  { label: '未报班次', value: data.value.exception_lane?.unreported_shift_count ?? 0 },
  { label: '迟报班次', value: data.value.exception_lane?.reminder_late_count ?? 0 },
  { label: '待处理差异', value: data.value.exception_lane?.reconciliation_open_count ?? 0 },
  { label: '待处理日报', value: data.value.exception_lane?.pending_report_publish_count ?? 0 },
  { label: '活跃合同', value: leaderMetrics.value.active_contract_count ?? 0 },
  { label: '停滞合同', value: leaderMetrics.value.stalled_contract_count ?? 0 },
  { label: '活跃卷数', value: leaderMetrics.value.active_coil_count ?? 0 },
  { label: '出勤', value: leaderMetrics.value.total_attendance ?? 0 }
])
const archiveCards = computed(() => [
  {
    label: '月度归档',
    value: `${formatNumber(monthArchive.value.total_output)} 吨`,
    meta: `${monthArchive.value.reported_days ?? 0} 天 / 日均 ${formatNumber(monthArchive.value.average_daily_output)} 吨`
  },
  {
    label: '年度归档',
    value: `${formatNumber(yearArchive.value.total_output)} 吨`,
    meta: `${yearArchive.value.active_months ?? 0} 月 / 月均 ${formatNumber(yearArchive.value.average_monthly_output)} 吨`
  },
  {
    label: '当日留存',
    value: targetDate.value,
    meta: `刷新 ${lastRefreshLabel.value}`
  }
])
let refreshTimer = null

function formatMoney(value) {
  if (value === null || value === undefined || value === '') return '-'
  return `¥${formatNumber(value)}`
}

function trendBarWidth(value) {
  const safeValue = Number(value) || 0
  return `${Math.max((safeValue / maxTrendOutput.value) * 100, safeValue > 0 ? 8 : 0)}%`
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
.factory-board {
  display: grid;
  gap: 12px;
  color: #111827;
}

.factory-board__header,
.card-header,
.trend-row,
.trend-row__metrics {
  display: flex;
  align-items: center;
}

.factory-board__header {
  justify-content: space-between;
  gap: 12px;
  padding: 14px 16px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #ffffff;
}

.factory-board__header h1 {
  margin: 0;
  font-size: 20px;
  line-height: 1.25;
  font-weight: 650;
  letter-spacing: 0;
}

.factory-board__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 4px;
  color: #6b7280;
  font-size: 12px;
}

.metric-grid,
.board-grid {
  display: grid;
  gap: 10px;
}

.metric-grid {
  grid-template-columns: repeat(13, minmax(92px, 1fr));
}

.metric-card,
.archive-cell {
  min-width: 0;
  padding: 10px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #ffffff;
}

.metric-card span,
.archive-cell span,
.fact-cell span,
.trend-row__date span,
.trend-row__metrics span {
  color: #6b7280;
  font-size: 12px;
  line-height: 1.2;
}

.metric-card strong,
.archive-cell strong,
.fact-cell strong {
  display: block;
  margin-top: 4px;
  color: #111827;
  font-size: 18px;
  line-height: 1.15;
  font-weight: 650;
  letter-spacing: 0;
}

.metric-card small,
.archive-cell small {
  display: block;
  margin-top: 3px;
  color: #6b7280;
  font-size: 11px;
  line-height: 1.3;
}

.metric-card--status strong {
  color: #b45309;
}

.board-grid--two {
  grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.65fr);
}

.board-grid--three {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.board-card {
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #ffffff;
}

.board-card :deep(.el-card__header) {
  padding: 9px 12px;
  border-bottom-color: #e5e7eb;
}

.board-card :deep(.el-card__body) {
  padding: 10px 12px;
}

.card-header {
  justify-content: space-between;
  gap: 8px;
  min-height: 20px;
  color: #111827;
  font-size: 13px;
  font-weight: 650;
}

.card-header small {
  color: #6b7280;
  font-size: 11px;
  font-weight: 500;
}

.dense-table {
  font-size: 12px;
}

.dense-table :deep(.el-table__cell) {
  padding: 5px 0;
}

.fact-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 8px;
}

.fact-cell {
  min-width: 0;
  padding: 8px 10px;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  background: #ffffff;
}

.fact-cell strong {
  font-size: 17px;
}

.trend-list {
  display: grid;
  gap: 8px;
}

.trend-row {
  gap: 12px;
  min-height: 44px;
  padding: 8px 0;
  border-bottom: 1px solid #f3f4f6;
}

.trend-row:last-child {
  border-bottom: 0;
}

.trend-row__date {
  width: 96px;
}

.trend-row__date strong {
  display: block;
  color: #111827;
  font-size: 13px;
  line-height: 1.25;
}

.trend-row__bar {
  flex: 1;
  height: 6px;
  overflow: hidden;
  border-radius: 999px;
  background: #f3f4f6;
}

.trend-row__bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: #111827;
}

.trend-row__metrics {
  justify-content: flex-end;
  gap: 10px;
  width: min(48%, 520px);
}

.archive-cell strong {
  font-size: 17px;
}

.empty-line {
  padding: 12px;
  border: 1px dashed #e5e7eb;
  border-radius: 6px;
  color: #6b7280;
  font-size: 12px;
  text-align: center;
}

@media (max-width: 1280px) {
  .metric-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
  }

  .board-grid--two {
    grid-template-columns: 1fr;
  }

  .trend-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .trend-row__bar,
  .trend-row__metrics {
    width: 100%;
  }

  .trend-row__metrics {
    justify-content: flex-start;
    flex-wrap: wrap;
  }
}

@media (max-width: 720px) {
  .factory-board__header {
    align-items: flex-start;
    flex-direction: column;
  }

  .metric-grid,
  .board-grid--three,
  .fact-grid {
    grid-template-columns: 1fr;
  }
}
</style>
