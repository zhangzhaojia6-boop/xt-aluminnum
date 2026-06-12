<template>
  <section class="page-stack contracts-command" data-testid="contracts-center-page">
    <header class="contracts-command__hero">
      <div class="contracts-command__hero-copy">
        <span class="contracts-command__eyebrow">订单管控</span>
        <h1>合同与订单中心</h1>
      </div>
      <div class="contracts-command__actions" data-testid="contracts-center-filters">
        <el-date-picker
          v-model="dateRange"
          class="contracts-command__date"
          type="daterange"
          value-format="YYYY-MM-DD"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
        />
        <el-select v-model="statusFilter" placeholder="状态" clearable class="contracts-command__select">
          <el-option label="执行中" value="active" />
          <el-option label="已完成" value="completed" />
          <el-option label="延期" value="overdue" />
        </el-select>
        <el-button class="contracts-command__button" @click="load">查询</el-button>
        <el-button class="contracts-command__button contracts-command__button--ghost" @click="onExport">导出</el-button>
      </div>
    </header>

    <section class="contracts-command__stats" data-testid="contracts-center-stats">
      <article
        v-for="item in contractStats"
        :key="item.key"
        class="contracts-command__stat"
        :class="`contracts-command__stat--${item.accent}`"
      >
        <div class="contracts-command__stat-top">
          <span class="contracts-command__led"></span>
          <span>{{ item.label }}</span>
        </div>
        <strong>{{ item.value }}</strong>
        <small>{{ item.unit }}</small>
      </article>
    </section>

    <section class="contracts-command__panel contracts-command__panel--chart">
      <div class="contracts-command__panel-head">
        <div>
          <span class="contracts-command__eyebrow">履约流转</span>
          <h2>履约进度</h2>
        </div>
        <span class="contracts-command__panel-chip">{{ progressLabels.length }} 个节点</span>
      </div>
      <XtErrorPanel v-if="error" :message="error" @retry="load" />
      <XtSkeleton v-else-if="loading" :rows="4" />
      <XtBarChart
        v-else
        :series="progressSeries"
        :x-labels="progressLabels"
        y-unit="吨"
        height="260px"
        :horizontal="true"
        :stacked="true"
      />
    </section>

    <section class="contracts-command__panel">
      <div class="contracts-command__panel-head">
        <div>
          <span class="contracts-command__eyebrow">合同清单</span>
          <h2>合同明细</h2>
        </div>
        <span class="contracts-command__panel-chip">{{ tableData.length }} 条</span>
      </div>

      <div class="contracts-command__table" data-testid="contracts-center-table">
        <XtDataTable
          :columns="columns"
          :data="tableData"
          :striped="true"
          data-source="contracts"
        >
          <template #cell-total_quantity="{ value }">
            {{ formatQuantity(value) }}
          </template>
          <template #cell-delivered_quantity="{ value }">
            {{ formatQuantity(value) }}
          </template>
          <template #cell-progress_pct="{ value }">
            <span class="contracts-command__progress">
              <i :style="{ width: progressWidth(value) }"></i>
              <strong>{{ formatPercent(value) }}</strong>
            </span>
          </template>
          <template #cell-status="{ value }">
            <span class="contracts-command__status" :data-status="statusTone(value)">{{ statusLabel(value) }}</span>
          </template>
        </XtDataTable>
      </div>

      <div class="contracts-command__mobile-list" data-testid="contracts-center-mobile-list">
        <article v-for="row in tableData" :key="row.contract_no || row.id">
          <div class="contracts-command__mobile-title">
            <span>{{ row.contract_no || '-' }}</span>
            <span class="contracts-command__status" :data-status="statusTone(row.status)">{{ statusLabel(row.status) }}</span>
          </div>
          <div class="contracts-command__mobile-grid">
            <span>客户</span><strong>{{ row.customer_name || '-' }}</strong>
            <span>合同量</span><strong>{{ formatQuantity(row.total_quantity) }}</strong>
            <span>已交付</span><strong>{{ formatQuantity(row.delivered_quantity) }}</strong>
            <span>进度</span><strong>{{ formatPercent(row.progress_pct) }}</strong>
            <span>交期</span><strong>{{ row.deadline || '-' }}</strong>
          </div>
        </article>
      </div>

      <XtEmpty v-if="!loading && !tableData.length" text="暂无合同数据" />
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../../api/index'
import XtBarChart from '../../components/xt/XtBarChart.vue'
import XtDataTable from '../../components/xt/XtDataTable.vue'
import XtErrorPanel from '../../components/xt/XtErrorPanel.vue'
import XtSkeleton from '../../components/xt/XtSkeleton.vue'
import XtEmpty from '../../components/xt/XtEmpty.vue'
import { downloadBlob } from '../../utils/downloadBlob.js'

