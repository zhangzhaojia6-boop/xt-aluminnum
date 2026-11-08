<template>
  <section class="page-stack attendance-command" data-testid="attendance-overview-page">
    <header class="attendance-command__hero">
      <div>
        <span class="attendance-command__eyebrow">考勤预留</span>
        <h1>考勤预留</h1>
        <p class="attendance-command__subtitle">后续接入钉钉打卡后启用；当前页面仅保留结果核查入口。</p>
      </div>
      <div class="attendance-command__actions">
        <el-date-picker
          v-model="businessDate"
          class="attendance-command__date"
          type="date"
          value-format="YYYY-MM-DD"
        />
        <el-button class="attendance-command__ghost" @click="load">查询</el-button>
        <el-button class="attendance-command__primary" :loading="processing" @click="runProcess">自动处理</el-button>
      </div>
    </header>

    <section class="attendance-command__stats" data-testid="attendance-overview-stats">
      <article
        v-for="item in summaryCards"
        :key="item.key"
        class="attendance-command__stat"
        :class="`attendance-command__stat--${item.accent}`"
      >
        <div class="attendance-command__stat-top">
          <span class="attendance-command__led"></span>
          <span>{{ item.label }}</span>
        </div>
        <strong>{{ item.value }}</strong>
        <small>{{ businessDate }}</small>
      </article>
    </section>

    <section class="attendance-command__matrix">
      <div class="attendance-command__matrix-head">
        <div>
          <span class="attendance-command__eyebrow">考勤清单</span>
          <h2>考勤结果明细</h2>
        </div>
        <div class="attendance-command__matrix-meta">
          <span>{{ businessDate }}</span>
          <span>{{ items.length }} 人</span>
        </div>
      </div>

      <div class="attendance-command__table" data-testid="attendance-overview-table">
        <ReferenceDataTable :data="items" stripe>
          <el-table-column prop="employee_no" label="工号" width="120" />
          <el-table-column prop="employee_name" label="姓名" width="140" />
          <el-table-column prop="attendance_status" label="状态" width="130">
            <template #default="{ row }">
              <ReferenceStatusTag :status="statusTone(row.attendance_status)" :label="formatStatusLabel(row.attendance_status)" />
            </template>
          </el-table-column>
          <el-table-column prop="check_in_time" label="上班打卡" width="190" />
          <el-table-column prop="check_out_time" label="下班打卡" width="190" />
          <el-table-column prop="late_minutes" label="迟到(分)" width="100" align="right" />
          <el-table-column prop="early_leave_minutes" label="早退(分)" width="100" align="right" />
          <el-table-column prop="data_status" label="数据状态" width="120">
            <template #default="{ row }">
              <ReferenceStatusTag :status="statusTone(row.data_status)" :label="formatFlowStatus(row.data_status)" />
            </template>
          </el-table-column>
          <el-table-column label="操作" width="120">
            <template #default="{ row }">
              <el-button class="attendance-command__detail" link type="primary" @click="openDetail(row)">详情</el-button>
            </template>
          </el-table-column>
        </ReferenceDataTable>
      </div>

      <div class="attendance-command__mobile-list" data-testid="attendance-overview-mobile-list">
        <article v-for="row in items" :key="`${row.employee_id}-${row.business_date}`">
          <div class="attendance-command__mobile-title">
            <span>{{ row.employee_name || '-' }}</span>
            <em>{{ row.employee_no || '-' }}</em>
          </div>
          <div class="attendance-command__mobile-status">
            <ReferenceStatusTag :status="statusTone(row.attendance_status)" :label="formatStatusLabel(row.attendance_status)" />
            <ReferenceStatusTag :status="statusTone(row.data_status)" :label="formatFlowStatus(row.data_status)" />
          </div>
          <div class="attendance-command__mobile-grid">
            <span>上班打卡</span><strong>{{ row.check_in_time || '-' }}</strong>
            <span>下班打卡</span><strong>{{ row.check_out_time || '-' }}</strong>
            <span>迟到(分)</span><strong>{{ formatNumber(row.late_minutes) }}</strong>
            <span>早退(分)</span><strong>{{ formatNumber(row.early_leave_minutes) }}</strong>
          </div>
          <el-button class="attendance-command__mobile-detail" link type="primary" @click="openDetail(row)">详情</el-button>
        </article>
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { fetchAttendanceResults, processAttendance } from '../../api/attendance'
import ReferenceDataTable from '../../components/reference/ReferenceDataTable.vue'
import ReferenceStatusTag from '../../components/reference/ReferenceStatusTag.vue'
import { formatStatusLabel } from '../../utils/display'
import { inferBusinessDate } from '../../utils/shiftClock'

