<template>
  <div class="page-stack">
    <div class="page-header">
      <div>
        <h1>班次配置</h1>
      </div>
    </div>

    <el-card class="panel">
      <el-form inline>
        <el-form-item label="开始日期">
          <el-date-picker v-model="filters.start_date" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="结束日期">
          <el-date-picker v-model="filters.end_date" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="车间">
          <el-select v-model="filters.workshop_id" clearable style="width: 180px">
            <el-option v-for="item in workshops" :key="item.id" :label="item.name" :value="item.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="数据状态">
          <el-select v-model="filters.data_status" clearable style="width: 180px">
            <el-option label="待处理" value="pending" />
            <el-option label="已校验" value="reviewed" />
            <el-option label="已确认" value="confirmed" />
            <el-option label="已驳回" value="rejected" />
            <el-option label="已作废" value="voided" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="load">查询</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="panel">
      <ReferenceDataTable :data="items" stripe>
        <el-table-column prop="id" label="编号" width="70" />
        <el-table-column prop="business_date" label="业务日期" width="110" />
        <el-table-column prop="workshop_name" label="车间" width="100" />
        <el-table-column prop="team_name" label="班组" width="90" />
        <el-table-column prop="shift_code" label="班次" width="70" />
        <el-table-column prop="version_no" label="版本" width="70" />
        <el-table-column prop="output_weight" label="产出量" width="90" />
        <el-table-column prop="actual_headcount" label="实到" width="70" />
        <el-table-column prop="planned_headcount" label="计划" width="70" />
        <el-table-column label="数据状态" width="104">
          <template #default="{ row }">
            <ReferenceStatusTag :status="statusTone(row.data_status)" :label="formatFlowStatus(row.data_status)" />
          </template>
        </el-table-column>
        <el-table-column label="观察提示" min-width="150">
          <template #default="{ row }">
            <span>{{ observationLabel(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="90">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row.id)">详情</el-button>
          </template>
        </el-table-column>
      </ReferenceDataTable>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'

import { fetchWorkshops } from '../../api/master'
import { fetchShiftProductionData } from '../../api/production'
import ReferenceDataTable from '../../components/reference/ReferenceDataTable.vue'
import ReferenceStatusTag from '../../components/reference/ReferenceStatusTag.vue'
import { formatStatusLabel } from '../../utils/display'

const router = useRouter()

const filters = reactive({
  start_date: dayjs().format('YYYY-MM-DD'),
  end_date: dayjs().format('YYYY-MM-DD'),
  workshop_id: null,
  data_status: ''
})
const workshops = ref([])
const items = ref([])

function statusTone(status) {
  if (status === 'confirmed') return 'success'
  if (status === 'reviewed' || status === 'pending') return 'warning'
  if (status === 'rejected') return 'danger'
  return 'normal'
}

function formatFlowStatus(status) {
  const label = formatStatusLabel(status)
  return label === '已审核' ? '已校验' : label
}

function observationLabel(row) {
  if (row.data_status === 'rejected') return '存在驳回记录，请关注补录或修订情况'
  if (row.data_status === 'voided') return '记录已作废，请核对替代版本'
  if (row.data_status === 'pending') return '等待后续处理，请关注异常与完整性'
  if (row.data_status === 'reviewed') return '已进入中间状态，可继续观察后续结果'
  if (row.data_status === 'confirmed') return '当前版本已稳定，可查看详情追踪来源'
  return '查看详情了解当前记录状态'
}

function openDetail(id) {
  router.push({ name: 'shift-detail', params: { id } })
}

async function loadWorkshops() {
  workshops.value = await fetchWorkshops()
}

async function load() {
  const params = { ...filters }
  if (!params.workshop_id) delete params.workshop_id
  if (!params.data_status) delete params.data_status
  items.value = await fetchShiftProductionData(params)
}

onMounted(async () => {
  try {
    await loadWorkshops()
    await load()
  } catch {
    ElMessage.error('加载失败')
  }
})
</script>
