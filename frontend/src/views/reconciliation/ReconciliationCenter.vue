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
        <el-table-column prop="dimension_key" label="机列/维度" width="130">
          <template #default="{ row }">
            {{ formatReconciliationDimension(row.dimension_key) }}
          </template>
        </el-table-column>
        <el-table-column prop="field_name" label="核对字段" width="120">
          <template #default="{ row }">
            {{ formatReconciliationFieldLabel(row.field_name) }}
          </template>
        </el-table-column>
        <el-table-column prop="source_a_value" label="填报侧" min-width="136">
          <template #default="{ row }">
            <div class="reconciliation-center__value">
              <span class="reconciliation-center__source">{{ formatReconciliationSourceLabel(row.source_a) }}</span>
              <span>{{ formatReconciliationValue(row.source_a_value, row.field_name) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="source_b_value" label="对照侧" min-width="136">
          <template #default="{ row }">
            <div class="reconciliation-center__value">
              <span class="reconciliation-center__source">{{ formatReconciliationSourceLabel(row.source_b) }}</span>
              <span>{{ formatReconciliationValue(row.source_b_value, row.field_name) }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="diff_value" label="差异" width="96">
          <template #default="{ row }">
            {{ formatReconciliationDiffValue(row) }}
          </template>
        </el-table-column>
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
import { useRoute, useRouter } from 'vue-router'
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
import {
  RECONCILIATION_DISPOSITION_REQUIRED_MESSAGE,
  hasReconciliationDispositionNote,
  normalizeReconciliationDispositionNote,
} from '../../utils/reconciliationDispositionValidation'

const route = useRoute()
const router = useRouter()
const items = ref([])
const reconciliationDispositionPromptOptions = {
  confirmButtonText: '提交',
  cancelButtonText: '取消',
  inputType: 'text',
  inputValidator: hasReconciliationDispositionNote,
  inputErrorMessage: RECONCILIATION_DISPOSITION_REQUIRED_MESSAGE,
}
const filters = reactive({
  business_date: normalizeQueryFilter(route.query.business_date) || dayjs().format('YYYY-MM-DD'),
  reconciliation_type: normalizeQueryFilter(route.query.reconciliation_type),
  status: normalizeQueryFilter(route.query.status)
})

function normalizeQueryFilter(value) {
  if (Array.isArray(value)) return String(value[0] || '')
  return typeof value === 'string' ? value : ''
}

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
  router.push({
    name: 'reconciliation-detail',
    params: { id },
    query: buildDesktopPreservingQuery()
  })
}

function statusTone(status) {
  const value = String(status || '').toLowerCase()
  if (['confirmed', 'corrected', 'resolved', 'done'].includes(value)) return 'success'
  if (['open', 'pending'].includes(value)) return 'warning'
  if (['blocked', 'failed', 'error'].includes(value)) return 'danger'
  return 'normal'
}

function formatReconciliationDimension(value) {
  const text = String(value || '').trim()
  if (!text) return '-'
  if (!text.includes(':')) return text

  const labels = {
    workshop: '车间',
    workshop_name: '车间',
    shift: '班次',
    shift_name: '班次',
    team: '班组',
    team_name: '班组',
    machine: '机列',
    machine_id: '机列',
    machine_line: '机列',
    tracking_card_no: '跟踪卡'
  }

  const parts = text
    .split('|')
    .map((part) => {
      const separatorIndex = part.indexOf(':')
      if (separatorIndex === -1) return ''
      const key = part.slice(0, separatorIndex)
      const rawValue = part.slice(separatorIndex + 1)
      const normalizedValue = rawValue && rawValue !== 'None' && rawValue !== 'null' ? rawValue : ''
      if (!normalizedValue) return ''
      return `${labels[key] || key} ${normalizedValue}`
    })
    .filter(Boolean)

  return parts.length ? parts.join(' / ') : text
}

function formatReconciliationFieldLabel(fieldName) {
  const labels = {
    output_weight: '产出重量',
    input_weight: '投入重量',
    headcount: '人数',
    energy_total: '能耗'
  }
  return labels[fieldName] || fieldName || '-'
}

function formatReconciliationSourceLabel(source) {
  const labels = {
    attendance_results: '考勤',
    production: '填报端产量',
    shift_production_data: '填报端产量',
    mes: '外部 MES',
    mes_export: '外部 MES',
    energy: '能耗'
  }
  return labels[source] || source || '-'
}

function formatReconciliationValue(value, fieldName) {
  const formatted = formatCompactNumber(value)
  if (formatted === '-') return formatted
  return `${formatted}${reconciliationFieldUnit(fieldName)}`
}

function formatReconciliationDiffValue(item = {}) {
  const formatted = formatCompactNumber(item.diff_value)
  if (formatted === '-') return formatted
  const diff = Number(item.diff_value)
  const sign = Number.isNaN(diff) || diff <= 0 ? '' : '+'
  return `${sign}${formatted}${reconciliationFieldUnit(item.field_name)}`
}

function formatCompactNumber(value) {
  if (value === null || value === undefined || value === '') return '-'
  const number = Number(value)
  if (Number.isNaN(number)) return String(value)
  return number.toFixed(3).replace(/\.?0+$/, '')
}

function reconciliationFieldUnit(fieldName) {
  const value = String(fieldName || '').toLowerCase()
  if (value === 'output_weight' || value === 'input_weight') return ' 吨'
  if (String(fieldName || '').includes('重量')) return ' 吨'
  if (value === 'headcount' || String(fieldName || '').includes('人数')) return ' 人'
  if (value === 'energy_total' || String(fieldName || '').includes('能耗')) return ' kWh'
  return ''
}

function buildDesktopPreservingQuery() {
  return route.query.desktop === '1' ? { desktop: '1' } : {}
}

async function onConfirm(row) {
  const note = await promptForReconciliationNote('请输入确认说明', '确认差异')
  await confirmReconciliationItem(row.id, note)
  ElMessage.success('已确认')
  await load()
}

async function onIgnore(row) {
  const note = await promptForReconciliationNote('请输入忽略说明', '忽略差异')
  await ignoreReconciliationItem(row.id, note)
  ElMessage.success('已忽略')
  await load()
}

async function onCorrect(row) {
  const note = await promptForReconciliationNote('请输入修正说明', '修正说明')
  await correctReconciliationItem(row.id, note)
  ElMessage.success('已修正')
  await load()
}

async function promptForReconciliationNote(message, title) {
  const { value } = await ElMessageBox.prompt(message, title, {
    ...reconciliationDispositionPromptOptions,
  })
  return normalizeReconciliationDispositionNote(value)
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

.reconciliation-center__value {
  display: grid;
  gap: 2px;
  line-height: 1.35;
}

.reconciliation-center__source {
  color: var(--xt-text-secondary);
  font-size: 12px;
}
</style>
