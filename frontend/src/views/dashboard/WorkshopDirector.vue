<template>
  <div class="page-stack">
    <div class="page-header">
      <div>
        <h1>车间主任看板</h1>
        <p>只看本车间授权范围内的岗位直录、智能体处理进度、催报状态和异常闭环。</p>
      </div>
      <div class="header-actions">
        <el-date-picker v-model="targetDate" type="date" value-format="YYYY-MM-DD" />
        <el-select v-model="workshopId" placeholder="选择车间" clearable style="width: 160px">
          <el-option
            v-for="w in workshops"
            :key="w.id"
            :label="w.name"
            :value="w.id"
          />
        </el-select>
        <el-button @click="load">刷新</el-button>
      </div>
    </div>

    <section class="workshop-command panel" v-loading="loading">
      <div class="workshop-command__copy">
        <span>本车间运行层</span>
        <h2>把本车间的直录、补录、提醒和异常收进同一张运行面板里，不再等统计汇总。</h2>
        <p>这里重点盯产量、催报、库存物流、水电气和异常处置，让车间主任直接看到车间今天有没有跑顺。</p>
      </div>
      <div class="workshop-command__pills">
        <span v-for="pill in workshopPills" :key="pill">{{ pill }}</span>
      </div>
    </section>

    <div class="stat-grid" v-loading="loading">
      <div class="stat-card">
        <div class="stat-label">今日产量</div>
        <div class="stat-value">{{ formatNumber(data.total_output) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">月累计产量</div>
        <div class="stat-value">{{ formatNumber(data.month_to_date_output) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">上报率</div>
        <div class="stat-value">{{ data.mobile_reporting_summary?.reporting_rate ?? 0 }}%</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">待处理班次</div>
        <div class="stat-value">{{ data.pending_shift_count ?? 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">未报班次</div>
        <div class="stat-value">{{ data.reminder_summary?.unreported_count ?? 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">迟报班次</div>
        <div class="stat-value">{{ data.reminder_summary?.late_report_count ?? 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">今日催报次数</div>
        <div class="stat-value">{{ data.reminder_summary?.today_reminder_count ?? 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">今日发货</div>
        <div class="stat-value">{{ formatNumber(inventoryShipmentWeight) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">入库面积</div>
        <div class="stat-value">{{ formatNumber(inventoryInboundArea) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">实际库存</div>
        <div class="stat-value">{{ formatNumber(actualInventoryWeight) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">单吨能耗</div>
        <div class="stat-value">{{ formatNumber(data.energy_summary?.energy_per_ton) }}</div>
      </div>
    </div>

    <el-card class="panel" v-loading="loading">
      <template #header>生产泳道</template>
      <el-table :data="data.production_lane || []" stripe>
        <el-table-column prop="workshop_name" label="车间" />
        <el-table-column prop="total_output" label="产量">
          <template #default="{ row }">{{ formatNumber(row.total_output) }}</template>
        </el-table-column>
        <el-table-column prop="compare_value" label="昨日对比">
          <template #default="{ row }">{{ formatNumber(row.compare_value) }}</template>
        </el-table-column>
        <el-table-column prop="delta_vs_yesterday" label="变化">
          <template #default="{ row }">{{ formatNumber(row.delta_vs_yesterday) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="panel" v-loading="loading">
      <template #header>能耗泳道</template>
      <el-table :data="data.energy_lane || []" stripe>
        <el-table-column prop="shift_code" label="班次" />
        <el-table-column prop="source" label="来源">
          <template #default="{ row }">{{ row.source || '导入' }}</template>
        </el-table-column>
        <el-table-column prop="electricity_value" label="电耗">
          <template #default="{ row }">{{ formatNumber(row.electricity_value) }}</template>
        </el-table-column>
        <el-table-column prop="gas_value" label="气耗">
          <template #default="{ row }">{{ formatNumber(row.gas_value) }}</template>
        </el-table-column>
        <el-table-column prop="water_value" label="用水">
          <template #default="{ row }">{{ formatNumber(row.water_value) }}</template>
        </el-table-column>
        <el-table-column prop="energy_per_ton" label="单吨能耗">
          <template #default="{ row }">{{ formatNumber(row.energy_per_ton) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="panel" v-loading="loading">
      <template #header>库存物流泳道</template>
      <el-table :data="data.inventory_lane || []" stripe>
        <el-table-column prop="team_name" label="班组" />
        <el-table-column prop="storage_prepared" label="备料">
          <template #default="{ row }">{{ formatNumber(row.storage_prepared) }}</template>
        </el-table-column>
        <el-table-column prop="storage_finished" label="成品入库">
          <template #default="{ row }">{{ formatNumber(row.storage_finished) }}</template>
        </el-table-column>
        <el-table-column prop="storage_inbound_area" label="入库面积">
          <template #default="{ row }">{{ formatNumber(row.storage_inbound_area) }}</template>
        </el-table-column>
        <el-table-column prop="shipment_weight" label="发货">
          <template #default="{ row }">{{ formatNumber(row.shipment_weight) }}</template>
        </el-table-column>
        <el-table-column prop="actual_inventory_weight" label="实际库存">
          <template #default="{ row }">{{ formatNumber(row.actual_inventory_weight) }}</template>
        </el-table-column>
        <el-table-column prop="contract_received" label="合同承接量">
          <template #default="{ row }">{{ formatNumber(row.contract_received) }}</template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card class="panel" v-loading="loading">
      <template #header>异常与提醒泳道</template>
      <el-descriptions :column="4" border>
        <el-descriptions-item label="未报班次">{{ data.exception_lane?.unreported_shift_count ?? 0 }}</el-descriptions-item>
        <el-descriptions-item label="退回班次">{{ data.exception_lane?.returned_shift_count ?? 0 }}</el-descriptions-item>
        <el-descriptions-item label="迟报班次">{{ data.exception_lane?.reminder_late_count ?? 0 }}</el-descriptions-item>
        <el-descriptions-item label="待发布日报">{{ data.exception_lane?.pending_report_publish_count ?? 0 }}</el-descriptions-item>
      </el-descriptions>
      <div class="note">交付缺口：{{ formatDeliveryMissingSteps(delivery.missing_steps).join('；') }}</div>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'

import { fetchDeliveryStatus, fetchWorkshopDashboard } from '../../api/dashboard'
import { fetchWorkshops } from '../../api/master'
import { formatDeliveryMissingSteps, formatNumber } from '../../utils/display'

const targetDate = ref(dayjs().format('YYYY-MM-DD'))
const workshopId = ref(null)
const workshops = ref([])
const data = ref({})
const delivery = ref({})
const loading = ref(false)
const workshopPills = ['本车间直录', '专项 owner 补录', '自动催报', '自动异常归档']
const inventoryShipmentWeight = computed(() =>
  (data.value.inventory_lane || []).reduce((sum, row) => sum + (Number(row.shipment_weight) || 0), 0)
)
const inventoryInboundArea = computed(() =>
  (data.value.inventory_lane || []).reduce((sum, row) => sum + (Number(row.storage_inbound_area) || 0), 0)
)
const actualInventoryWeight = computed(() =>
  (data.value.inventory_lane || []).reduce((sum, row) => sum + (Number(row.actual_inventory_weight) || 0), 0)
)

async function load() {
  loading.value = true
  try {
    const params = { target_date: targetDate.value }
    if (workshopId.value) params.workshop_id = workshopId.value
    const [dashboardPayload, deliveryPayload] = await Promise.all([
      fetchWorkshopDashboard(params),
      fetchDeliveryStatus({ target_date: targetDate.value })
    ])
    data.value = dashboardPayload
    delivery.value = deliveryPayload
  } catch {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

watch([targetDate, workshopId], load)

onMounted(async () => {
  try {
    const items = await fetchWorkshops({ limit: 500, is_active: true })
    workshops.value = items
    if (items.length > 0) workshopId.value = items[0].id
  } catch {
    ElMessage.error('车间列表加载失败')
  }
  await load()
})
</script>

<style scoped>
.workshop-command,
.workshop-command__copy {
  display: grid;
  gap: 12px;
}

.workshop-command {
  padding: 22px;
  background:
    radial-gradient(circle at top right, rgba(37, 99, 235, 0.12), transparent 30%),
    radial-gradient(circle at bottom left, rgba(14, 165, 233, 0.1), transparent 34%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(244, 247, 251, 0.98));
}

.workshop-command__copy span {
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--app-muted);
}

.workshop-command__copy h2 {
  margin: 0;
  font-size: 30px;
  line-height: 1.2;
  color: var(--app-text);
}

.workshop-command__copy p {
  margin: 0;
  color: var(--app-muted);
  line-height: 1.7;
  max-width: 860px;
}

.workshop-command__pills {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.workshop-command__pills span {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 0 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(148, 163, 184, 0.16);
  color: var(--app-text);
  font-size: 13px;
  font-weight: 600;
  transition:
    transform 0.18s ease,
    box-shadow 0.18s ease,
    border-color 0.18s ease;
}

.workshop-command__pills span:hover {
  transform: translateY(-1px);
  border-color: rgba(37, 99, 235, 0.18);
  box-shadow: 0 12px 24px rgba(37, 99, 235, 0.1);
}
</style>
