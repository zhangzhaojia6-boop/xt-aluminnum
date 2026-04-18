<template>
  <div class="page-stack">
    <div class="page-header">
      <div>
        <h1>班次观察台</h1>
        <p>导入并查看生产班次数据，主路径聚焦状态、异常说明与版本变化，不展示审核确认按钮。</p>
      </div>
      <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
        <el-input v-model="templateCode" placeholder="模板编码（可选）" style="width: 180px" />
        <el-select v-model="duplicateStrategy" style="width: 220px">
          <el-option label="重复时默认拒绝" value="reject" />
          <el-option label="新数据覆盖旧版本" value="supersede" />
        </el-select>
        <input type="file" accept=".csv,.xlsx" @change="onFileChange" />
        <el-button type="primary" :loading="importing" :disabled="!uploadFile" @click="onImport">导入生产班次数据</el-button>
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
            <el-option label="已审核" value="reviewed" />
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
      <el-table :data="items" stripe>
        <el-table-column prop="id" label="编号" width="80" />
        <el-table-column prop="business_date" label="业务日期" width="120" />
        <el-table-column prop="workshop_name" label="车间" width="140" />
        <el-table-column prop="team_name" label="班组" width="140" />
        <el-table-column prop="shift_code" label="班次" width="90" />
        <el-table-column prop="version_no" label="版本" width="80" />
        <el-table-column prop="output_weight" label="产出量" width="110" />
        <el-table-column prop="actual_headcount" label="实到" width="90" />
        <el-table-column prop="planned_headcount" label="计划" width="90" />
        <el-table-column label="数据状态" width="120">
          <template #default="{ row }">
            <el-tag :type="statusType(row.data_status)">{{ formatStatusLabel(row.data_status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="观察提示" min-width="180">
          <template #default="{ row }">
            <span>{{ observationLabel(row) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" min-width="120">
          <template #default="{ row }">
            <el-button link type="primary" @click="openDetail(row.id)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'

import { fetchWorkshops } from '../../api/master'
import { fetchShiftProductionData, importProductionFile } from '../../api/production'
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
const importing = ref(false)
const uploadFile = ref(null)
const templateCode = ref('')
const duplicateStrategy = ref('reject')

function statusType(status) {
  if (status === 'confirmed') return 'success'
  if (status === 'reviewed') return 'warning'
  if (status === 'rejected') return 'danger'
  if (status === 'voided') return 'info'
  return ''
}

function observationLabel(row) {
  if (row.data_status === 'rejected') return '存在驳回记录，请关注补录或修订情况'
  if (row.data_status === 'voided') return '记录已作废，请核对替代版本'
  if (row.data_status === 'pending') return '等待后续处理，请关注异常与完整性'
  if (row.data_status === 'reviewed') return '已进入中间状态，可继续观察后续结果'
  if (row.data_status === 'confirmed') return '当前版本已稳定，可查看详情追踪来源'
  return '查看详情了解当前记录状态'
}

function onFileChange(event) {
  uploadFile.value = event.target.files?.[0] || null
}

async function onImport() {
  if (!uploadFile.value) return
  importing.value = true
  try {
    const result = await importProductionFile(uploadFile.value, templateCode.value || null, duplicateStrategy.value)
    const summary = result.summary
    ElMessage.success(`导入完成：成功 ${summary.success_rows}，失败 ${summary.failed_rows}，跳过 ${summary.skipped_rows}`)
    await load()
  } catch {
    ElMessage.error('导入失败')
  } finally {
    importing.value = false
  }
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
