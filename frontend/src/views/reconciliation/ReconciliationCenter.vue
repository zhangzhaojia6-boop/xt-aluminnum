<template>
  <ReferencePageFrame module-number="09" title="差异核对中心" :tags="['多源核对', '差异闭环', '发布闸门']" class="reconciliation-center">
    <template #actions>
      <el-date-picker v-model="filters.business_date" type="date" value-format="YYYY-MM-DD" />
      <el-select v-model="filters.reconciliation_type" clearable placeholder="核对类型" style="width: 220px">
        <el-option label="考勤与生产核对" value="attendance_vs_production" />
        <el-option label="生产与 MES 核对" value="production_vs_mes" />
        <el-option label="能耗与生产核对" value="energy_vs_production" />
      </el-select>
      <el-button type="primary" @click="onGenerate">生成差异</el-button>
    </template>

    <ReferenceModuleCard module-number="09" title="核对筛选">
      <el-form inline>
        <el-form-item label="业务日期">
          <el-date-picker v-model="filters.business_date" type="date" value-format="YYYY-MM-DD" />
        </el-form-item>
        <el-form-item label="核对类型">
          <el-select v-model="filters.reconciliation_type" clearable style="width: 220px">
            <el-option label="考勤与生产核对" value="attendance_vs_production" />
            <el-option label="生产与 MES 核对" value="production_vs_mes" />
            <el-option label="能耗与生产核对" value="energy_vs_production" />
          </el-select>
        </el-form-item>
        <el-form-item label="处理状态">
          <el-select v-model="filters.status" clearable style="width: 160px">
            <el-option label="待处理" value="open" />
            <el-option label="已确认" value="confirmed" />
            <el-option label="已忽略" value="ignored" />
            <el-option label="已修正" value="corrected" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="load">查询</el-button>
        </el-form-item>
      </el-form>
    </ReferenceModuleCard>

    <ReferenceModuleCard module-number="09" title="差异清单">
      <ReferenceDataTable :data="items" stripe>
        <el-table-column prop="id" label="编号" width="70" />
        <el-table-column prop="business_date" label="业务日期" width="110" />
        <el-table-column prop="reconciliation_type" label="核对类型" width="150">
          <template #default="{ row }">
            {{ formatReconciliationTypeLabel(row.reconciliation_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="dimension_key" label="维度" width="110" />
        <el-table-column prop="field_name" label="字段" width="120" />
        <el-table-column prop="source_a_value" label="来源 A" width="96" />
        <el-table-column prop="source_b_value" label="来源 B" width="96" />
        <el-table-column prop="diff_value" label="差异值" width="88" />
        <el-table-column prop="status" label="处理状态" width="110">
          <template #default="{ row }">
            <ReferenceStatusTag :status="statusTone(row.status)" :label="formatStatusLabel(row.status)" />
          </template>
        </el-table-column>
        <el-table-column label="操作" width="220">
          <template #default="{ row }">
            <div class="reconciliation-center__actions">
              <el-button link type="primary" @click="openDetail(row.id)">详情</el-button>
              <el-button v-if="row.status === 'open'" link type="success" @click="onConfirm(row)">确认</el-button>
              <el-button v-if="row.status === 'open'" link type="warning" @click="onIgnore(row)">忽略</el-button>
              <el-button v-if="row.status === 'open'" link type="danger" @click="onCorrect(row)">修正</el-button>
            </div>
          </template>
        </el-table-column>
      </ReferenceDataTable>
    </ReferenceModuleCard>
  </ReferencePageFrame>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'
import { ElMessage, ElMessageBox } from 'element-plus'

import {
  confirmReconciliationItem,
  correctReconciliationItem,
  fetchReconciliationItems,
  generateReconciliation,
  ignoreReconciliationItem
} from '../../api/reconciliation'
import ReferenceDataTable from '../../components/reference/ReferenceDataTable.vue'
import ReferenceModuleCard from '../../components/reference/ReferenceModuleCard.vue'
import ReferencePageFrame from '../../components/reference/ReferencePageFrame.vue'
import ReferenceStatusTag from '../../components/reference/ReferenceStatusTag.vue'
import { formatReconciliationTypeLabel, formatStatusLabel } from '../../utils/display'

const router = useRouter()
const items = ref([])
const filters = reactive({
  business_date: dayjs().format('YYYY-MM-DD'),
  reconciliation_type: '',
  status: ''
})

async function load() {
  const params = { ...filters }
  if (!params.reconciliation_type) delete params.reconciliation_type
  if (!params.status) delete params.status
  items.value = await fetchReconciliationItems(params)
}

async function onGenerate() {
  try {
    const payload = {
      business_date: filters.business_date,
      reconciliation_type: filters.reconciliation_type || undefined
    }
    await generateReconciliation(payload)
    ElMessage.success('差异清单已生成')
    await load()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '生成失败')
  }
}

function openDetail(id) {
  router.push({ name: 'reconciliation-detail', params: { id } })
}

function statusTone(status) {
  const value = String(status || '').toLowerCase()
  if (['confirmed', 'corrected', 'resolved', 'done'].includes(value)) return 'success'
  if (['open', 'pending'].includes(value)) return 'warning'
  if (['blocked', 'failed', 'error'].includes(value)) return 'danger'
  return 'normal'
}

async function onConfirm(row) {
  await confirmReconciliationItem(row.id, '已确认业务口径')
  ElMessage.success('已确认')
  await load()
}

async function onIgnore(row) {
  await ignoreReconciliationItem(row.id, '当前无需处理')
  ElMessage.success('已忽略')
  await load()
}

async function onCorrect(row) {
  const { value } = await ElMessageBox.prompt('请输入修正说明', '修正说明', {
    confirmButtonText: '提交',
    cancelButtonText: '取消',
    inputType: 'text'
  })
  await correctReconciliationItem(row.id, value)
  ElMessage.success('已修正')
  await load()
}

onMounted(load)
</script>

<style scoped>
.reconciliation-center__actions {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.reconciliation-center__actions :deep(.el-button + .el-button) {
  margin-left: 0;
}
</style>
