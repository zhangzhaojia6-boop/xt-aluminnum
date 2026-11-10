<template>
  <section class="page-stack inventory-command" data-testid="inventory-center-page">
    <header class="inventory-command__hero">
      <div class="inventory-command__hero-copy">
        <span class="inventory-command__eyebrow">库存管控</span>
        <h1>库存出入中心</h1>
      </div>
      <div class="inventory-command__actions" data-testid="inventory-center-filters">
        <el-date-picker
          v-model="dateRange"
          class="inventory-command__date"
          type="daterange"
          value-format="YYYY-MM-DD"
          range-separator="至"
          start-placeholder="开始日期"
          end-placeholder="结束日期"
        />
        <el-select v-model="warehouseFilter" placeholder="仓库" clearable class="inventory-command__select">
          <el-option v-for="w in warehouses" :key="w.id" :label="w.name" :value="w.id" />
        </el-select>
        <el-button class="inventory-command__button" @click="load">查询</el-button>
        <el-button class="inventory-command__button inventory-command__button--ghost" @click="onExport">导出</el-button>
      </div>
    </header>

    <section class="inventory-command__stats" data-testid="inventory-center-stats">
      <article
        v-for="item in inventoryStats"
        :key="item.key"
        class="inventory-command__stat"
        :class="`inventory-command__stat--${item.accent}`"
      >
        <div class="inventory-command__stat-top">
          <span class="inventory-command__led"></span>
          <span>{{ item.label }}</span>
        </div>
        <strong>{{ item.value }}</strong>
        <small>{{ item.unit }}</small>
        <em v-if="item.extra">{{ item.extra }}</em>
      </article>
    </section>

    <section class="inventory-command__panel inventory-command__panel--chart">
      <div class="inventory-command__panel-head">
        <div>
          <span class="inventory-command__eyebrow">库存流转</span>
          <h2>出入库趋势</h2>
        </div>
        <span class="inventory-command__panel-chip">{{ trendLabels.length }} 个节点</span>
      </div>
      <XtErrorPanel v-if="error" :message="error" @retry="load" />
      <XtSkeleton v-else-if="loading" :rows="4" />
      <XtLineChart
        v-else
        :series="trendSeries"
        :x-labels="trendLabels"
        y-unit="吨"
        height="260px"
      />
    </section>

    <section class="inventory-command__panel">
      <div class="inventory-command__panel-head">
        <div>
          <span class="inventory-command__eyebrow">出入库流水</span>
          <h2>出入库明细</h2>
        </div>
        <span class="inventory-command__panel-chip">{{ tableData.length }} 条</span>
      </div>

      <div class="inventory-command__table" data-testid="inventory-center-table">
        <XtDataTable
          :columns="columns"
          :data="tableData"
          :striped="true"
          data-source="inventory_transactions"
        >
          <template #cell-direction="{ value }">
            <span class="inventory-command__direction" :data-direction="directionTone(value)">
              {{ directionLabel(value) }}
            </span>
          </template>
          <template #cell-quantity="{ value }">
            {{ formatQuantity(value) }}
          </template>
        </XtDataTable>
      </div>

      <div class="inventory-command__mobile-list" data-testid="inventory-center-mobile-list">
        <article v-for="(row, index) in tableData" :key="row.id || `${row.transaction_date}-${row.material_name}-${index}`">
          <div class="inventory-command__mobile-title">
            <span>{{ row.material_name || '-' }}</span>
            <span class="inventory-command__direction" :data-direction="directionTone(row.direction)">
              {{ directionLabel(row.direction) }}
            </span>
          </div>
          <div class="inventory-command__mobile-grid">
            <span>日期</span><strong>{{ row.transaction_date || '-' }}</strong>
            <span>仓库</span><strong>{{ row.warehouse_name || '-' }}</strong>
            <span>数量</span><strong>{{ formatQuantity(row.quantity) }}</strong>
            <span>操作人</span><strong>{{ row.operator || '-' }}</strong>
          </div>
        </article>
      </div>

      <XtEmpty v-if="!loading && !tableData.length" text="当前筛选条件下暂无出入库记录" />
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../../api/index'
import XtLineChart from '../../components/xt/XtLineChart.vue'
import XtDataTable from '../../components/xt/XtDataTable.vue'
import XtErrorPanel from '../../components/xt/XtErrorPanel.vue'
import XtSkeleton from '../../components/xt/XtSkeleton.vue'
import XtEmpty from '../../components/xt/XtEmpty.vue'
import { downloadBlob } from '../../utils/downloadBlob.js'

