<template>
  <div class="page-stack" v-loading="loading">
    <div class="page-header">
      <div>
        <h1>考勤详情</h1>
        <p>查看单个员工某业务日的打卡、自动结果和异常，并执行例外修正。</p>
      </div>
      <el-button @click="reload">刷新</el-button>
    </div>

    <el-card class="panel" v-if="detail">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="工号">{{ detail.result.employee_no }}</el-descriptions-item>
        <el-descriptions-item label="姓名">{{ detail.result.employee_name }}</el-descriptions-item>
        <el-descriptions-item label="业务日期">{{ detail.result.business_date }}</el-descriptions-item>
        <el-descriptions-item label="考勤状态">
          <ReferenceStatusTag :status="statusTone(detail.result.attendance_status)" :label="formatStatusLabel(detail.result.attendance_status)" />
        </el-descriptions-item>
        <el-descriptions-item label="上班打卡">{{ detail.result.check_in_time || '-' }}</el-descriptions-item>
        <el-descriptions-item label="下班打卡">{{ detail.result.check_out_time || '-' }}</el-descriptions-item>
        <el-descriptions-item label="迟到(分)">{{ detail.result.late_minutes }}</el-descriptions-item>
        <el-descriptions-item label="早退(分)">{{ detail.result.early_leave_minutes }}</el-descriptions-item>
        <el-descriptions-item label="数据状态">
          <ReferenceStatusTag :status="statusTone(detail.result.data_status)" :label="formatFlowStatus(detail.result.data_status)" />
        </el-descriptions-item>
        <el-descriptions-item label="例外修正">{{ formatBooleanLabel(detail.result.is_manual_override) }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card class="panel" v-if="detail">
      <template #header>
        <div style="font-weight: 700;">异常列表</div>
      </template>
      <ReferenceDataTable :data="detail.exceptions" stripe>
        <el-table-column label="异常类型" width="180">
          <template #default="{ row }">
            {{ formatExceptionTypeLabel(row.exception_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="exception_desc" label="说明" min-width="220" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <ReferenceStatusTag :status="statusTone(row.status)" :label="formatStatusLabel(row.status)" />
          </template>
        </el-table-column>
      </ReferenceDataTable>
    </el-card>

    <el-card class="panel" v-if="detail">
      <template #header>
        <div style="font-weight: 700;">例外修正</div>
      </template>
      <el-form :model="overrideForm" label-width="120px">
        <el-form-item label="考勤状态">
          <el-select v-model="overrideForm.attendance_status" style="width: 220px;">
            <el-option label="正常" value="normal" />
            <el-option label="异常" value="abnormal" />
            <el-option label="缺勤" value="absent" />
          </el-select>
        </el-form-item>
        <el-form-item label="上班打卡">
          <el-date-picker
            v-model="overrideForm.check_in_time"
            type="datetime"
            value-format="YYYY-MM-DDTHH:mm:ss"
            style="width: 280px;"
          />
        </el-form-item>
        <el-form-item label="下班打卡">
          <el-date-picker
            v-model="overrideForm.check_out_time"
            type="datetime"
            value-format="YYYY-MM-DDTHH:mm:ss"
            style="width: 280px;"
          />
        </el-form-item>
        <el-form-item label="迟到分钟">
          <el-input-number v-model="overrideForm.late_minutes" :min="0" />
        </el-form-item>
        <el-form-item label="早退分钟">
          <el-input-number v-model="overrideForm.early_leave_minutes" :min="0" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="overrideForm.remark" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="修正原因">
          <el-input v-model="overrideForm.override_reason" type="textarea" :rows="3" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="submitting" @click="submitOverride">提交修正</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'

import { fetchAttendanceDetail, overrideAttendanceResult } from '../../api/attendance'
import ReferenceDataTable from '../../components/reference/ReferenceDataTable.vue'
import ReferenceStatusTag from '../../components/reference/ReferenceStatusTag.vue'
import { formatBooleanLabel, formatExceptionTypeLabel, formatStatusLabel } from '../../utils/display'

const route = useRoute()
const loading = ref(false)
const submitting = ref(false)
const detail = ref(null)

const employeeId = computed(() => Number(route.params.employeeId))
const businessDate = computed(() => String(route.params.businessDate))

const overrideForm = reactive({
  attendance_status: 'normal',
  check_in_time: '',
  check_out_time: '',
  late_minutes: 0,
  early_leave_minutes: 0,
  remark: '',
  override_reason: ''
})

async function reload() {
  loading.value = true
  try {
    const data = await fetchAttendanceDetail(employeeId.value, businessDate.value)
    detail.value = data
    const result = data.result
    overrideForm.attendance_status = result.attendance_status
    overrideForm.check_in_time = result.check_in_time || ''
    overrideForm.check_out_time = result.check_out_time || ''
    overrideForm.late_minutes = result.late_minutes
    overrideForm.early_leave_minutes = result.early_leave_minutes
    overrideForm.remark = result.remark || ''
    overrideForm.override_reason = ''
  } finally {
    loading.value = false
  }
}

async function submitOverride() {
  if (!detail.value) return
  if (!overrideForm.override_reason.trim()) {
    ElMessage.warning('请填写修正原因')
    return
  }

  submitting.value = true
  try {
    await overrideAttendanceResult(detail.value.result.id, {
      attendance_status: overrideForm.attendance_status,
      check_in_time: overrideForm.check_in_time || null,
      check_out_time: overrideForm.check_out_time || null,
      late_minutes: overrideForm.late_minutes,
      early_leave_minutes: overrideForm.early_leave_minutes,
      remark: overrideForm.remark,
      override_reason: overrideForm.override_reason
    })
    ElMessage.success('修正成功')
    await reload()
  } finally {
    submitting.value = false
  }
}

function formatFlowStatus(status) {
  if (status === 'flagged') return '异常待闭环'
  const label = formatStatusLabel(status)
  return label === '已审核' ? '已校验' : label
}

function statusTone(status) {
  const value = String(status || '').toLowerCase()
  if (['normal', 'closed', 'confirmed', 'success', 'auto_confirmed'].includes(value)) return 'success'
  if (['pending', 'reviewed', 'open', 'warning', 'flagged'].includes(value)) return 'warning'
  if (['abnormal', 'absent', 'rejected', 'returned', 'failed', 'error'].includes(value)) return 'danger'
  return 'normal'
}

reload()
</script>
