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
import {
  formatReconciliationDiffValue,
  formatReconciliationDimension,
  formatReconciliationFieldLabel,
  formatReconciliationSourceLabel,
  formatReconciliationValue,
} from '../../utils/reconciliationDisplay'

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