const dateRange = ref([])
const statusFilter = ref('')
const loading = ref(false)
const error = ref('')
const kpi = ref({})
const progressSeries = ref([])
const progressLabels = ref([])
const tableData = ref([])

const columns = [
  { key: 'contract_no', label: '合同号', width: '140px' },
  { key: 'customer_name', label: '客户', width: '140px' },
  { key: 'total_quantity', label: '合同量(吨)', width: '108px' },
  { key: 'delivered_quantity', label: '已交付(吨)', width: '108px' },
  { key: 'progress_pct', label: '进度', width: '132px' },
  { key: 'deadline', label: '交期', width: '110px' },
  { key: 'status', label: '状态', width: '90px' }
]

const contractStats = computed(() => [
  { key: 'active', label: '活跃合同', value: formatNumber(kpi.value.active_count), unit: '份', accent: 'cyan' },
  { key: 'fulfillment', label: '履约率', value: formatNumber(kpi.value.fulfillment_pct), unit: '%', accent: 'blue' },
  { key: 'overdue', label: '延期预警', value: formatNumber(kpi.value.overdue_count), unit: '项', accent: 'amber' },
  { key: 'delivery', label: '本月交付量', value: formatNumber(kpi.value.mtd_delivery_tons), unit: '吨', accent: 'cyan' }
])

function toNumber(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number : 0
}

function formatNumber(value) {
  if (value === null || value === undefined || value === '') return '-'
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(toNumber(value))
}

function formatQuantity(value) {
  if (value === null || value === undefined || value === '') return '-'
  return `${formatNumber(value)} 吨`
}

function formatPercent(value) {
  if (value === null || value === undefined || value === '') return '-'
  return `${formatNumber(value)}%`
}

function progressWidth(value) {
  const clamped = Math.max(0, Math.min(100, toNumber(value)))
  return `${clamped}%`
}

function statusTone(status) {
  const value = String(status || '').toLowerCase()
  if (['completed', 'done', 'closed', 'finished'].includes(value)) return 'success'
  if (['overdue', 'delayed', 'risk'].includes(value)) return 'danger'
  if (['active', 'running', 'processing'].includes(value)) return 'active'
  return 'normal'
}

function statusLabel(status) {
  const value = String(status || '').toLowerCase()
  const map = {
    active: '执行中',
    completed: '已完成',
    done: '已完成',
    overdue: '延期',
    delayed: '延期',
    risk: '风险',
    closed: '已关闭'
  }
  return map[value] || status || '-'
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const params = {
      date_from: dateRange.value?.[0],
      date_to: dateRange.value?.[1],
      status: statusFilter.value || undefined
    }
    const { data } = await api.get('/contracts/summary', { params })
    kpi.value = data.kpi || {}
    progressSeries.value = data.progress?.series || []
    progressLabels.value = data.progress?.labels || []
    tableData.value = data.contracts || []
  } catch (e) {
    error.value = e?.response?.data?.detail || '加载失败'
  } finally {
    loading.value = false
  }
}

async function onExport() {
  try {
    const params = {
      date_from: dateRange.value?.[0],
      date_to: dateRange.value?.[1],
      status: statusFilter.value || undefined
    }
    const { data } = await api.get('/contracts/export', { params, responseType: 'blob' })
    downloadBlob(data, 'contracts_summary.csv')
  } catch (e) {
    error.value = e?.response?.data?.detail || '导出失败'
  }
}

onMounted(load)
</script>

<style scoped>
.contracts-command {
  --contracts-cyan: #00f2ff;
  --contracts-cyan-soft: rgba(0, 242, 255, 0.16);
  --contracts-amber: #ffab00;
  --contracts-blue: #74f5ff;
  --contracts-danger: #ff5c35;
  --contracts-bg: #06101f;
  --contracts-panel: rgba(12, 25, 42, 0.72);
  --contracts-line: rgba(0, 242, 255, 0.18);
  --contracts-muted: rgba(223, 226, 235, 0.66);
  color: #dfe2eb;
}

.contracts-command::before {
  position: fixed;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  content: '';
  background:
    radial-gradient(circle at 14% 8%, rgba(0, 242, 255, 0.12), transparent 30%),
    radial-gradient(circle at 82% 10%, rgba(255, 171, 0, 0.08), transparent 24%),
    linear-gradient(rgba(0, 242, 255, 0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 242, 255, 0.035) 1px, transparent 1px),
    linear-gradient(135deg, #0a0e14, var(--contracts-bg));
  background-size: auto, auto, 32px 32px, 32px 32px, auto;
}

.contracts-command__hero,
.contracts-command__panel,
.contracts-command__stat,
.contracts-command__mobile-list article {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--contracts-line);
  background: linear-gradient(180deg, rgba(38, 42, 49, 0.54), var(--contracts-panel));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06), 0 20px 54px rgba(0, 0, 0, 0.22);
  backdrop-filter: blur(14px);
}

