<template>
  <div class="page-stack">
    <div class="page-header">
      <div>
        <h1>差异详情</h1>
      </div>
      <div class="reconciliation-detail__actions">
        <el-button @click="backToCenter">返回核对中心</el-button>
        <el-button @click="load">刷新</el-button>
      </div>
    </div>

    <div v-if="item" class="reconciliation-detail__fields">
      <XtFieldGroup title="结论区" tier="primary" :items="primaryFields" />
      <XtFieldGroup title="来源区" tier="supporting" :items="supportingFields" />
      <XtFieldGroup title="审计区" tier="audit" :items="auditFields" collapsed />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { fetchReconciliationItems } from '../../api/reconciliation'
import { XtFieldGroup } from '../../components/xt'
import { formatReconciliationTypeLabel, formatStatusLabel } from '../../utils/display'

const route = useRoute()
const router = useRouter()
const item = ref(null)
const primaryFields = computed(() => [
  { label: '业务日期', value: item.value?.business_date },
  { label: '差异类型', value: formatReconciliationTypeLabel(item.value?.reconciliation_type) },
  { label: '处理状态', value: formatStatusLabel(item.value?.status) },
  { label: '差异', value: formatReconciliationDiffValue(item.value) },
  { label: '核对字段', value: formatReconciliationFieldLabel(item.value?.field_name) }
])
const supportingFields = computed(() => [
  { label: '机列/维度', value: formatReconciliationDimension(item.value?.dimension_key) },
  { label: '填报侧', value: formatReconciliationSourceLabel(item.value?.source_a) },
  { label: '填报侧值', value: formatReconciliationValue(item.value?.source_a_value, item.value?.field_name) },
  { label: '对照侧', value: formatReconciliationSourceLabel(item.value?.source_b) },
  { label: '对照侧值', value: formatReconciliationValue(item.value?.source_b_value, item.value?.field_name) },
  { label: '处理说明', value: item.value?.resolve_note }
])
const auditFields = computed(() => [
  { label: '差异编号', value: item.value?.id },
  { label: '处理人', value: item.value?.resolved_by },
  { label: '处理时间', value: item.value?.resolved_at }
])

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

function formatReconciliationDiffValue(currentItem = {}) {
  const formatted = formatCompactNumber(currentItem?.diff_value)
  if (formatted === '-') return formatted
  const diff = Number(currentItem?.diff_value)
  const sign = Number.isNaN(diff) || diff <= 0 ? '' : '+'
  return `${sign}${formatted}${reconciliationFieldUnit(currentItem?.field_name)}`
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

async function load() {
  const data = await fetchReconciliationItems({ item_id: route.params.id })
  item.value = data && data.length ? data[0] : null
}

function backToCenter() {
  const query = {}
  for (const key of ['business_date', 'reconciliation_type', 'status', 'desktop']) {
    if (typeof route.query[key] === 'string' && route.query[key]) query[key] = route.query[key]
  }
  if (!query.business_date && item.value?.business_date) query.business_date = item.value.business_date
  if (!query.status && item.value?.status) query.status = item.value.status
  router.push({ name: 'review-reconciliation-center', query })
}

onMounted(load)
</script>

<style scoped>
.reconciliation-detail__actions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--xt-space-2);
}

.reconciliation-detail__fields {
  display: grid;
  gap: var(--xt-space-3);
}
</style>
