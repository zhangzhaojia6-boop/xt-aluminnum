<template>
  <section class="cost-center page-stack">
    <header class="page-header">
      <h1>成本与效益中心</h1>
      <XtCommandBar v-model="dateRange" :exportable="true" @export="onExport">
        <template #filters>
          <el-select v-model="workshopFilter" placeholder="车间" clearable style="width: 140px">
            <el-option v-for="w in workshops" :key="w.id" :label="w.name" :value="w.id" />
          </el-select>
        </template>
      </XtCommandBar>
    </header>

    <XtKpiRibbon>
      <XtMetricCard label="单吨成本" :value="kpi.cost_per_ton" unit="元/吨" :change="kpi.cost_change" />
      <XtMetricCard label="毛利率" :value="kpi.gross_margin_pct" unit="%" tone="success" />
      <XtMetricCard label="本月累计成本" :value="kpi.mtd_total_cost" unit="万元" />
      <XtMetricCard label="本月累计收入" :value="kpi.mtd_revenue" unit="万元" tone="primary" />
    </XtKpiRibbon>

    <div class="cost-grid">
      <XtSectionCard title="BOM 成本构成">
        <XtErrorPanel v-if="error" :message="error" @retry="load" />
        <XtSkeleton v-else-if="loading" :rows="4" />
        <XtBarChart
          v-else
          :series="bomSeries"
          :x-labels="bomLabels"
          y-unit="元"
          height="240px"
          :stacked="true"
        />
      </XtSectionCard>

      <XtSectionCard title="单吨成本走势">
        <XtSkeleton v-if="loading" :rows="4" />
        <XtLineChart
          v-else
          :series="costTrendSeries"
          :x-labels="costTrendLabels"
          y-unit="元/吨"
          height="240px"
        />
      </XtSectionCard>
    </div>

    <XtSectionCard title="车间毛利热力">
      <XtDataTable
        :columns="profitColumns"
        :data="profitData"
        :striped="true"
        data-source="cost_analysis"
      />
      <XtEmpty v-if="!loading && !profitData.length" text="暂无成本数据" />
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
import XtLineChart from '../../components/xt/XtLineChart.vue'
import XtBarChart from '../../components/xt/XtBarChart.vue'
import XtDataTable from '../../components/xt/XtDataTable.vue'
import XtErrorPanel from '../../components/xt/XtErrorPanel.vue'
import XtSkeleton from '../../components/xt/XtSkeleton.vue'
import XtEmpty from '../../components/xt/XtEmpty.vue'

const dateRange = ref([])
const workshopFilter = ref('')
const workshops = ref([])
const loading = ref(false)
const error = ref('')
const kpi = ref({})
const bomSeries = ref([])
const bomLabels = ref([])
const costTrendSeries = ref([])
const costTrendLabels = ref([])
const profitData = ref([])

const profitColumns = [
  { key: 'workshop_name', label: '车间', width: '120px' },
  { key: 'output_tons', label: '产量(吨)', width: '100px' },
  { key: 'total_cost', label: '总成本(元)', width: '120px' },
  { key: 'cost_per_ton', label: '单吨成本', width: '100px' },
  { key: 'revenue', label: '收入(元)', width: '120px' },
  { key: 'gross_profit', label: '毛利(元)', width: '120px' },
  { key: 'margin_pct', label: '毛利率', width: '80px' }
]

async function load() {
  loading.value = true
  error.value = ''
  try {
    const params = {
      date_from: dateRange.value?.[0],
      date_to: dateRange.value?.[1],
      workshop_id: workshopFilter.value || undefined
    }
    const { data } = await api.get('/cost/summary', { params })
    kpi.value = data.kpi || {}
    bomSeries.value = data.bom?.series || []
    bomLabels.value = data.bom?.labels || []
    costTrendSeries.value = data.trend?.series || []
    costTrendLabels.value = data.trend?.labels || []
    profitData.value = data.profit_table || []
    workshops.value = data.workshops || workshops.value
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
  window.open(`/api/v1/cost/export?${params}`, '_blank')
}

onMounted(load)
</script>

<style scoped>
.cost-center {
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

.cost-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--xt-space-6);
}

@media (max-width: 1024px) {
  .cost-grid {
    grid-template-columns: 1fr;
  }
}
</style>