const router = useRouter()
const processing = ref(false)
const businessDate = ref(inferBusinessDate())
const items = ref([])
const summary = ref({ total: 0, normal: 0, abnormal: 0, pending_review: 0 })

const summaryCards = computed(() => [
  { key: 'total', label: '总人数', value: formatNumber(summary.value.total), accent: 'cyan' },
  { key: 'normal', label: '正常', value: formatNumber(summary.value.normal), accent: 'blue' },
  { key: 'abnormal', label: '异常', value: formatNumber(summary.value.abnormal), accent: 'alert' },
  { key: 'pending_review', label: '待闭环', value: formatNumber(summary.value.pending_review), accent: 'amber' }
])

function formatNumber(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return '0'
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(number)
}

async function load() {
  const data = await fetchAttendanceResults({ business_date: businessDate.value })
  items.value = data.items || []
  summary.value = data.summary || { total: 0, normal: 0, abnormal: 0, pending_review: 0 }
}

async function runProcess() {
  processing.value = true
  try {
    const result = await processAttendance({ start_date: businessDate.value, end_date: businessDate.value })
    ElMessage.success(`处理完成：结果 ${result.processed_results} 条，异常 ${result.generated_exceptions} 条`)
    await load()
  } finally {
    processing.value = false
  }
}

function openDetail(row) {
  router.push({
    name: 'attendance-detail',
    params: { employeeId: row.employee_id, businessDate: row.business_date }
  })
}

function formatFlowStatus(status) {
  const label = formatStatusLabel(status)
  return label === '已审核' ? '已校验' : label
}

function statusTone(status) {
  const value = String(status || '').toLowerCase()
  if (['normal', 'confirmed', 'success', 'auto_confirmed'].includes(value)) return 'success'
  if (['pending', 'reviewed', 'warning'].includes(value)) return 'warning'
  if (['abnormal', 'rejected', 'returned', 'failed', 'error'].includes(value)) return 'danger'
  return 'normal'
}

onMounted(load)
</script>

<style scoped>
.attendance-command {
  --attendance-cyan: #00f2ff;
  --attendance-blue: #74f5ff;
  --attendance-amber: #ffab00;
  --attendance-alert: #ff3d00;
  --attendance-bg: #06101f;
  --attendance-panel: rgba(12, 25, 42, 0.72);
  --attendance-line: rgba(0, 242, 255, 0.18);
  --attendance-muted: rgba(223, 226, 235, 0.66);
  color: var(--xt-text);
}

.attendance-command::before {
  position: fixed;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  content: '';
  background: transparent;
  background-size: auto, auto, 32px 32px, 32px 32px, auto;
}

.attendance-command__hero,
.attendance-command__matrix,
.attendance-command__stat,
.attendance-command__mobile-list article {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--xt-border);
  background: transparent;


}

.attendance-command__hero::after,
.attendance-command__matrix::after,
.attendance-command__stat::after {
  position: absolute;
  inset: 0;
  pointer-events: none;
  content: '';
  background: transparent;
  transform: translateX(-120%);

}

.attendance-command__hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  min-height: 152px;
  padding: 28px;
  border-radius: 4px;
}

.attendance-command__eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--xt-primary);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.16em;
}

.attendance-command__eyebrow::before {
  width: 8px;
  height: 8px;
  content: '';
  border-radius: 999px;
  background: transparent;

}

.attendance-command h1,
.attendance-command h2 {
  margin: 0;
  color: var(--xt-text);

  letter-spacing: -0.03em;
}

.attendance-command h1 {
  margin-top: 12px;
  font-size: clamp(34px, 5vw, 58px);
  line-height: 1;

}

.attendance-command__subtitle {
  position: relative;
  z-index: 1;
  max-width: 34em;
  margin: 10px 0 0;
  color: var(--xt-text-secondary);
  font-size: 13px;
  font-weight: 600;
}

.attendance-command h2 {
  margin-top: 8px;
  font-size: 24px;
}

.attendance-command__actions {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px;
  border: 1px solid var(--xt-border);
  border-radius: 4px;
  background: transparent;
}

.attendance-command__date {
  width: 178px;
}

.attendance-command :deep(.attendance-command__date .el-input__wrapper) {
  background: transparent;

}

.attendance-command :deep(.attendance-command__date .el-input__inner),
.attendance-command :deep(.attendance-command__date .el-input__prefix) {
  color: var(--xt-text);
}

.attendance-command__ghost,
.attendance-command__primary {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--xt-border);
  color: var(--xt-primary);
  font-weight: 600;
}

.attendance-command__ghost {
  background: transparent;
}

.attendance-command__primary {
  background: transparent;
}

.attendance-command__ghost:hover,
.attendance-command__primary:hover {
  border-color: var(--xt-border);
  background: transparent;

}

