<template>
  <div class="page-stack">
    <div class="page-header">
      <div>
        <h1>考勤异常处置</h1>
      </div>
      <div class="attendance-anomaly-toolbar">
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
        <div class="stat-label">待处理</div>
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
      <el-table :data="filteredItems" stripe v-loading="loading">
        <el-table-column prop="business_date" label="日期" width="120" />
        <el-table-column prop="workshop_name" label="车间" min-width="140" />
        <el-table-column prop="machine_name" label="机台" width="100" />
        <el-table-column prop="shift_name" label="班次" width="100" />
        <el-table-column prop="employee_name" label="姓名" width="120" />
        <el-table-column label="钉钉记录" min-width="170">
          <template #default="{ row }">{{ formatClock(row) }}</template>
        </el-table-column>
        <el-table-column label="班长确认" min-width="150">
          <template #default="{ row }">
            {{ formatStatusLabel(row.auto_status) }} → {{ formatStatusLabel(row.leader_status) }}
          </template>
        </el-table-column>
        <el-table-column prop="override_reason" label="差异原因" min-width="220" />
        <el-table-column label="人事状态" width="150">
          <template #default="{ row }">
            <el-tag :type="hrStatusTagType(row.hr_status)" effect="light">
              {{ hrStatusLabel(row.hr_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="处理" min-width="260">
          <template #default="{ row }">
            <div class="attendance-anomaly-actions">
              <el-select
                v-model="row._next_hr_status"
                placeholder="选择状态"
                size="small"
                style="width: 110px;"
              >
                <el-option label="待处理" value="pending" />
                <el-option label="已核实" value="verified" />
                <el-option label="已处理" value="resolved" />
              </el-select>
              <el-input
                v-model="row._review_note"
                size="small"
                placeholder="处置备注"
                maxlength="200"
                show-word-limit
              />
              <el-button
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
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'

import { fetchAttendanceAnomalies, reviewAttendanceAnomaly } from '../../api/attendance'
import { fetchWorkshops } from '../../api/master'
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
  if (value === 'resolved') return 'info'
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
    ElMessage.success('复核状态已更新')
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
