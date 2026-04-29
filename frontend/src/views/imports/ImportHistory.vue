<template>
  <div class="page-stack">
    <div class="page-header">
      <div>
        <h1>导入历史</h1>
      </div>
      <el-button @click="load">刷新</el-button>
    </div>

    <el-card class="panel">
      <ReferenceDataTable :data="items" stripe>
        <el-table-column type="expand">
          <template #default="{ row }">
            <pre class="summary-json">{{ JSON.stringify(extractSummary(row), null, 2) }}</pre>
          </template>
        </el-table-column>
        <el-table-column label="批次号" width="160">
          <template #default="{ row }">
            {{ row.batch_no || `#${row.id}` }}
          </template>
        </el-table-column>
        <el-table-column prop="import_type" label="导入类型" width="140">
          <template #default="{ row }">
            {{ formatImportTypeLabel(row.import_type) }}
          </template>
        </el-table-column>
        <el-table-column label="文件名" min-width="180">
          <template #default="{ row }">
            {{ row.file_name || row.filename || '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="处理状态" width="120">
          <template #default="{ row }">
            <ReferenceStatusTag :status="statusTone(row.status)" :label="formatStatusLabel(row.status)" />
          </template>
        </el-table-column>
        <el-table-column label="总行数" width="100">
          <template #default="{ row }">
            {{ row.total_rows ?? row.row_count ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column label="成功" width="100">
          <template #default="{ row }">
            {{ row.success_rows ?? row.success_count ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column label="失败" width="100">
          <template #default="{ row }">
            {{ row.failed_rows ?? row.failed_count ?? '-' }}
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="时间" width="200" />
      </ReferenceDataTable>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'

import { fetchImportHistory } from '../../api/imports'
import ReferenceDataTable from '../../components/reference/ReferenceDataTable.vue'
import ReferenceStatusTag from '../../components/reference/ReferenceStatusTag.vue'
import { formatImportTypeLabel, formatStatusLabel } from '../../utils/display'

const items = ref([])

function extractSummary(row) {
  return {
    batch_no: row.batch_no,
    file_name: row.file_name || row.filename,
    total_rows: row.total_rows ?? row.row_count,
    success_rows: row.success_rows ?? row.success_count,
    failed_rows: row.failed_rows ?? row.failed_count,
    skipped_rows: row.skipped_rows,
    error_summary: row.error_summary || null
  }
}

async function load() {
  const data = await fetchImportHistory()
  items.value = Array.isArray(data) ? data : data?.items || []
}

function statusTone(status) {
  const value = String(status || '').toLowerCase()
  if (['success', 'done', 'completed'].includes(value)) return 'success'
  if (['pending', 'processing', 'running'].includes(value)) return 'warning'
  if (['failed', 'error'].includes(value)) return 'danger'
  return 'normal'
}

onMounted(load)
</script>
