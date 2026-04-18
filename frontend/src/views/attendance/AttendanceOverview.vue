<template>
  <div class="page-stack">
    <div class="page-header">
      <div>
        <h1>考勤总览</h1>
        <p>按业务日期查看考勤结果，并触发自动处理流程。</p>
      </div>
      <div style="display: flex; gap: 10px;">
        <el-date-picker v-model="businessDate" type="date" value-format="YYYY-MM-DD" />
        <el-button @click="load">查询</el-button>
        <el-button type="primary" :loading="processing" @click="runProcess">自动处理</el-button>
      </div>
    </div>

    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-label">总人数</div>
        <div class="stat-value">{{ summary.total }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">正常</div>
        <div class="stat-value">{{ summary.normal }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">异常</div>
        <div class="stat-value">{{ summary.abnormal }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">待处理</div>
        <div class="stat-value">{{ summary.pending_review }}</div>
      </div>
    </div>

    <el-card class="panel">
      <el-table :data="items" stripe>
        <el-table-column prop="employee_no" label="工号" width="120" />
        <el-table-column prop="employee_name" label="姓名" width="140" />
        <el-table-column prop="attendance_status" label="状态" width="130">
          <template #default="{ row }">
            <el-tag :type="row.attendance_status === 'normal' ? 'success' : 'danger'">{{ formatStatusLabel(row.attendance_status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="check_in_time" label="上班打卡" width="190" />
        <el-table-column prop="check_out_time" label="下班打卡" width="190" />
        <el-table-column prop="late_minutes" label="迟到(分)" width="100" />
        <el-table-column prop="early_leave_minutes" label="早退(分)" width="100" />
        <el-table-column prop="data_status" label="数据状态" width="120">
          <template #default="{ row }">
            {{ formatStatusLabel(row.data_status) }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'

import { fetchAttendanceResults, processAttendance } from '../../api/attendance'
import { formatStatusLabel } from '../../utils/display'

const router = useRouter()
const processing = ref(false)
const businessDate = ref(dayjs().format('YYYY-MM-DD'))
const items = ref([])
const summary = ref({ total: 0, normal: 0, abnormal: 0, pending_review: 0 })

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

onMounted(load)
</script>
