<template>
  <div class="page-stack">
    <div class="page-header">
      <div>
        <h1>质量问题详情</h1>
        <p>查看问题来源、字段维度和处理记录，方便观察者或管理员继续跟进。</p>
      </div>
      <el-button @click="load">刷新</el-button>
    </div>

    <el-card class="panel" v-if="item">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="问题编号">{{ item.id }}</el-descriptions-item>
        <el-descriptions-item label="业务日期">{{ item.business_date }}</el-descriptions-item>
        <el-descriptions-item label="问题类型">
          {{ formatQualityIssueTypeLabel(item.issue_type) }}
        </el-descriptions-item>
        <el-descriptions-item label="问题级别">
          {{ formatStatusLabel(item.issue_level) }}
        </el-descriptions-item>
        <el-descriptions-item label="来源类型">{{ formatSourceTypeLabel(item.source_type) }}</el-descriptions-item>
        <el-descriptions-item label="维度键">{{ item.dimension_key || '-' }}</el-descriptions-item>
        <el-descriptions-item label="字段名">{{ item.field_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="处理状态">{{ formatStatusLabel(item.status) }}</el-descriptions-item>
        <el-descriptions-item label="问题描述" :span="2">
          {{ item.issue_desc }}
        </el-descriptions-item>
        <el-descriptions-item label="处理人">{{ item.resolved_by || '-' }}</el-descriptions-item>
        <el-descriptions-item label="处理时间">{{ item.resolved_at || '-' }}</el-descriptions-item>
        <el-descriptions-item label="处理说明" :span="2">{{ item.resolve_note || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'

import { fetchQualityIssues } from '../../api/quality'
import { formatQualityIssueTypeLabel, formatSourceTypeLabel, formatStatusLabel } from '../../utils/display'

const route = useRoute()
const item = ref(null)

async function load() {
  const rows = await fetchQualityIssues({ issue_id: route.params.id })
  item.value = rows && rows.length ? rows[0] : null
}

onMounted(load)
</script>
