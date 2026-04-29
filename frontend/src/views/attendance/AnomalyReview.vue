<template>
  <div class="page-stack">
    <div class="page-header">
      <div>
        <h1>考勤异常处置</h1>
      </div>
      <div class="header-actions attendance-anomaly-toolbar">
        <el-date-picker
          v-model="filters.dateRange"
          type="daterange"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
          value-format="YYYY-MM-DD"
        />
        <el-select v-model="filters.workshopId" clearable placeholder="车间" style="width: 180px;">
          <el-option
            v-for="workshop in workshops"
            :key="workshop.id"
            :label="workshop.name"
            :value="workshop.id"
          />
        </el-select>
        <el-select v-model="filters.anomalyType" clearable placeholder="差异类型" style="width: 220px;">
          <el-option
            v-for="option in anomalyTypeOptions"
            :key="option.value"
            :label="option.label"
            :value="option.value"
          />
        </el-select>
        <el-button @click="load">查询</el-button>
      </div>
    </div>

    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-label">差异总数</div>
        <div class="stat-value">{{ filteredItems.length }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">待闭环</div>
        <div class="stat-value">{{ countByHrStatus('pending') }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">已核实</div>
        <div class="stat-value">{{ countByHrStatus('verified') }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">已处理</div>
        <div class="stat-value">{{ countByHrStatus('resolved') }}</div>
      </div>
    </div>

    <el-card class="panel">
      <ReferenceDataTable :data="filteredItems" stripe v-loading="loading">
        <el-table-column prop="business_date" label="日期" width="108" />
        <el-table-column prop="workshop_name" label="车间" width="100" />
        <el-table-column prop="machine_name" label="机台" width="96" />
        <el-table-column prop="shift_name" label="班次" width="88" />
        <el-table-column prop="employee_name" label="姓名" width="110" />
        <el-table-column label="钉钉记录" min-width="142">
          <template #default="{ row }">{{ formatClock(row) }}</template>
        </el-table-column>
        <el-table-column label="班长确认" min-width="140">
          <template #default="{ row }">
            {{ formatStatusLabel(row.auto_status) }} → {{ formatStatusLabel(row.leader_status) }}
          </template>
        </el-table-column>
        <el-table-column prop="override_reason" label="差异原因" min-width="150" />
        <el-table-column label="人事状态" width="116">
          <template #default="{ row }">
            <ReferenceStatusTag :status="hrStatusTagType(row.hr_status)" :label="hrStatusLabel(row.hr_status)" />
          </template>
        </el-table-column>
        <el-table-column label="处理" width="316" fixed="right">
          <template #default="{ row }">
            <div class="attendance-anomaly-actions">
              <el-select
                v-model="row._next_hr_status"
                class="attendance-anomaly-actions__select"
                placeholder="选择状态"
                size="small"
              >
                <el-option label="待处理" value="pending" />
                <el-option label="已核实" value="verified" />
                <el-option label="已处理" value="resolved" />
              </el-select>
              <el-input
                v-model="row._review_note"
                class="attendance-anomaly-actions__note"
                size="small"
                placeholder="备注"
                maxlength="80"
              />
              <el-button
                class="attendance-anomaly-actions__save"
                type="primary"
                size="small"
                :loading="updatingIds.has(row.detail_id)"
                @click="applyReview(row)"
              >
                保存
              </el-button>
            </div>
          </template>
        </el-table-column>
      </ReferenceDataTable>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'

import { fetchAttendanceAnomalies, reviewAttendanceAnomaly } from '../../api/attendance'
import { fetchWorkshops } from '../../api/master'
import ReferenceDataTable from '../../components/reference/ReferenceDataTable.vue'
import ReferenceStatusTag from '../../components/reference/ReferenceStatusTag.vue'
import { formatStatusLabel } from '../../utils/display'

const loading = ref(false)
const items = ref([])
const workshops = ref([])
const updatingIds = ref(new Set())

const filters = reactive({
  dateRange: [dayjs().subtract(6, 'day').format('YYYY-MM-DD'), dayjs().format('YYYY-MM-DD')],
  workshopId: '',
  anomalyType: ''
})

const anomalyTypeOptions = computed(() => {
  const seen = new Map()
  items.value.forEach((item) => {
    const value = `${item.auto_status}->${item.leader_status}`
    if (!seen.has(value)) {
      seen.set(value, {
        value,
        label: `${formatStatusLabel(item.auto_status)} → ${formatStatusLabel(item.leader_status)}`
      })
    }
  })
  return Array.from(seen.values())
})

const filteredItems = computed(() => {
  return items.value.filter((item) => {
    if (!filters.anomalyType) return true
    return `${item.auto_status}->${item.leader_status}` === filters.anomalyType
  })
})

function normalizeItems(rows) {
  items.value = (rows || []).map((item) => ({
    ...item,
    _next_hr_status: item.hr_status || 'pending',
    _review_note: ''
  }))
}

function formatClock(row) {
  if (!row.dingtalk_clock_in && !row.dingtalk_clock_out) return '无记录'
  return `${row.dingtalk_clock_in || '--'} → ${row.dingtalk_clock_out || '--'}`
}

function hrStatusLabel(value) {
  if (value === 'verified') return '已核实'
  if (value === 'resolved') return '已处理'
  return '待处理'
}

function hrStatusTagType(value) {
  if (value === 'verified') return 'success'
  if (value === 'resolved') return 'success'
  return 'warning'
}

function countByHrStatus(status) {
  return filteredItems.value.filter((item) => item.hr_status === status).length
}

async function load() {
  loading.value = true
  try {
    const rows = await fetchAttendanceAnomalies({
      workshop_id: filters.workshopId || undefined,
      date_from: filters.dateRange?.[0],
      date_to: filters.dateRange?.[1]
    })
    normalizeItems(rows)
  } finally {
    loading.value = false
  }
}

async function applyReview(row) {
  const next = row._next_hr_status || 'pending'
  const nextSet = new Set(updatingIds.value)
  nextSet.add(row.detail_id)
  updatingIds.value = nextSet
  try {
    const payload = await reviewAttendanceAnomaly(row.detail_id, {
      hr_status: next,
      note: row._review_note || null
    })
    row.hr_status = payload.hr_status
    row._review_note = payload.note || ''
    ElMessage.success('处置状态已更新')
  } finally {
    const remaining = new Set(updatingIds.value)
    remaining.delete(row.detail_id)
    updatingIds.value = remaining
  }
}

onMounted(async () => {
  workshops.value = await fetchWorkshops()
  await load()
})
</script>

<style scoped>
.attendance-anomaly-actions {
  display: grid;
  grid-template-columns: 92px minmax(112px, 1fr) 54px;
  gap: 6px;
  align-items: center;
}

.attendance-anomaly-actions__select,
.attendance-anomaly-actions__note {
  min-width: 0;
}

.attendance-anomaly-actions__save {
  min-width: 54px;
  padding: 0 10px;
}

.attendance-anomaly-actions :deep(.el-select__wrapper),
.attendance-anomaly-actions :deep(.el-input__wrapper) {
  min-height: 30px;
  border-radius: var(--xt-radius-md);
  box-shadow: 0 0 0 1px var(--xt-border-light) inset;
}
</style>
