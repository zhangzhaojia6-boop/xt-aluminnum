<template>
  <section class="contracts-center page-stack">
    <header class="page-header">
      <h1>合同与订单中心</h1>
      <XtCommandBar v-model="dateRange" :exportable="true" @export="onExport">
        <template #filters>
          <el-select v-model="statusFilter" placeholder="状态" clearable style="width: 120px">
            <el-option label="执行中" value="active" />
            <el-option label="已完成" value="completed" />
            <el-option label="延期" value="overdue" />
          </el-select>
        </template>
      </XtCommandBar>
    </header>

    <XtKpiRibbon>
      <XtMetricCard label="活跃合同" :value="kpi.active_count" />
      <XtMetricCard label="履约率" :value="kpi.fulfillment_pct" unit="%" tone="success" />
      <XtMetricCard label="延期预警" :value="kpi.overdue_count" tone="danger" />
      <XtMetricCard label="本月交付量" :value="kpi.mtd_delivery_tons" unit="吨" />
    </XtKpiRibbon>

    <XtSectionCard title="履约进度">
      <XtErrorPanel v-if="error" :message="error" @retry="load" />
      <XtSkeleton v-else-if="loading" :rows="4" />
      <XtBarChart
        v-else
        :series="progressSeries"
        :x-labels="progressLabels"
        y-unit="吨"
        height="260px"
        :horizontal="true"
        :stacked="true"
      />
    </XtSectionCard>

    <XtSectionCard title="合同明细">
      <XtDataTable
        :columns="columns"
        :data="tableData"
        :striped="true"
        data-source="contracts"
      />
      <XtEmpty v-if="!loading && !tableData.length" text="暂无合同数据" />
    </XtSectionCard>
  </section>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../../api/index'
import XtCommandBar from '../../components/xt/XtCommandBar.vue'
import XtKpiRibbon from '../../components/xt/XtKpiRibbon.vue'
import XtMetricCard from '../../components/xt/XtMetricCard.vue'
import XtSectionCard from '../../components/xt/XtSectionCard.vue'
import XtBarChart from '../../components/xt/XtBarChart.vue'
import XtDataTable from '../../components/xt/XtDataTable.vue'
import XtErrorPanel from '../../components/xt/XtErrorPanel.vue'
import XtSkeleton from '../../components/xt/XtSkeleton.vue'
import XtEmpty from '../../components/xt/XtEmpty.vue'

const dateRange = ref([])
const statusFilter = ref('')
const loading = ref(false)
const error = ref('')
const kpi = ref({})
const progressSeries = ref([])
const progressLabels = ref([])
const tableData = ref([])

const columns = [
  { key: 'contract_no', label: '合同号', width: '140px' },
  { key: 'customer_name', label: '客户', width: '140px' },
  { key: 'total_quantity', label: '合同量(吨)', width: '100px' },
  { key: 'delivered_quantity', label: '已交付(吨)', width: '100px' },
  { key: 'progress_pct', label: '进度', width: '80px' },
  { key: 'deadline', label: '交期', width: '110px' },
  { key: 'status', label: '状态', width: '80px' }
]

async function load() {
  loading.value = true
  error.value = ''
  try {
    const params = {
      date_from: dateRange.value?.[0],
      date_to: dateRange.value?.[1],
      status: statusFilter.value || undefined
    }
    const { data } = await api.get('/contracts/summary', { params })
    kpi.value = data.kpi || {}
    progressSeries.value = data.progress?.series || []
    progressLabels.value = data.progress?.labels || []
    tableData.value = data.contracts || []
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
  window.open(`/api/v1/contracts/export?${params}`, '_blank')
}

onMounted(load)
</script>

<style scoped>
.contracts-center {
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