const dateRange = ref([])
const warehouseFilter = ref('')
const warehouses = ref([])
const loading = ref(false)
const error = ref('')
const kpi = ref({})
const trendSeries = ref([])
const trendLabels = ref([])
const tableData = ref([])

const columns = [
  { key: 'transaction_date', label: '日期', width: '110px' },
  { key: 'warehouse_name', label: '仓库', width: '120px' },
  { key: 'material_name', label: '物料', width: '140px' },
  { key: 'direction', label: '方向', width: '90px' },
  { key: 'quantity', label: '数量(吨)', width: '108px' },
  { key: 'operator', label: '操作人', width: '100px' }
]

const inventoryStats = computed(() => [
  {
    key: 'stock',
    label: '当前库存',
    value: formatNumber(kpi.value.current_stock),
    unit: '吨',
    extra: `变化 ${formatSigned(kpi.value.stock_change)} 吨`,
    accent: 'cyan'
  },
  { key: 'inbound', label: '今日入库', value: formatNumber(kpi.value.inbound_today), unit: '吨', accent: 'blue' },
  { key: 'outbound', label: '今日出库', value: formatNumber(kpi.value.outbound_today), unit: '吨', accent: 'amber' },
  { key: 'anomaly', label: '异动告警', value: formatNumber(kpi.value.anomaly_count), unit: '项', accent: 'danger' }
])

function toNumber(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number : 0
}

function formatNumber(value) {
  if (value === null || value === undefined || value === '') return '-'
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(toNumber(value))
}

function formatSigned(value) {
  if (value === null || value === undefined || value === '') return '-'
  const number = toNumber(value)
  return `${number > 0 ? '+' : ''}${formatNumber(number)}`
}

function formatQuantity(value) {
  if (value === null || value === undefined || value === '') return '-'
  return `${formatNumber(value)} 吨`
}

function directionTone(direction) {
  const value = String(direction || '').toLowerCase()
  if (['in', 'inbound', '入库'].includes(value)) return 'inbound'
  if (['out', 'outbound', '出库'].includes(value)) return 'outbound'
  return 'normal'
}

function directionLabel(direction) {
  const value = String(direction || '').toLowerCase()
  const map = {
    in: '入库',
    inbound: '入库',
    out: '出库',
    outbound: '出库'
  }
  return map[value] || direction || '-'
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const params = {
      date_from: dateRange.value?.[0],
      date_to: dateRange.value?.[1],
      warehouse_id: warehouseFilter.value || undefined
    }
    const { data } = await api.get('/inventory/summary', { params })
    kpi.value = data.kpi || {}
    trendSeries.value = data.trend?.series || []
    trendLabels.value = data.trend?.labels || []
    tableData.value = data.transactions || []
    warehouses.value = data.warehouses || warehouses.value
  } catch (e) {
    error.value = e?.response?.data?.detail || '加载失败'
  } finally {
    loading.value = false
  }
}

async function onExport() {
  try {
    const params = {
      date_from: dateRange.value?.[0],
      date_to: dateRange.value?.[1],
      warehouse_id: warehouseFilter.value || undefined
    }
    const { data } = await api.get('/inventory/export', { params, responseType: 'blob' })
    downloadBlob(data, 'inventory_summary.csv')
  } catch (e) {
    error.value = e?.response?.data?.detail || '导出失败'
  }
}