.contracts-command__hero::after,
.contracts-command__panel::after,
.contracts-command__stat::after {
  position: absolute;
  inset: 0;
  pointer-events: none;
  content: '';
  background: linear-gradient(115deg, transparent 0%, rgba(0, 242, 255, 0.14) 42%, transparent 62%);
  transform: translateX(-120%);
  animation: contractsSweep 7s ease-in-out infinite;
}

.contracts-command__hero {
  display: grid;
  grid-template-columns: minmax(460px, 1fr) minmax(420px, auto);
  align-items: center;
  gap: 20px;
  min-height: 156px;
  padding: 28px;
  border-radius: 18px;
}

.contracts-command__hero-copy,
.contracts-command__actions,
.contracts-command__panel-head,
.contracts-command__table,
.contracts-command__mobile-list {
  position: relative;
  z-index: 1;
}

.contracts-command__eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--contracts-cyan);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.16em;
}

.contracts-command__eyebrow::before {
  width: 8px;
  height: 8px;
  content: '';
  border-radius: 999px;
  background: var(--contracts-cyan);
  box-shadow: 0 0 18px var(--contracts-cyan);
}

.contracts-command h1,
.contracts-command h2 {
  margin: 0;
  color: #f6fbff;
  font-family: 'Hanken Grotesk', 'Inter', sans-serif;
  letter-spacing: -0.03em;
}

.contracts-command h1 {
  margin-top: 12px;
  font-size: clamp(34px, 5vw, 58px);
  line-height: 1;
  white-space: nowrap;
  text-shadow: 0 0 28px rgba(0, 242, 255, 0.22);
}

.contracts-command h2 {
  margin-top: 8px;
  font-size: 24px;
}

.contracts-command__actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 12px;
  padding: 12px;
  border: 1px solid rgba(0, 242, 255, 0.14);
  border-radius: 16px;
  background: rgba(1, 16, 31, 0.58);
}

.contracts-command__date {
  width: 260px;
}

.contracts-command__select {
  width: 130px;
}

.contracts-command__actions :deep(.el-input__wrapper),
.contracts-command__actions :deep(.el-select__wrapper) {
  min-height: 38px;
  border-radius: 10px;
  background: rgba(1, 16, 31, 0.72);
  box-shadow:
    inset 0 -1px 0 rgba(0, 242, 255, 0.3),
    inset 0 0 0 1px rgba(0, 242, 255, 0.14);
}

.contracts-command__actions :deep(.el-input__inner),
.contracts-command__actions :deep(.el-range-input),
.contracts-command__actions :deep(.el-range-separator),
.contracts-command__actions :deep(.el-select__placeholder),
.contracts-command__actions :deep(.el-select__selected-item) {
  color: #e1fdff;
}

.contracts-command__button {
  min-width: 92px;
  border: 1px solid rgba(0, 242, 255, 0.32);
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(0, 242, 255, 0.22), rgba(0, 118, 255, 0.32));
  color: #e1fdff;
  font-weight: 800;
  box-shadow: 0 0 26px rgba(0, 242, 255, 0.16);
}

.contracts-command__button--ghost {
  background: rgba(1, 16, 31, 0.68);
}

.contracts-command__stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.contracts-command__stat {
  min-height: 132px;
  padding: 18px;
  border-radius: 16px;
}

.contracts-command__stat-top {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--contracts-muted);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.contracts-command__led {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: var(--contracts-cyan);
  box-shadow: 0 0 18px var(--contracts-cyan);
  animation: contractsPulse 2.2s ease-in-out infinite;
}

.contracts-command__stat strong {
  position: relative;
  z-index: 1;
  display: block;
  margin-top: 18px;
  color: #f6fbff;
  font-family: 'Hanken Grotesk', 'Inter', sans-serif;
  font-size: clamp(30px, 4vw, 46px);
  line-height: 0.95;
  text-shadow: 0 0 24px rgba(0, 242, 255, 0.22);
}

.contracts-command__stat small {
  position: relative;
  z-index: 1;
  display: block;
  margin-top: 8px;
  color: var(--contracts-muted);
  font-weight: 700;
}

.contracts-command__stat--amber .contracts-command__led {
  background: var(--contracts-amber);
  box-shadow: 0 0 18px var(--contracts-amber);
}

