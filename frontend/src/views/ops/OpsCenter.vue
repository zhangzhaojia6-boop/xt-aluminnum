<template>
  <section class="ops-center page-stack">
    <header class="page-header">
      <h1>运维告警中心</h1>
      <XtCommandBar v-model="dateRange">
        <template #filters>
          <el-select v-model="levelFilter" placeholder="告警级别" clearable style="width: 120px">
            <el-option label="紧急" value="critical" />
            <el-option label="警告" value="warning" />
            <el-option label="通知" value="info" />
          </el-select>
        </template>
      </XtCommandBar>
    </header>

    <XtKpiRibbon>
      <XtMetricCard label="设备 MTBF" :value="kpi.mtbf_hours" unit="小时" />
      <XtMetricCard label="设备 MTTR" :value="kpi.mttr_hours" unit="小时" />
      <XtMetricCard label="活跃告警" :value="kpi.active_alerts" tone="danger" />
      <XtMetricCard label="本月工单" :value="kpi.mtd_work_orders" />
    </XtKpiRibbon>

    <div class="ops-grid">
      <XtSectionCard title="告警趋势">
        <XtErrorPanel v-if="error" :message="error" @retry="load" />
        <XtSkeleton v-else-if="loading" :rows="4" />
        <XtBarChart
          v-else
          :series="alertSeries"
          :x-labels="alertLabels"
          y-unit="次"
          height="220px"
          :stacked="true"
        />
      </XtSectionCard>

      <XtSectionCard title="设备可靠性">
        <XtSkeleton v-if="loading" :rows="4" />
        <XtGaugeChart
          v-else
          :value="kpi.availability_pct || 0"
          :max="100"
          label="设备可用率"
          unit="%"
          height="200px"
        />
      </XtSectionCard>
    </div>

    <XtSectionCard title="告警明细">
      <XtDataTable
        :columns="columns"
        :data="alerts"
        :striped="true"
        data-source="ops_alerts"
      />
      <XtEmpty v-if="!loading && !alerts.length" text="当前无告警" />
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
import XtGaugeChart from '../../components/xt/XtGaugeChart.vue'
import XtDataTable from '../../components/xt/XtDataTable.vue'
import XtErrorPanel from '../../components/xt/XtErrorPanel.vue'
import XtSkeleton from '../../components/xt/XtSkeleton.vue'
import XtEmpty from '../../components/xt/XtEmpty.vue'

const dateRange = ref([])
const levelFilter = ref('')
const loading = ref(false)
const error = ref('')
const kpi = ref({})
const alertSeries = ref([])
const alertLabels = ref([])
const alerts = ref([])

const columns = [
  { key: 'created_at', label: '时间', width: '160px' },
  { key: 'level', label: '级别', width: '80px' },
  { key: 'device_name', label: '设备', width: '140px' },
  { key: 'message', label: '告警内容', width: '240px' },
  { key: 'status', label: '状态', width: '80px' },
  { key: 'work_order_no', label: '关联工单', width: '120px' }
]

async function load() {
  loading.value = true
  error.value = ''
  try {
    const params = {
      date_from: dateRange.value?.[0],
      date_to: dateRange.value?.[1],
      level: levelFilter.value || undefined
    }
    const { data } = await api.get('/ops/summary', { params })
    kpi.value = data.kpi || {}
    alertSeries.value = data.trend?.series || []
    alertLabels.value = data.trend?.labels || []
    alerts.value = data.alerts || []
  } catch (e) {
    error.value = e?.response?.data?.detail || '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.ops-center {
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

.ops-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: var(--xt-space-6);
}

@media (max-width: 1024px) {
  .ops-grid {
    grid-template-columns: 1fr;
  }
}
</style>