onMounted(load)
</script>

<style scoped>
.inventory-command {
  --inventory-cyan: var(--xt-primary);
  --inventory-amber: var(--xt-warning);
  --inventory-blue: var(--xt-primary-hover);
  --inventory-danger: var(--xt-danger);
  --inventory-bg: var(--xt-bg-page);
  --inventory-panel: var(--xt-bg-panel);
  --inventory-line: color-mix(in srgb, var(--xt-primary) 18%, transparent);
  --inventory-muted: var(--xt-text-secondary);
  color: var(--xt-text);
}

.inventory-command::before {
  position: fixed;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  content: '';
  background: transparent;
  background-size: auto, auto, 32px 32px, 32px 32px, auto;
}

.inventory-command__hero,
.inventory-command__panel,
.inventory-command__stat,
.inventory-command__mobile-list article {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--xt-border);
  background: transparent;


}

.inventory-command__hero::after,
.inventory-command__panel::after,
.inventory-command__stat::after {
  position: absolute;
  inset: 0;
  pointer-events: none;
  content: '';
  background: transparent;
  transform: translateX(-120%);

}

.inventory-command__hero {
  display: grid;
  grid-template-columns: minmax(420px, 1fr) minmax(420px, auto);
  align-items: center;
  gap: 20px;
  min-height: 156px;
  padding: 28px;
  border-radius: 4px;
}

.inventory-command__hero-copy,
.inventory-command__actions,
.inventory-command__panel-head,
.inventory-command__table,
.inventory-command__mobile-list {
  position: relative;
  z-index: 1;
}

.inventory-command__eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--xt-primary);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.16em;
}

.inventory-command__eyebrow::before {
  width: 8px;
  height: 8px;
  content: '';
  border-radius: 999px;
  background: transparent;

}

.inventory-command h1,
.inventory-command h2 {
  margin: 0;
  color: var(--xt-text);

  letter-spacing: -0.03em;
}

.inventory-command h1 {
  margin-top: 12px;
  font-size: clamp(34px, 5vw, 58px);
  line-height: 1;
  white-space: nowrap;

}

.inventory-command h2 {
  margin-top: 8px;
  font-size: 24px;
}

.inventory-command__actions {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 12px;
  padding: 12px;
  border: 1px solid var(--xt-border);
  border-radius: 4px;
  background: transparent;
}

.inventory-command__date {
  width: 260px;
}

.inventory-command__select {
  width: 150px;
}

.inventory-command__actions :deep(.el-input__wrapper),
.inventory-command__actions :deep(.el-select__wrapper) {
  min-height: 38px;
  border-radius: 4px;
  background: transparent;

}

.inventory-command__actions :deep(.el-input__inner),
.inventory-command__actions :deep(.el-range-input),
.inventory-command__actions :deep(.el-range-separator),
.inventory-command__actions :deep(.el-select__placeholder),
.inventory-command__actions :deep(.el-select__selected-item) {
  color: var(--xt-text);
}

.inventory-command__button {
  min-width: 92px;
  border: 1px solid var(--xt-border);
  border-radius: 4px;
  background: transparent;
  color: var(--xt-text);
  font-weight: 600;

}

.inventory-command__button--ghost {
  background: transparent;
}

.inventory-command__stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.inventory-command__stat {
  min-height: 136px;
  padding: 18px;
  border-radius: 4px;
}

.inventory-command__stat-top {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.08em;
}

.inventory-command__led {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: transparent;


}

.inventory-command__stat strong {
  position: relative;
  z-index: 1;
  display: block;
  margin-top: 18px;
  color: var(--xt-text);

  font-size: clamp(30px, 4vw, 46px);
  line-height: 0.95;

}

.inventory-command__stat small,
.inventory-command__stat em {
  position: relative;
  z-index: 1;
  display: block;
  margin-top: 8px;
  color: var(--xt-text-secondary);
  font-style: normal;
  font-weight: 600;
}