.contracts-command__stat--blue .contracts-command__led {
  background: var(--contracts-blue);
  box-shadow: 0 0 18px var(--contracts-blue);
}

.contracts-command__panel {
  padding: 22px;
  border-radius: 18px;
}

.contracts-command__panel--chart {
  min-height: 360px;
}

.contracts-command__panel-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 18px;
}

.contracts-command__panel-chip {
  border: 1px solid rgba(0, 242, 255, 0.16);
  border-radius: 999px;
  padding: 6px 10px;
  color: var(--contracts-muted);
  background: rgba(1, 16, 31, 0.62);
  font-size: 12px;
  font-weight: 700;
}

.contracts-command__table {
  overflow: hidden;
  border: 1px solid rgba(0, 242, 255, 0.12);
  border-radius: 14px;
}

.contracts-command__table :deep(.xt-data-table),
.contracts-command__table :deep(.xt-data-table__table),
.contracts-command__table :deep(.xt-data-table__row) {
  border-color: rgba(0, 242, 255, 0.12);
  background: transparent;
}

.contracts-command__table :deep(.xt-data-table__th) {
  color: rgba(225, 253, 255, 0.82);
  border-color: rgba(0, 242, 255, 0.12);
}

.contracts-command__table :deep(.xt-data-table__td) {
  color: #dfe2eb;
  border-color: rgba(0, 242, 255, 0.1);
}

.contracts-command__table :deep(.xt-data-table--striped .xt-data-table__row:nth-child(even)) {
  background: rgba(0, 242, 255, 0.035);
}

.contracts-command__table :deep(.xt-data-table__row:hover) {
  background: rgba(0, 242, 255, 0.08);
}

.contracts-command__progress {
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: center;
  gap: 8px;
  min-width: 92px;
}

.contracts-command__progress i {
  display: block;
  height: 6px;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--contracts-cyan), var(--contracts-blue));
  box-shadow: 0 0 14px rgba(0, 242, 255, 0.22);
}

.contracts-command__progress strong {
  color: #f6fbff;
}

.contracts-command__status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 58px;
  border-radius: 999px;
  padding: 4px 9px;
  background: rgba(0, 242, 255, 0.14);
  color: #a7fff8;
  font-size: 12px;
  font-weight: 800;
  box-shadow: 0 0 14px rgba(0, 242, 255, 0.12);
}

.contracts-command__status[data-status='success'] {
  background: rgba(116, 245, 255, 0.16);
  color: #d8ffff;
}

.contracts-command__status[data-status='danger'] {
  background: rgba(255, 92, 53, 0.16);
  color: #ffd8cf;
  box-shadow: 0 0 16px rgba(255, 92, 53, 0.16);
}

.contracts-command__mobile-list {
  display: none;
}

.contracts-command__mobile-list article {
  border-radius: 16px;
  padding: 16px;
}

.contracts-command__mobile-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: #f6fbff;
  font-family: 'Hanken Grotesk', 'Inter', sans-serif;
  font-size: 18px;
  font-weight: 800;
}

.contracts-command__mobile-grid {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 8px 14px;
  margin-top: 14px;
}

.contracts-command__mobile-grid span {
  color: var(--contracts-muted);
}

.contracts-command__mobile-grid strong {
  color: #f6fbff;
  text-align: right;
}

@keyframes contractsSweep {
  0% { transform: translateX(-120%); opacity: 0; }
  42% { opacity: 1; }
  100% { transform: translateX(120%); opacity: 0; }
}

@keyframes contractsPulse {
  0%, 100% { transform: scale(1); opacity: 0.72; }
  50% { transform: scale(1.22); opacity: 1; }
}

@media (max-width: 1180px) {
  .contracts-command__hero {
    grid-template-columns: 1fr;
  }

  .contracts-command__actions {
    justify-content: flex-start;
  }

  .contracts-command__stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .contracts-command__hero,
  .contracts-command__panel-head {
    align-items: stretch;
    flex-direction: column;
  }

  .contracts-command h1 {
    white-space: normal;
  }

  .contracts-command__actions {
    display: grid;
    grid-template-columns: 1fr;
  }

  .contracts-command__date,
  .contracts-command__select,
  .contracts-command__button,
  .contracts-command__actions :deep(.el-date-editor) {
    width: 100%;
  }

  .contracts-command__stats {
    grid-template-columns: 1fr;
  }

  .contracts-command__panel {
    padding: 16px;
  }

  .contracts-command__table {
    display: none;
  }

  .contracts-command__mobile-list {
    display: grid;
    gap: 12px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .contracts-command__hero::after,
  .contracts-command__panel::after,
  .contracts-command__stat::after,
  .contracts-command__led {
    animation: none;
  }
}
</style>
