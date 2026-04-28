<template>
  <div class="page-stack">
    <div class="page-header">
      <div>
        <h1>导入历史</h1>
      </div>
      <el-button @click="load">刷新</el-button>
    </div>

    <el-card class="panel">
      <el-table :data="items" stripe>
        <el-table-column type="expand">
          <template #default="{ row }">
            <pre class="summary-json">{{ JSON.stringify(extractSummary(row), null, 2) }}</pre>
          </template>
        </el-table-column>
        <el-table-column prop="batch_no" label="批次号" width="220" />
        <el-table-column prop="import_type" label="导入类型" width="140">
          <template #default="{ row }">
            {{ formatImportTypeLabel(row.import_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="file_name" label="文件名" />
        <el-table-column prop="status" label="处理状态" width="120">
          <template #default="{ row }">
            {{ formatStatusLabel(row.status) }}
          </template>
        </el-table-column>
        <el-table-column prop="total_rows" label="总行数" width="100" />
        <el-table-column prop="success_rows" label="成功" width="100" />
        <el-table-column prop="failed_rows" label="失败" width="100" />
        <el-table-column prop="created_at" label="时间" width="200" />
      </el-table>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'

import { fetchImportHistory } from '../../api/imports'
import { formatImportTypeLabel, formatStatusLabel } from '../../utils/display'

const items = ref([])

function extractSummary(row) {
  return {
    batch_no: row.batch_no,
    file_name: row.file_name,
    total_rows: row.total_rows,
    success_rows: row.success_rows,
    failed_rows: row.failed_rows,
    skipped_rows: row.skipped_rows,
    error_summary: row.error_summary || null
  }
}

async function load() {
  const data = await fetchImportHistory()
  items.value = Array.isArray(data) ? data : []
}

onMounted(load)
</script>