.inventory-command__stat--amber .inventory-command__led {
  background: transparent;

}

.inventory-command__stat--blue .inventory-command__led {
  background: transparent;

}

.inventory-command__stat--danger .inventory-command__led {
  background: transparent;

}

.inventory-command__panel {
  padding: 22px;
  border-radius: 4px;
}

.inventory-command__panel--chart {
  min-height: 360px;
}

.inventory-command__panel-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 18px;
}

.inventory-command__panel-chip {
  border: 1px solid var(--xt-border);
  border-radius: 999px;
  padding: 6px 10px;
  color: var(--xt-text-secondary);
  background: transparent;
  font-size: 12px;
  font-weight: 600;
}

.inventory-command__table {
  overflow: hidden;
  border: 1px solid var(--xt-border);
  border-radius: 4px;
}

.inventory-command__table :deep(.xt-data-table),
.inventory-command__table :deep(.xt-data-table__table),
.inventory-command__table :deep(.xt-data-table__row) {
  border-color: var(--xt-border);
  background: transparent;
}

.inventory-command__table :deep(.xt-data-table__th) {
  color: var(--xt-text);
  border-color: var(--xt-border);
}

.inventory-command__table :deep(.xt-data-table__td) {
  color: var(--xt-text);
  border-color: var(--xt-border);
}

.inventory-command__table :deep(.xt-data-table--striped .xt-data-table__row:nth-child(even)) {
  background: transparent;
}

.inventory-command__table :deep(.xt-data-table__row:hover) {
  background: transparent;
}

.inventory-command__direction {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 52px;
  border-radius: 999px;
  padding: 4px 9px;
  background: transparent;
  color: var(--xt-text);
  font-size: 12px;
  font-weight: 600;

}

.inventory-command__direction[data-direction='inbound'] {
  background: transparent;
  color: var(--xt-text);
}

.inventory-command__direction[data-direction='outbound'] {
  background: transparent;
  color: var(--xt-text);

}

.inventory-command__mobile-list {
  display: none;
}

.inventory-command__mobile-list article {
  border-radius: 4px;
  padding: 16px;
}

.inventory-command__mobile-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: var(--xt-text);

  font-size: 18px;
  font-weight: 600;
}

.inventory-command__mobile-grid {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 8px 14px;
  margin-top: 14px;
}

.inventory-command__mobile-grid span {
  color: var(--xt-text-secondary);
}

.inventory-command__mobile-grid strong {
  color: var(--xt-text);
  text-align: right;
}

@keyframes inventorySweep {
  0% { transform: translateX(-120%); opacity: 0; }
  42% { opacity: 1; }
  100% { transform: translateX(120%); opacity: 0; }
}

@keyframes inventoryPulse {
  0%, 100% { transform: scale(1); opacity: 0.72; }
  50% { transform: scale(1.22); opacity: 1; }
}

@media (max-width: 1180px) {
  .inventory-command__hero {
    grid-template-columns: 1fr;
  }

  .inventory-command__actions {
    justify-content: flex-start;
  }

  .inventory-command__stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .inventory-command__hero,
  .inventory-command__panel-head {
    align-items: stretch;
    flex-direction: column;
  }

  .inventory-command h1 {
    white-space: normal;
  }

  .inventory-command__actions {
    display: grid;
    grid-template-columns: 1fr;
  }

  .inventory-command__date,
  .inventory-command__select,
  .inventory-command__button,
  .inventory-command__actions :deep(.el-date-editor) {
    width: 100%;
  }

  .inventory-command__stats {
    grid-template-columns: 1fr;
  }

  .inventory-command__panel {
    padding: 16px;
  }

  .inventory-command__table {
    display: none;
  }

  .inventory-command__mobile-list {
    display: grid;
    gap: 12px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .inventory-command__hero::after,
  .inventory-command__panel::after,
  .inventory-command__stat::after,
  .inventory-command__led {
    animation: none;
  }
}
</style>
