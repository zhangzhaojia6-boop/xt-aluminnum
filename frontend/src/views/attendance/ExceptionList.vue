<template>
  <div class="page-stack">
    <div class="page-header">
      <div>
        <h1>异常清单</h1>
        <p>筛选考勤异常并完成例外处置闭环。</p>
      </div>
      <div class="header-actions">
        <el-date-picker v-model="filters.businessDate" type="date" value-format="YYYY-MM-DD" />
        <el-select v-model="filters.exceptionType" clearable placeholder="异常类型" style="width: 180px;">
          <el-option label="缺上班卡" value="missing_checkin" />
          <el-option label="缺下班卡" value="missing_checkout" />
          <el-option label="无排班" value="no_schedule" />
          <el-option label="有排班无打卡" value="no_clock_with_schedule" />
          <el-option label="迟到" value="late" />
          <el-option label="早退" value="early_leave" />
          <el-option label="班次不匹配" value="shift_mismatch" />
          <el-option label="重复打卡" value="duplicate_clock" />
        </el-select>
        <el-button @click="load">查询</el-button>
      </div>
    </div>

    <el-card class="panel">
      <ReferenceDataTable :data="items" stripe>
        <el-table-column prop="business_date" label="业务日期" width="130" />
        <el-table-column prop="employee_no" label="工号" width="120" />
        <el-table-column prop="employee_name" label="姓名" width="140" />
        <el-table-column prop="exception_type" label="异常类型" width="180">
          <template #default="{ row }">
            {{ formatExceptionTypeLabel(row.exception_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="exception_desc" label="说明" min-width="220" />
        <el-table-column prop="status" label="状态" width="120">
          <template #default="{ row }">
            <ReferenceStatusTag :status="row.status === 'open' ? 'danger' : 'success'" :label="formatStatusLabel(row.status)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="210">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
            <el-button link type="warning" @click="openResolveDialog(row)">处理</el-button>
          </template>
        </el-table-column>
      </ReferenceDataTable>
    </el-card>

    <el-dialog v-model="resolveDialog.visible" title="处理异常" width="480px">
      <el-form label-width="100px">
        <el-form-item label="异常类型">
          <span>{{ formatExceptionTypeLabel(resolveDialog.row?.exception_type) }}</span>
        </el-form-item>
        <el-form-item label="处理动作">
          <el-radio-group v-model="resolveDialog.action">
            <el-radio label="confirmed">确认无误</el-radio>
            <el-radio label="corrected">已更正</el-radio>
            <el-radio label="ignored">忽略</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="resolveDialog.note" type="textarea" :rows="3" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resolveDialog.visible = false">取消</el-button>
        <el-button type="primary" @click="submitResolve">提交</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'

import { fetchAttendanceExceptions, resolveAttendanceException } from '../../api/attendance'
import ReferenceDataTable from '../../components/reference/ReferenceDataTable.vue'
import ReferenceStatusTag from '../../components/reference/ReferenceStatusTag.vue'
import { formatExceptionTypeLabel, formatStatusLabel } from '../../utils/display'

const router = useRouter()
const items = ref([])

const filters = reactive({
  businessDate: dayjs().format('YYYY-MM-DD'),
  exceptionType: ''
})

const resolveDialog = reactive({
  visible: false,
  row: null,
  action: 'confirmed',
  note: ''
})

async function load() {
  const data = await fetchAttendanceExceptions({
    business_date: filters.businessDate,
    exception_type: filters.exceptionType || undefined
  })
  items.value = Array.isArray(data) ? data : []
}

function openResolveDialog(row) {
  resolveDialog.visible = true
  resolveDialog.row = row
  resolveDialog.action = 'confirmed'
  resolveDialog.note = ''
}

async function submitResolve() {
  if (!resolveDialog.row) return
  await resolveAttendanceException(resolveDialog.row.id, {
    action: resolveDialog.action,
    note: resolveDialog.note
  })
  ElMessage.success('处理完成')
  resolveDialog.visible = false
  await load()
}

function openDetail(row) {
  router.push({
    name: 'attendance-detail',
    params: { employeeId: row.employee_id, businessDate: row.business_date }
  })
}

onMounted(load)
</script>
