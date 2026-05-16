<template>
  <section class="inventory-center page-stack">
    <header class="page-header">
      <h1>库存出入中心</h1>
      <XtCommandBar v-model="dateRange" :exportable="true" @export="onExport">
        <template #filters>
          <el-select v-model="warehouseFilter" placeholder="仓库" clearable style="width: 140px">
            <el-option v-for="w in warehouses" :key="w.id" :label="w.name" :value="w.id" />
          </el-select>
        </template>
      </XtCommandBar>
    </header>

    <XtKpiRibbon>
      <XtMetricCard label="当前库存" :value="kpi.current_stock" unit="吨" :change="kpi.stock_change" />
      <XtMetricCard label="今日入库" :value="kpi.inbound_today" unit="吨" tone="success" />
      <XtMetricCard label="今日出库" :value="kpi.outbound_today" unit="吨" tone="warning" />
      <XtMetricCard label="异动告警" :value="kpi.anomaly_count" tone="danger" />
    </XtKpiRibbon>

    <XtSectionCard title="出入库趋势">
      <XtErrorPanel v-if="error" :message="error" @retry="load" />
      <XtSkeleton v-else-if="loading" :rows="4" />
      <XtLineChart
        v-else
        :series="trendSeries"
        :x-labels="trendLabels"
        y-unit="吨"
        height="260px"
      />
    </XtSectionCard>

    <XtSectionCard title="出入库明细">
      <XtDataTable
        :columns="columns"
        :data="tableData"
        :striped="true"
        data-source="inventory_transactions"
      />
      <XtEmpty v-if="!loading && !tableData.length" text="当前筛选条件下暂无出入库记录" />
    </XtSectionCard>
  </section>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { api } from '../../api/index'
import XtCommandBar from '../../components/xt/XtCommandBar.vue'
import XtKpiRibbon from '../../components/xt/XtKpiRibbon.vue'
import XtMetricCard from '../../components/xt/XtMetricCard.vue'
import XtSectionCard from '../../components/xt/XtSectionCard.vue'
import XtLineChart from '../../components/xt/XtLineChart.vue'
import XtDataTable from '../../components/xt/XtDataTable.vue'
import XtErrorPanel from '../../components/xt/XtErrorPanel.vue'
import XtSkeleton from '../../components/xt/XtSkeleton.vue'
import XtEmpty from '../../components/xt/XtEmpty.vue'

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
  { key: 'direction', label: '方向', width: '80px' },
  { key: 'quantity', label: '数量(吨)', width: '100px' },
  { key: 'operator', label: '操作人', width: '100px' }
]

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

function onExport() {
  const params = new URLSearchParams({
    date_from: dateRange.value?.[0] || '',
    date_to: dateRange.value?.[1] || ''
  })
  window.open(`/api/v1/inventory/export?${params}`, '_blank')
}

onMounted(load)
</script>

<style scoped>
.inventory-center {
  display: flex;
  flex-direction: column;
  gap: var(--xt-space-6);
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-4);
}

.page-header h1 {
  font-size: var(--xt-text-xl);
  font-weight: 700;
  margin: 0;
}
</style>
