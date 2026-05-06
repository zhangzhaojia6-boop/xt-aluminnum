<template>
  <div class="page-stack">
    <div class="page-header">
      <div>
        <h1>导入历史</h1>
      </div>
      <el-button @click="load">刷新</el-button>
    </div>

    <section v-if="mappingPreview" class="mapping-gate">
      <header class="mapping-gate__head">
        <div>
          <span class="mapping-gate__eyebrow">每日产量</span>
          <h2>{{ mappingPreview.batch_no || '映射门禁' }}</h2>
        </div>
        <ReferenceStatusTag :status="mappingGateTone" :label="mappingGateLabel" />
      </header>

      <div class="mapping-gate__metrics">
        <div v-for="item in mappingMetrics" :key="item.key" class="mapping-gate__metric" :class="`is-${item.key}`">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
        </div>
      </div>

      <div class="mapping-gate__strip" aria-label="每日产量映射分布">
        <span class="is-ready" :style="{ width: segmentWidth(mappingPreview.ready_rows) }"></span>
        <span class="is-equipment" :style="{ width: segmentWidth(mappingPreview.needs_equipment_mapping_rows) }"></span>
        <span class="is-unresolved" :style="{ width: segmentWidth(mappingPreview.unresolved_rows) }"></span>
      </div>

      <div v-if="unresolvedMappingLabels.length" class="mapping-gate__labels">
        <span v-for="item in unresolvedMappingLabels" :key="item.label">
          <strong>{{ item.label }}</strong>
          <small v-if="item.candidateSummary">{{ item.candidateSummary }}</small>
        </span>
      </div>
    </section>

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
import { computed, onMounted, ref } from 'vue'

import { fetchDailyProductionMappingPreview, fetchImportHistory } from '../../api/imports'
import ReferenceDataTable from '../../components/reference/ReferenceDataTable.vue'
import ReferenceStatusTag from '../../components/reference/ReferenceStatusTag.vue'
import { formatImportTypeLabel, formatStatusLabel } from '../../utils/display'

const items = ref([])
const mappingPreview = ref(null)

const latestDailyProductionBatch = computed(() =>
  items.value.find((item) => item.import_type === 'daily_production_report')
)

const mappingGateTone = computed(() => {
  if (!mappingPreview.value) return 'normal'
  if (Number(mappingPreview.value.unresolved_rows || 0) > 0) return 'danger'
  if (Number(mappingPreview.value.needs_equipment_mapping_rows || 0) > 0) return 'warning'
  return 'success'
})

const mappingGateLabel = computed(() => {
  if (!mappingPreview.value) return '未导入'
  if (Number(mappingPreview.value.unresolved_rows || 0) > 0) return '需补映射'
  if (Number(mappingPreview.value.needs_equipment_mapping_rows || 0) > 0) return '需定机列'
  return '可进入复核'
})

const mappingMetrics = computed(() => {
  const preview = mappingPreview.value || {}
  return [
    { key: 'ready', label: '已匹配', value: Number(preview.ready_rows || 0) },
    { key: 'equipment', label: '待机列', value: Number(preview.needs_equipment_mapping_rows || 0) },
    { key: 'unresolved', label: '未解析', value: Number(preview.unresolved_rows || 0) },
    { key: 'total', label: '总行', value: Number(preview.total_rows || 0) }
  ]
})

const unresolvedMappingLabels = computed(() => {
  const rows = mappingPreview.value?.rows || []
  return rows
    .filter((row) => row.status === 'unresolved_workshop')
    .map((row) => ({
      label: `${row.workshop_label || '-'} / ${row.project_label || '-'}`,
      candidateSummary: candidateSummary(row)
    }))
    .slice(0, 12)
})

function compactCandidates(items) {
  if (!Array.isArray(items)) return ''
  return items
    .map((item) => item?.code || item?.name)
    .filter(Boolean)
    .slice(0, 3)
    .join(' / ')
}

function candidateSummary(row) {
  const workshops = compactCandidates(row.candidate_workshops)
  const equipment = compactCandidates(row.candidate_equipment)
  return [
    workshops ? `车间 ${workshops}` : '',
    equipment ? `机列 ${equipment}` : ''
  ].filter(Boolean).join(' · ')
}

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
  await loadMappingPreview()
}

async function loadMappingPreview() {
  const batch = latestDailyProductionBatch.value
  if (!batch) {
    mappingPreview.value = null
    return
  }
  try {
    mappingPreview.value = await fetchDailyProductionMappingPreview(batch.id)
  } catch (_error) {
    mappingPreview.value = null
  }
}

function segmentWidth(count) {
  const total = Number(mappingPreview.value?.total_rows || 0)
  if (!total) return '0%'
  return `${Math.max(0, Math.min(100, (Number(count || 0) / total) * 100))}%`
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

<style scoped>
.mapping-gate {
  border: 1px solid #d7dde5;
  border-radius: 8px;
  background: #f8fafc;
  padding: 16px;
}

.mapping-gate__head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.mapping-gate__eyebrow {
  display: block;
  color: #64748b;
  font-size: 12px;
  line-height: 1;
}

.mapping-gate h2 {
  margin: 4px 0 0;
  color: #172033;
  font-size: 18px;
  line-height: 1.25;
}

.mapping-gate__metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 8px;
  margin-top: 14px;
}

.mapping-gate__metric {
  border-left: 3px solid #94a3b8;
  background: #fff;
  padding: 10px 12px;
}

.mapping-gate__metric span {
  display: block;
  color: #64748b;
  font-size: 12px;
}

.mapping-gate__metric strong {
  display: block;
  margin-top: 4px;
  color: #172033;
  font-size: 20px;
  line-height: 1;
}

.mapping-gate__metric.is-ready {
  border-color: #16a34a;
}

.mapping-gate__metric.is-equipment {
  border-color: #d97706;
}

.mapping-gate__metric.is-unresolved {
  border-color: #dc2626;
}

.mapping-gate__metric.is-total {
  border-color: #2563eb;
}

.mapping-gate__strip {
  display: flex;
  height: 8px;
  margin-top: 14px;
  overflow: hidden;
  border-radius: 999px;
  background: #e2e8f0;
}

.mapping-gate__strip span {
  display: block;
}

.mapping-gate__strip .is-ready {
  background: #16a34a;
}

.mapping-gate__strip .is-equipment {
  background: #d97706;
}

.mapping-gate__strip .is-unresolved {
  background: #dc2626;
}

.mapping-gate__labels {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 12px;
}

.mapping-gate__labels span {
  display: inline-flex;
  flex-direction: column;
  gap: 4px;
  border: 1px solid #fecaca;
  border-radius: 8px;
  background: #fff1f2;
  color: #9f1239;
  font-size: 12px;
  line-height: 1.2;
  padding: 7px 9px;
}

.mapping-gate__labels strong {
  color: #881337;
  font-size: 12px;
  font-weight: 700;
  line-height: 1.15;
}

.mapping-gate__labels small {
  color: #475569;
  font-size: 11px;
  line-height: 1.2;
}

@media (max-width: 640px) {
  .mapping-gate__head {
    align-items: stretch;
    flex-direction: column;
  }

  .mapping-gate__metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