.attendance-command__stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.attendance-command__stat {
  min-height: 144px;
  padding: 20px;
  border-radius: 4px;
}

.attendance-command__stat-top {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.12em;
}

.attendance-command__led {
  width: 9px;
  height: 9px;
  border-radius: 999px;
  background: currentColor;


}

.attendance-command__stat strong {
  position: relative;
  z-index: 1;
  display: block;
  margin-top: 24px;
  color: var(--xt-primary);

  font-size: clamp(30px, 4vw, 46px);
  line-height: 1;

}

.attendance-command__stat small {
  position: relative;
  z-index: 1;
  display: block;
  margin-top: 8px;
  color: var(--xt-text-secondary);
  font-size: 12px;
}

.attendance-command__stat--blue strong,
.attendance-command__stat--blue .attendance-command__led {
  color: var(--xt-text);
}

.attendance-command__stat--amber strong,
.attendance-command__stat--amber .attendance-command__led {
  color: var(--xt-warning);
}

.attendance-command__stat--alert strong,
.attendance-command__stat--alert .attendance-command__led {
  color: var(--xt-text);
}

.attendance-command__matrix {
  border-radius: 4px;
}

.attendance-command__matrix-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 22px 24px;
  border-bottom: 1px solid var(--xt-border);
  background: transparent;
}

.attendance-command__matrix-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.attendance-command__matrix-meta span {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 5px 10px;
  border: 1px solid var(--xt-border);
  border-radius: 999px;
  background: transparent;
  color: var(--xt-text);
  font-size: 12px;
  font-weight: 600;
}

.attendance-command__table {
  padding: 16px;
}

.attendance-command__table :deep(.el-table) {
  --el-table-header-bg-color: rgba(0, 242, 255, 0.08);
  --el-table-tr-bg-color: transparent;
  --el-table-row-hover-bg-color: rgba(0, 242, 255, 0.08);
  --el-table-border-color: rgba(0, 242, 255, 0.14);
  --el-table-header-text-color: #74f5ff;
  --el-table-text-color: #dfe2eb;
  overflow: hidden;
  border: 1px solid var(--xt-border);
  border-radius: 4px;
  background: transparent;
}

.attendance-command__table :deep(.el-table th.el-table__cell) {
  font-size: 12px;
  letter-spacing: 0.08em;
  background: transparent;
}

.attendance-command__table :deep(.el-table th.el-table__cell > .cell) {
  color: var(--xt-text);
}

.attendance-command__table :deep(.el-table td.el-table__cell) {
  background: transparent;
}

.attendance-command__table :deep(.el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell) {
  background: transparent;
}

.attendance-command__detail {
  color: var(--xt-primary);
  font-weight: 600;
}

.attendance-command__mobile-list {
  display: none;
  padding: 16px;
}

.attendance-command__mobile-list article {
  border-radius: 4px;
  padding: 16px;
}

.attendance-command__mobile-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--xt-text);
  font-weight: 600;
}

.attendance-command__mobile-title em {
  padding: 4px 9px;
  border-radius: 999px;
  background: transparent;
  color: var(--xt-primary);
  font-size: 12px;
  font-style: normal;
}

.attendance-command__mobile-status {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 14px 0;
}

.attendance-command__mobile-grid {
  display: grid;
  grid-template-columns: minmax(76px, auto) 1fr;
  gap: 10px 14px;
  color: var(--xt-text-secondary);
  font-size: 13px;
}

.attendance-command__mobile-grid strong {
  color: var(--xt-text);
  text-align: right;
}

.attendance-command__mobile-detail {
  margin-top: 12px;
  color: var(--xt-primary);
  font-weight: 600;
}

@keyframes attendanceCommandSweep {
  0%,
  70% {
    transform: translateX(-120%);
  }

  100% {
    transform: translateX(120%);
  }
}

@keyframes attendanceCommandPulse {
  0%,
  100% {
    opacity: 0.56;
    transform: scale(0.88);
  }

  50% {
    opacity: 1;
    transform: scale(1.18);
  }
}

@media (max-width: 1080px) {
  .attendance-command__stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .attendance-command__hero,
  .attendance-command__matrix-head {
    align-items: stretch;
    flex-direction: column;
  }

  .attendance-command__hero {
    padding: 22px;
  }

  .attendance-command__actions {
    flex-direction: column;
    align-items: stretch;
  }

  .attendance-command__date {
    width: 100%;
  }

  .attendance-command__stats {
    grid-template-columns: 1fr;
  }

  .attendance-command__table {
    display: none;
  }

  .attendance-command__mobile-list {
    display: grid;
    gap: 12px;
  }
}
</style>
