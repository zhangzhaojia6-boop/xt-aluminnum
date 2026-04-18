<template>
  <div class="page-stack">
    <div class="page-header">
      <div>
        <h1>差异详情</h1>
        <p>查看两个来源之间的差异内容、处理过程和最终说明。</p>
      </div>
      <el-button @click="load">刷新</el-button>
    </div>

    <el-card class="panel" v-if="item">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="差异编号">{{ item.id }}</el-descriptions-item>
        <el-descriptions-item label="业务日期">{{ item.business_date }}</el-descriptions-item>
        <el-descriptions-item label="差异类型">
          {{ formatReconciliationTypeLabel(item.reconciliation_type) }}
        </el-descriptions-item>
        <el-descriptions-item label="维度键">{{ item.dimension_key || '-' }}</el-descriptions-item>
        <el-descriptions-item label="字段名">{{ item.field_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="处理状态">{{ formatStatusLabel(item.status) }}</el-descriptions-item>
        <el-descriptions-item label="来源 A">{{ formatSourceTypeLabel(item.source_a) }}</el-descriptions-item>
        <el-descriptions-item label="来源 B">{{ formatSourceTypeLabel(item.source_b) }}</el-descriptions-item>
        <el-descriptions-item label="来源 A 值">{{ item.source_a_value ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="来源 B 值">{{ item.source_b_value ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="差异值">{{ item.diff_value ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="处理人">{{ item.resolved_by || '-' }}</el-descriptions-item>
        <el-descriptions-item label="处理时间">{{ item.resolved_at || '-' }}</el-descriptions-item>
        <el-descriptions-item label="处理说明">{{ item.resolve_note || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { fetchReconciliationItems } from '../../api/reconciliation'
import { formatReconciliationTypeLabel, formatSourceTypeLabel, formatStatusLabel } from '../../utils/display'

const route = useRoute()
const item = ref(null)

async function load() {
  const data = await fetchReconciliationItems({ item_id: route.params.id })
  item.value = data && data.length ? data[0] : null
}

onMounted(load)
</script>
