<template>
  <div class="page-stack" data-testid="statistics-dashboard">
    <div class="page-header">
      <div>
        <div class="page-eyebrow">数据观察</div>
        <h1>统计看板</h1>
      </div>
      <div class="header-actions">
        <el-date-picker v-model="targetDate" type="date" value-format="YYYY-MM-DD" />
        <span class="note">数据更新于 {{ lastRefreshLabel }}</span>
        <el-button @click="load">刷新</el-button>
      </div>
    </div>

    <div class="stat-grid stat-reveal stat-reveal--1" v-loading="loading">
      <div class="stat-card">
        <div class="stat-label">待处理班次</div>
        <div class="stat-value">{{ stats.pending_shift_count ?? 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">兼容中间态班次</div>
        <div class="stat-value">{{ stats.reviewed_shift_count ?? 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">主口径已就绪班次</div>
        <div class="stat-value">{{ stats.confirmed_shift_count ?? 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">手机上报率</div>
        <div class="stat-value">{{ stats.mobile_reporting_summary?.reporting_rate ?? 0 }}%</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">未报班次</div>
        <div class="stat-value">{{ stats.unreported_shift_count ?? 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">迟报班次</div>
        <div class="stat-value">{{ stats.late_report_count ?? 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">今日催报次数</div>
        <div class="stat-value">{{ stats.today_reminder_count ?? 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">未处理差异</div>
        <div class="stat-value">{{ stats.open_reconciliation_count ?? 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">质量阻断</div>
        <div class="stat-value">{{ delivery.blocker_count ?? 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">交付条件满足</div>
        <div class="stat-value">{{ formatBooleanLabel(stats.can_finalize) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">交付状态</div>
        <div class="stat-value">{{ delivery.delivery_ready ? '可交付' : '未就绪' }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">MES 同步延迟</div>
        <div class="stat-value">{{ syncLagText }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">活跃合同</div>
        <div class="stat-value">{{ stats.management_estimate?.active_contract_count ?? 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">停滞合同</div>
        <div class="stat-value">{{ stats.management_estimate?.stalled_contract_count ?? 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">活跃卷数</div>
        <div class="stat-value">{{ stats.management_estimate?.active_coil_count ?? 0 }}</div>
      </div>
    </div>

    <el-card class="panel stat-reveal stat-reveal--2" v-loading="loading">
      <template #header>MES 同步状态</template>
      <el-descriptions :column="4" border>
        <el-descriptions-item label="最近同步">{{ stats.mes_sync_status?.last_synced_at || '-' }}</el-descriptions-item>
        <el-descriptions-item label="最近事件">{{ stats.mes_sync_status?.last_event_at || '-' }}</el-descriptions-item>
        <el-descriptions-item label="Lag">{{ syncLagText }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ stats.mes_sync_status?.last_run_status || 'idle' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card class="panel stat-reveal stat-reveal--2" v-loading="loading">
      <template #header>成品率矩阵正式口径</template>
      <el-descriptions :column="4" border>
        <el-descriptions-item label="矩阵日期">{{ yieldMatrixLane.business_date ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="快照数">{{ yieldMatrixLane.snapshot_count ?? 0 }}</el-descriptions-item>
        <el-descriptions-item label="公司总成品率">{{ formatNumber(yieldMatrixLane.company_total_yield) }}</el-descriptions-item>
        <el-descriptions-item label="质量状态">{{ formatStatusLabel(yieldMatrixLane.quality_status) }}</el-descriptions-item>
        <el-descriptions-item label="M 指标">{{ formatNumber(yieldMatrixLane.mp_targets?.M) }}</el-descriptions-item>
        <el-descriptions-item label="P 指标">{{ formatNumber(yieldMatrixLane.mp_targets?.P) }}</el-descriptions-item>
        <el-descriptions-item label="主交付范围">{{ yieldMatrixLane.primary_delivery_scope ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="交付范围">{{ (yieldMatrixLane.delivery_scopes || []).join('、') || '-' }}</el-descriptions-item>
      </el-descriptions>
      <el-table :data="yieldMatrixWorkshopRows" stripe>
        <el-table-column prop="workshop_key" label="矩阵口径" min-width="180" />
        <el-table-column prop="yield_rate" label="正式成品率" min-width="120">
          <template #default="{ row }">{{ formatNumber(row.yield_rate) }}</template>
        </el-table-column>
      </el-table>
    </el-card>


    <el-card class="panel stat-reveal stat-reveal--3" v-loading="loading">
      <template #header>合同口径观察</template>
      <el-descriptions :column="4" border>
        <el-descriptions-item label="快照数">{{ stats.contract_lane?.snapshot_count ?? 0 }}</el-descriptions-item>
        <el-descriptions-item label="当日合同">{{ formatNumber(stats.contract_lane?.daily_contract_weight) }}</el-descriptions-item>
        <el-descriptions-item label="月累计合同">{{ formatNumber(stats.contract_lane?.month_to_date_contract_weight) }}</el-descriptions-item>
        <el-descriptions-item label="质量状态">{{ formatStatusLabel(stats.contract_lane?.quality_status) }}</el-descriptions-item>
      </el-descriptions>
      <div class="note">作用域：{{ (stats.contract_lane?.delivery_scopes || []).join('、') || '未识别' }}</div>
      <el-table :data="stats.contract_lane?.items || []" stripe>
        <el-table-column prop="sheet_name" label="Sheet" />
        <el-table-column prop="business_date" label="业务日期" width="120" />
        <el-table-column prop="delivery_scope" label="作用域" width="160" />
        <el-table-column prop="daily_contract_weight" label="当日合同">
          <template #default="{ row }">{{ formatNumber(row.daily_contract_weight) }}</template>
        </el-table-column>
        <el-table-column prop="month_to_date_contract_weight" label="月累计合同">
          <template #default="{ row }">{{ formatNumber(row.month_to_date_contract_weight) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="panel stat-reveal stat-reveal--3" v-loading="loading">
      <template #header>日报产出状态</template>
      <el-descriptions :column="4" border>
        <el-descriptions-item label="已生成日报">{{ delivery.reports_generated ?? 0 }}</el-descriptions-item>
        <el-descriptions-item label="兼容中间态日报">{{ delivery.reports_reviewed_count ?? 0 }}</el-descriptions-item>
        <el-descriptions-item label="已输出日报">{{ delivery.reports_published_count ?? 0 }}</el-descriptions-item>
        <el-descriptions-item label="兼容统计字段">{{ delivery.reports_published ?? 0 }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card class="panel stat-reveal stat-reveal--3" v-loading="loading">
      <template #header>待处理班次</template>
      <el-table :data="stats.pending_shift_items || []" stripe>
        <el-table-column prop="id" label="编号" width="80" />
        <el-table-column prop="business_date" label="业务日期" width="120" />
        <el-table-column prop="workshop_id" label="车间编号" width="100" />
        <el-table-column prop="shift_config_id" label="班次编号" width="100" />
        <el-table-column prop="version_no" label="版本号" width="90" />
        <el-table-column prop="data_status" label="状态" width="120">
          <template #default="{ row }">
            {{ formatStatusLabel(row.data_status) }}
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="panel stat-reveal stat-reveal--3" v-loading="loading">
      <template #header>催报概览</template>
      <el-table :data="stats.reminder_summary?.recent_items || []" stripe>
        <el-table-column prop="reminder_type" label="提醒类型">
          <template #default="{ row }">{{ formatReminderTypeLabel(row.reminder_type) }}</template>
        </el-table-column>
        <el-table-column prop="reminder_status" label="状态">
          <template #default="{ row }">{{ formatStatusLabel(row.reminder_status) }}</template>
        </el-table-column>
        <el-table-column prop="reminder_count" label="次数" width="80" />
        <el-table-column prop="last_reminded_at" label="最近催报时间" />
      </el-table>
    </el-card>

    <el-card class="panel stat-reveal stat-reveal--3" v-loading="loading">
      <template #header>交付缺口</template>
      <div class="note">{{ formatDeliveryMissingSteps(delivery.missing_steps).join('；') }}</div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import dayjs from 'dayjs'

import { fetchDeliveryStatus, fetchStatisticsDashboard } from '../../api/dashboard'
import {
  formatBooleanLabel,
  formatDeliveryMissingSteps,
  formatNumber,
  formatReminderTypeLabel,
  formatStatusLabel
} from '../../utils/display'

const targetDate = ref(dayjs().format('YYYY-MM-DD'))
const loading = ref(false)
const stats = ref({})
const delivery = ref({})
const lastRefreshAt = ref('')
const yieldMatrixLane = computed(() => stats.value.yield_matrix_lane || {})
const syncLagText = computed(() => {
  const lag = Number(stats.value.mes_sync_status?.lag_seconds)
  if (!Number.isFinite(lag)) return '--'
  if (lag < 60) return `${lag.toFixed(0)} 秒`
  return `${(lag / 60).toFixed(1)} 分钟`
})
const yieldMatrixWorkshopRows = computed(() =>
  Object.entries(yieldMatrixLane.value.workshop_yields || {}).map(([workshopKey, yieldRate]) => ({
    workshop_key: workshopKey,
    yield_rate: yieldRate
  }))
)
const lastRefreshLabel = computed(() => (lastRefreshAt.value ? dayjs(lastRefreshAt.value).format('HH:mm:ss') : '--:--:--'))
let refreshTimer = null

async function load() {
  loading.value = true
  try {
    const [statsPayload, deliveryPayload] = await Promise.all([
      fetchStatisticsDashboard({ target_date: targetDate.value }),
      fetchDeliveryStatus({ target_date: targetDate.value })
    ])
    stats.value = statsPayload
    delivery.value = deliveryPayload
    lastRefreshAt.value = new Date().toISOString()
  } finally {
    loading.value = false
  }
}

watch(targetDate, () => load())

onMounted(() => {
  load()
  refreshTimer = setInterval(load, 60000)
})

onUnmounted(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})
</script>

<style scoped>
.page-stack {
  padding: var(--xt-space-4);
  background: var(--xt-bg-page);
  min-height: 100vh;
}

.page-eyebrow {
  font-size: var(--xt-text-xs);
  letter-spacing: 0.02em;
  color: var(--xt-text-muted);
}

.page-header h1 {
  margin: 0;
  font-size: var(--xt-text-2xl);
  line-height: 1.16;
  letter-spacing: 0;
  color: var(--xt-text);
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--xt-space-3);
  margin-bottom: var(--xt-space-4);
}

.stat-card {
  padding: var(--xt-space-4);
  background: var(--xt-bg-panel);
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-xl);
  box-shadow: var(--xt-shadow-sm);
  transition: transform var(--xt-motion-fast) var(--xt-ease),
              box-shadow var(--xt-motion-fast) var(--xt-ease),
              border-color var(--xt-motion-fast) var(--xt-ease);
}

.stat-card:hover {
  transform: translateY(-2px);
  border-color: var(--xt-primary-border);
  box-shadow: var(--xt-shadow-md);
}

.stat-label {
  color: var(--xt-text-muted);
  font-size: var(--xt-text-xs);
  font-weight: 600;
  letter-spacing: 0.02em;
  margin-bottom: var(--xt-space-1);
}

.stat-value {
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-2xl);
  font-weight: 700;
  color: var(--xt-text);
  letter-spacing: -0.01em;
  font-variant-numeric: tabular-nums;
}

.panel {
  padding: var(--xt-space-4);
  background: var(--xt-bg-panel);
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-xl);
  box-shadow: var(--xt-shadow-sm);
  margin-bottom: var(--xt-space-3);
}

.header-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--xt-space-4);
}

.note {
  font-size: var(--xt-text-xs);
  color: var(--xt-text-muted);
}

.stat-reveal {
  opacity: 0;
  transform: translateY(8px);
  animation: stat-reveal 0.24s var(--xt-ease) forwards;
}

.stat-reveal--1 { animation-delay: 0.02s; }
.stat-reveal--2 { animation-delay: 0.04s; }
.stat-reveal--3 { animation-delay: 0.06s; }

@keyframes stat-reveal {
  to { opacity: 1; transform: translateY(0); }
}
</style>
