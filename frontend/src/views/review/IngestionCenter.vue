<template>
  <ReferencePageFrame
    module-number="06"
    title="数据接入与字段映射中心"
    :tags="['数据源状态', '字段映射', '历史记录']"
    data-testid="review-ingestion-center-v2"
  >
    <template #actions>
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
    </template>

    <section class="stat-grid" v-loading="loading">
      <article class="stat-card">
        <div class="stat-label">导入批次</div>
        <div class="stat-value">{{ totalBatches }}</div>
      </article>
      <article class="stat-card">
        <div class="stat-label">总成功率</div>
        <div class="stat-value">{{ successRate }}%</div>
      </article>
      <article class="stat-card">
        <div class="stat-label">总错误率</div>
        <div class="stat-value">{{ errorRate }}%</div>
      </article>
      <article class="stat-card">
        <div class="stat-label">最近批次</div>
        <div class="stat-value">{{ latestBatchNo }}</div>
      </article>
    </section>

    <section class="ingestion-center__main">
      <el-card class="panel">
        <template #header>数据源状态卡</template>
        <div class="ingestion-source-grid">
          <article v-for="item in sourceCards" :key="item.key" class="ingestion-source-card">
            <span>{{ item.label }}</span>
            <strong>{{ item.status }}</strong>
          </article>
        </div>
      </el-card>

      <el-card class="panel">
        <template #header>字段映射表（核心口径）</template>
        <el-table :data="mappingRows" stripe size="small">
          <el-table-column prop="sourceField" label="来源字段" min-width="170" />
          <el-table-column prop="targetField" label="目标字段" min-width="170" />
          <el-table-column prop="owner" label="责任角色" min-width="120" />
          <el-table-column prop="status" label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="row.status === '已映射' ? 'success' : 'warning'" effect="light">
                {{ row.status }}
              </el-tag>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

    </section>

    <el-card class="panel" v-loading="loading">
      <template #header>历史批次</template>
      <el-table :data="historyRows" stripe size="small">
        <el-table-column prop="batch_no" label="批次号" min-width="220" />
        <el-table-column prop="import_type" label="导入类型" width="140" />
        <el-table-column prop="file_name" label="文件名" min-width="220" />
        <el-table-column prop="status" label="状态" width="110" />
        <el-table-column prop="total_rows" label="总行数" width="90" align="right" />
        <el-table-column prop="success_rows" label="成功" width="90" align="right" />
        <el-table-column prop="failed_rows" label="失败" width="90" align="right" />
        <el-table-column prop="created_at" label="时间" min-width="170" />
      </el-table>
    </el-card>
  </ReferencePageFrame>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

import ReferencePageFrame from '../../components/reference/ReferencePageFrame.vue'
import { fetchImportHistory } from '../../api/imports'

const loading = ref(false)
const historyRows = ref([])

const mappingRows = [
  { sourceField: 'tracking_card_no', targetField: 'work_order.tracking_card_no', owner: '主操', status: '已映射' },
  { sourceField: 'output_weight', targetField: 'shift_production_data.output_weight', owner: '主操', status: '已映射' },
  { sourceField: 'shipment_weight', targetField: 'inventory_lane.shipment_weight', owner: '成品库', status: '已映射' },
  { sourceField: 'electricity_usage', targetField: 'energy_lane.electricity_value', owner: '水电气', status: '已映射' },
  { sourceField: 'contract_weight', targetField: 'contract_projection.remaining_weight', owner: '计划科', status: '已映射' }
]

const sourceCards = computed(() => [
  { key: 'mobile', label: '移动直录', status: '在线' },
  { key: 'imports', label: '文件导入', status: '已停用' },
  { key: 'mapping', label: '字段映射', status: '在线' },
  { key: 'quality', label: '质量校验', status: '在线' }
])

const totalBatches = computed(() => historyRows.value.length)
const latestBatchNo = computed(() => historyRows.value[0]?.batch_no || '--')

const successRate = computed(() => {
  const totals = historyRows.value.reduce((acc, row) => {
    acc.total += Number(row.total_rows || 0)
    acc.success += Number(row.success_rows || 0)
    return acc
  }, { total: 0, success: 0 })
  if (!totals.total) return '0.00'
  return ((totals.success / totals.total) * 100).toFixed(2)
})

const errorRate = computed(() => {
  const totals = historyRows.value.reduce((acc, row) => {
    acc.total += Number(row.total_rows || 0)
    acc.failed += Number(row.failed_rows || 0)
    return acc
  }, { total: 0, failed: 0 })
  if (!totals.total) return '0.00'
  return ((totals.failed / totals.total) * 100).toFixed(2)
})

async function load() {
  loading.value = true
  try {
    const rows = await fetchImportHistory()
    historyRows.value = Array.isArray(rows) ? rows : []
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.ingestion-center__header {
  display: flex;
  justify-content: space-between;
  align-items: start;
  gap: 12px;
}

.ingestion-center__header h1 {
  margin: 0;
}

.ingestion-center__header p {
  margin: 6px 0 0;
  color: var(--app-muted);
}

.ingestion-center__main {
  display: grid;
  gap: 12px;
}

.ingestion-source-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
}

.ingestion-source-card {
  display: grid;
  gap: 6px;
  padding: 12px;
  border-radius: 14px;
  border: 1px solid var(--app-border);
  background: var(--xt-gray-50);
}

.ingestion-source-card span {
  font-size: 12px;
  color: var(--app-muted);
}

.ingestion-source-card strong {
  font-size: 18px;
}

</style>
