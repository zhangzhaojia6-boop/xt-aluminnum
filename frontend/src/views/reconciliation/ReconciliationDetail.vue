<template>
  <div class="page-stack">
    <div class="page-header">
      <div>
        <h1>差异详情</h1>
      </div>
      <el-button @click="load">刷新</el-button>
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
import { useRoute } from 'vue-router'

import { fetchReconciliationItems } from '../../api/reconciliation'
import { XtFieldGroup } from '../../components/xt'
import { formatReconciliationTypeLabel, formatSourceTypeLabel, formatStatusLabel } from '../../utils/display'

const route = useRoute()
const item = ref(null)
const primaryFields = computed(() => [
  { label: '业务日期', value: item.value?.business_date },
  { label: '差异类型', value: formatReconciliationTypeLabel(item.value?.reconciliation_type) },
  { label: '处理状态', value: formatStatusLabel(item.value?.status) },
  { label: '差异值', value: item.value?.diff_value },
  { label: '字段', value: item.value?.field_name }
])
const supportingFields = computed(() => [
  { label: '维度键', value: item.value?.dimension_key },
  { label: '来源 A', value: formatSourceTypeLabel(item.value?.source_a) },
  { label: '来源 A 值', value: item.value?.source_a_value },
  { label: '来源 B', value: formatSourceTypeLabel(item.value?.source_b) },
  { label: '来源 B 值', value: item.value?.source_b_value },
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

onMounted(load)
</script>

<style scoped>
.reconciliation-detail__fields {
  display: grid;
  gap: var(--xt-space-3);
}
</style>
