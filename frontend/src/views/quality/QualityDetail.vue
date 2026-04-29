<template>
  <div class="page-stack">
    <div class="page-header">
      <div>
        <h1>质量问题详情</h1>
        <p>查看问题来源、字段维度和处理记录，方便观察者或管理员继续跟进。</p>
      </div>
      <el-button @click="load">刷新</el-button>
    </div>

    <div v-if="item" class="quality-detail__fields">
      <XtFieldGroup title="结论区" tier="primary" :items="primaryFields" />
      <XtFieldGroup title="来源区" tier="supporting" :items="supportingFields" />
      <XtFieldGroup title="审计区" tier="audit" :items="auditFields" collapsed />
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { fetchQualityIssues } from '../../api/quality'
import { XtFieldGroup } from '../../components/xt'
import { formatQualityIssueTypeLabel, formatSourceTypeLabel, formatStatusLabel } from '../../utils/display'

const route = useRoute()
const item = ref(null)
const primaryFields = computed(() => [
  { label: '业务日期', value: item.value?.business_date },
  { label: '问题类型', value: formatQualityIssueTypeLabel(item.value?.issue_type) },
  { label: '问题级别', value: formatStatusLabel(item.value?.issue_level) },
  { label: '处理状态', value: formatStatusLabel(item.value?.status) },
  { label: '字段', value: item.value?.field_name },
  { label: '问题描述', value: item.value?.issue_desc }
])
const supportingFields = computed(() => [
  { label: '来源类型', value: formatSourceTypeLabel(item.value?.source_type) },
  { label: '维度键', value: item.value?.dimension_key },
  { label: '处理说明', value: item.value?.resolve_note }
])
const auditFields = computed(() => [
  { label: '问题编号', value: item.value?.id },
  { label: '处理人', value: item.value?.resolved_by },
  { label: '处理时间', value: item.value?.resolved_at }
])

async function load() {
  const rows = await fetchQualityIssues({ issue_id: route.params.id })
  item.value = rows && rows.length ? rows[0] : null
}

onMounted(load)
</script>

<style scoped>
.quality-detail__fields {
  display: grid;
  gap: var(--xt-space-3);
}
</style>
