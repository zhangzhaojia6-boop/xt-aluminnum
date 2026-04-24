<template>
  <div class="page-stack review-workshop" data-testid="workshop-dashboard">
    <section class="review-workshop__overview panel review-workshop__reveal review-workshop__reveal--1" v-loading="loading">
      <div class="review-workshop__headline">
        <div class="review-workshop__eyebrow">工作面</div>
        <h1>车间审阅端</h1>
        <p>{{ workshopDisplayName }} · {{ targetDate }}</p>
      </div>

      <div class="review-workshop__controls">
        <el-date-picker v-model="targetDate" type="date" value-format="YYYY-MM-DD" />
        <el-select v-model="workshopId" placeholder="选择车间" clearable style="width: 210px">
          <el-option
            v-for="workshop in workshops"
            :key="workshop.id"
            :label="workshop.name"
            :value="workshop.id"
          />
        </el-select>
        <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
      </div>

      <ReviewCommandDeck :cards="commandCards" />
    </section>

    <el-card class="panel review-workshop__reveal review-workshop__reveal--2" v-loading="loading">
      <div class="panel-header-shell">
        <span class="panel-title-with-icon">
          <el-icon><Connection /></el-icon>
          数据流转
        </span>
        <div v-if="sourceTagsFor('今日数据流转').length" class="panel-source-tags">
          <span
            v-for="lane in sourceTagsFor('今日数据流转')"
            :key="`workshop-flow-${lane.key}`"
            :class="['panel-source-tag', sourceTagClass(lane)]"
          >
            {{ sourceTagText(lane) }}
          </span>
        </div>
      </div>
      <AgentRuntimeFlow
        compact
        title="先看来源，再看结果"
        :trace="runtimeTrace"
        :risks="data.exception_lane || {}"
      />
    </el-card>

    <div class="review-workshop__metric-grid review-workshop__reveal review-workshop__reveal--3">
      <div class="stat-card">
        <div class="stat-label">今日产量</div>
        <div v-if="sourceTagsFor('今日产量').length" class="stat-source-tags">
          <span
            v-for="lane in sourceTagsFor('今日产量')"
            :key="`workshop-output-${lane.key}`"
            :class="['stat-source-tag', sourceTagClass(lane)]"
          >
            {{ sourceTagText(lane) }}
          </span>
        </div>
        <div class="stat-value">{{ formatNumber(data.total_output) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">上报率</div>
        <div class="stat-value">{{ data.mobile_reporting_summary?.reporting_rate ?? 0 }}%</div>
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
        <div class="stat-label">待处理班次</div>
        <div class="stat-value">{{ data.pending_shift_count ?? 0 }}</div>
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
      <div class="stat-card">
        <div class="stat-label">月累计产量</div>
        <div class="stat-value">{{ formatNumber(data.month_to_date_output) }}</div>
      </div>
    </div>

    <el-card class="panel review-workshop__layers review-workshop__reveal review-workshop__reveal--4" v-loading="loading">
      <el-collapse v-model="activePanels">
        <el-collapse-item name="production">
          <template #title>
            <div class="workshop-panel-title">
              <span class="workshop-panel-title__name">
                <el-icon><TrendCharts /></el-icon>
                生产泳道
              </span>
              <small>产量与同比</small>
              <span v-if="sourceTagsFor('生产泳道').length" class="panel-source-tags panel-source-tags--inline">
                <span
                  v-for="lane in sourceTagsFor('生产泳道')"
                  :key="`product-tag-${lane.key}`"
                  :class="['panel-source-tag', sourceTagClass(lane)]"
                >
                  {{ sourceTagText(lane) }}
                </span>
              </span>
            </div>
          </template>
          <el-table :data="data.production_lane || []" class="workshop-lane-table" stripe size="small">
            <el-table-column prop="workshop_name" label="车间" min-width="130" />
            <el-table-column label="来源" width="150">
              <template #default="{ row }">
                <span :class="['lane-source-pill', laneSourceClass(row.source_variant)]">
                  {{ row.source_label || '主操直录' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="产量(吨)" min-width="120" align="right">
              <template #default="{ row }">
                {{ formatNumber(row.total_output) }}
              </template>
            </el-table-column>
            <el-table-column label="昨日(吨)" min-width="120" align="right">
              <template #default="{ row }">
                {{ formatNumber(row.compare_value) }}
              </template>
            </el-table-column>
            <el-table-column label="变化" min-width="120" align="right">
              <template #default="{ row }">
                <span :class="['workshop-delta', deltaClass(row.delta_vs_yesterday)]">
                  {{ formatDelta(row.delta_vs_yesterday) }}
                </span>
              </template>
            </el-table-column>
          </el-table>
        </el-collapse-item>

        <el-collapse-item name="energy">
          <template #title>
            <div class="workshop-panel-title">
              <span class="workshop-panel-title__name">
                <el-icon><Document /></el-icon>
                能耗泳道
              </span>
              <small>电 / 气 / 水</small>
              <span v-if="sourceTagsFor('能耗泳道').length" class="panel-source-tags panel-source-tags--inline">
                <span
                  v-for="lane in sourceTagsFor('能耗泳道')"
                  :key="`energy-tag-${lane.key}`"
                  :class="['panel-source-tag', sourceTagClass(lane)]"
                >
                  {{ sourceTagText(lane) }}
                </span>
              </span>
            </div>
          </template>
          <el-table :data="data.energy_lane || []" class="workshop-lane-table" stripe size="small">
            <el-table-column prop="shift_code" label="班次" width="110" />
            <el-table-column prop="source" label="来源">
              <template #default="{ row }">
                <span :class="['lane-source-pill', laneSourceClass(row.source_variant)]">
                  {{ row.source_label || '系统导入' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="电耗" min-width="110" align="right">
              <template #default="{ row }">
                {{ formatNumber(row.electricity_value) }}
              </template>
            </el-table-column>
            <el-table-column label="气耗" min-width="110" align="right">
              <template #default="{ row }">
                {{ formatNumber(row.gas_value) }}
              </template>
            </el-table-column>
            <el-table-column prop="water_value" label="用水" min-width="110" align="right">
              <template #default="{ row }">
                {{ formatNumber(row.water_value) }}
              </template>
            </el-table-column>
            <el-table-column label="单吨能耗" min-width="120" align="right">
              <template #default="{ row }">
                {{ formatNumber(row.energy_per_ton) }}
              </template>
            </el-table-column>
          </el-table>
        </el-collapse-item>

        <el-collapse-item name="inventory">
          <template #title>
            <div class="workshop-panel-title">
              <span class="workshop-panel-title__name">
                <el-icon><Promotion /></el-icon>
                库存泳道
              </span>
              <small>库存与发货</small>
              <span v-if="sourceTagsFor('库存物流泳道').length" class="panel-source-tags panel-source-tags--inline">
                <span
                  v-for="lane in sourceTagsFor('库存物流泳道')"
                  :key="`inventory-tag-${lane.key}`"
                  :class="['panel-source-tag', sourceTagClass(lane)]"
                >
                  {{ sourceTagText(lane) }}
                </span>
              </span>
            </div>
          </template>
          <el-table :data="data.inventory_lane || []" class="workshop-lane-table" stripe size="small">
            <el-table-column prop="team_name" label="班组" min-width="120" />
            <el-table-column label="来源" width="150">
              <template #default="{ row }">
                <span :class="['lane-source-pill', laneSourceClass(row.source_variant)]">
                  {{ row.source_label || '系统导入' }}
                </span>
              </template>
            </el-table-column>
            <el-table-column label="备料(吨)" min-width="110" align="right">
              <template #default="{ row }">
                {{ formatNumber(row.storage_prepared) }}
              </template>
            </el-table-column>
            <el-table-column label="入库(吨)" min-width="110" align="right">
              <template #default="{ row }">
                {{ formatNumber(row.storage_finished) }}
              </template>
            </el-table-column>
            <el-table-column label="面积(㎡)" min-width="110" align="right">
              <template #default="{ row }">
                {{ formatNumber(row.storage_inbound_area) }}
              </template>
            </el-table-column>
            <el-table-column label="发货(吨)" min-width="110" align="right">
              <template #default="{ row }">
                {{ formatNumber(row.shipment_weight) }}
              </template>
            </el-table-column>
            <el-table-column label="库存(吨)" min-width="110" align="right">
              <template #default="{ row }">
                {{ formatNumber(row.actual_inventory_weight) }}
              </template>
            </el-table-column>
          </el-table>
        </el-collapse-item>

        <el-collapse-item name="exception">
          <template #title>
            <div class="workshop-panel-title">
              <span class="workshop-panel-title__name">
                <el-icon><WarningFilled /></el-icon>
                异常与处理
              </span>
              <small>重点先行</small>
              <span v-if="sourceTagsFor('异常与提醒泳道').length" class="panel-source-tags panel-source-tags--inline">
                <span
                  v-for="lane in sourceTagsFor('异常与提醒泳道')"
                  :key="`exception-tag-${lane.key}`"
                  :class="['panel-source-tag', sourceTagClass(lane)]"
                >
                  {{ sourceTagText(lane) }}
                </span>
              </span>
            </div>
          </template>
          <el-descriptions :column="4" border>
            <el-descriptions-item label="未报班次">{{ data.exception_lane?.unreported_shift_count ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="退回班次">{{ data.exception_lane?.returned_shift_count ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="迟报班次">{{ data.exception_lane?.reminder_late_count ?? 0 }}</el-descriptions-item>
            <el-descriptions-item label="待发布日报">{{ data.exception_lane?.pending_report_publish_count ?? 0 }}</el-descriptions-item>
          </el-descriptions>
          <p class="review-workshop__note">交付缺口：{{ formatDeliveryMissingSteps(delivery.missing_steps).join('；') }}</p>
        </el-collapse-item>
      </el-collapse>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import dayjs from 'dayjs'
import { Connection, Document, Promotion, TrendCharts, WarningFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

import { fetchDeliveryStatus, fetchWorkshopDashboard } from '../../api/dashboard'
import AgentRuntimeFlow from '../../components/review/AgentRuntimeFlow.vue'
import ReviewCommandDeck from '../../components/review/ReviewCommandDeck.vue'
import { fetchWorkshops } from '../../api/master'
import { formatDeliveryMissingSteps, formatNumber } from '../../utils/display'

const targetDate = ref(dayjs().format('YYYY-MM-DD'))
const workshopId = ref(null)
const workshops = ref([])
const data = ref({})
const delivery = ref({})
const loading = ref(false)
const activePanels = ref(['production', 'energy', 'inventory', 'exception'])
const lastLoadErrorMessage = ref('')

const commandCards = computed(() => [
  {
    key: 'workshop-command-1',
    label: '当前动作',
    value: '先处理异常',
    hint: '生产、能耗、库存分区',
    tone: 'primary'
  },
  {
    key: 'workshop-command-2',
    label: '待处理班次',
    value: String(data.value.pending_shift_count ?? 0),
    hint: '先跟进未闭环项',
    tone: (data.value.pending_shift_count ?? 0) > 0 ? 'alert' : 'success'
  },
  {
    key: 'workshop-command-3',
    label: '异常工单',
    value: String((data.value.exception_lane?.mobile_exception_count ?? 0) + (data.value.exception_lane?.returned_shift_count ?? 0)),
    hint: '需确认后再归档',
    tone: ((data.value.exception_lane?.mobile_exception_count ?? 0) + (data.value.exception_lane?.returned_shift_count ?? 0)) > 0 ? 'alert' : 'success'
  },
  {
    key: 'workshop-command-4',
    label: '交付状态',
    value: delivery.value.delivery_ready ? '可交付' : '未就绪',
    hint: formatDeliveryMissingSteps(delivery.value.missing_steps).join('；') || '关键链路已具备',
    tone: delivery.value.delivery_ready ? 'success' : 'primary'
  }
])

const runtimeTrace = computed(() => data.value.runtime_trace || {})
const runtimeSourceIndex = computed(() => {
  const index = {}
  for (const lane of runtimeTrace.value.source_lanes || []) {
    for (const target of lane.result_targets || []) {
      if (!index[target]) index[target] = []
      index[target].push(lane)
    }
  }
  return index
})

const inventoryShipmentWeight = computed(() =>
  (data.value.inventory_lane || []).reduce((sum, row) => sum + (Number(row.shipment_weight) || 0), 0)
)
const inventoryInboundArea = computed(() =>
  (data.value.inventory_lane || []).reduce((sum, row) => sum + (Number(row.storage_inbound_area) || 0), 0)
)
const actualInventoryWeight = computed(() =>
  (data.value.inventory_lane || []).reduce((sum, row) => sum + (Number(row.actual_inventory_weight) || 0), 0)
)

const workshopDisplayName = computed(() => {
  const selected = workshops.value.find((item) => item.id === workshopId.value)
  return selected?.name || '全部车间'
})

function sourceTagsFor(target) {
  return runtimeSourceIndex.value[target] || []
}

function sourceTagText(lane) {
  if (!lane?.stage_label) return `来自 ${lane?.label || ''}`.trim()
  return `${lane.label} · ${lane.stage_label}`
}

function sourceTagClass(lane) {
  return lane?.status ? `is-${lane.status}` : ''
}

function laneSourceClass(variant) {
  const normalized = String(variant || '').toLowerCase()
  if (normalized === 'owner') return 'is-owner'
  if (normalized === 'mobile') return 'is-mobile'
  return 'is-import'
}

function formatDelta(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric) || numeric === 0) return '0'
  return `${numeric > 0 ? '+' : ''}${formatNumber(numeric)}`
}

function deltaClass(value) {
  const numeric = Number(value)
  if (!Number.isFinite(numeric) || numeric === 0) return 'is-flat'
  return numeric > 0 ? 'is-up' : 'is-down'
}

function requestErrorMessage(error, fallback = '加载失败') {
  const detail = error?.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || item).join('；')
  }
  if (detail && typeof detail === 'object') {
    return detail.message || detail.msg || fallback
  }
  if (typeof detail === 'string' && detail.trim()) {
    return detail.trim()
  }
  return error?.message || fallback
}

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
    lastLoadErrorMessage.value = ''
  } catch (error) {
    const message = requestErrorMessage(error, '加载车间审阅数据失败，请稍后重试')
    if (message !== lastLoadErrorMessage.value) {
      ElMessage.error(message)
      lastLoadErrorMessage.value = message
    }
  } finally {
    loading.value = false
  }
}

watch([targetDate, workshopId], load)

onMounted(async () => {
  try {
    const items = await fetchWorkshops({ limit: 500, is_active: true })
    workshops.value = items
    if (items.length > 0 && !workshopId.value) workshopId.value = items[0].id
  } catch (error) {
    const message = requestErrorMessage(error, '车间列表加载失败，请稍后重试')
    if (message !== lastLoadErrorMessage.value) {
      ElMessage.error(message)
      lastLoadErrorMessage.value = message
    }
  }
  await load()
})
</script>

<style scoped>
.review-workshop__overview,
.review-workshop__headline {
  display: grid;
  gap: 8px;
}

.review-workshop__overview {
  padding: 14px;
  background:
    radial-gradient(circle at top right, rgba(37, 99, 235, 0.1), transparent 30%),
    radial-gradient(circle at bottom left, rgba(14, 165, 233, 0.06), transparent 34%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(248, 251, 255, 0.98));
}

.review-workshop__eyebrow {
  font-size: 12px;
  letter-spacing: 0.02em;
  text-transform: none;
  color: var(--app-muted);
}

.review-workshop__eyebrow + h1,
.review-workshop__headline h1 {
  margin: 0;
  font-size: 26px;
  line-height: 1.16;
  color: var(--app-text);
}

.review-workshop__headline p {
  margin: 0;
  color: var(--app-muted);
}

.review-workshop__controls {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.review-workshop__metric-grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
}

.review-workshop__reveal {
  opacity: 0;
  transform: translateY(8px);
  animation: review-workshop-reveal 0.24s ease forwards;
}

.review-workshop__reveal--1 {
  animation-delay: 0.02s;
}

.review-workshop__reveal--2 {
  animation-delay: 0.04s;
}

.review-workshop__reveal--3 {
  animation-delay: 0.06s;
}

.review-workshop__reveal--4 {
  animation-delay: 0.08s;
}

.review-workshop__overview {
  border-radius: 16px;
  border: 1px solid rgba(148, 163, 184, 0.16);
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.06);
}

.review-workshop__note {
  margin: 10px 0 0;
  color: var(--app-muted);
  line-height: 1.58;
  max-height: 1.7em;
  overflow: hidden;
  transition: max-height 0.22s ease;
}

.review-workshop__overview:hover .review-workshop__note {
  max-height: 5.1em;
}

.workshop-panel-title {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
}

.workshop-panel-title small {
  color: var(--app-muted);
}

.panel-title-with-icon,
.workshop-panel-title__name {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.review-workshop__layers :deep(.el-collapse-item__header) {
  padding: 10px 4px;
}

.review-workshop__layers :deep(.el-collapse-item__content) {
  padding-top: 14px;
  padding-bottom: 10px;
}

.review-workshop__layers {
  border-radius: 18px;
}

.review-workshop__layers :deep(.el-collapse-item__header) {
  padding: 8px 0;
}

.review-workshop__layers :deep(.el-collapse-item__header) .el-collapse-item__arrow {
  color: var(--app-muted);
}

.panel-source-tags--inline {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.workshop-lane-table {
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 12px;
  overflow: hidden;
}

.workshop-lane-table :deep(.el-table__cell) {
  padding-top: 8px;
  padding-bottom: 8px;
}

.workshop-lane-table :deep(.cell) {
  font-size: 12px;
}

.workshop-lane-table :deep(thead .cell) {
  font-size: 11px;
  letter-spacing: 0.02em;
  color: #475569;
}

.workshop-delta {
  font-weight: 600;
  letter-spacing: 0.01em;
}

.workshop-delta.is-up {
  color: #0f766e;
}

.workshop-delta.is-down {
  color: #b91c1c;
}

.workshop-delta.is-flat {
  color: #64748b;
}

.workshop-panel-title {
  color: var(--app-text);
}

.workshop-panel-title span {
  font-size: 14px;
  font-weight: 600;
}

.workshop-panel-title__name .el-icon {
  width: 18px;
  height: 18px;
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: #1d4ed8;
  background: rgba(219, 234, 254, 0.82);
}

.workshop-panel-title small {
  font-size: 13px;
  color: var(--app-muted);
}

@keyframes review-workshop-reveal {
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (max-width: 1200px) {
  .review-workshop__metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .review-workshop__overview {
    padding: 16px;
  }

  .review-workshop__headline h1,
  .review-workshop__eyebrow + h1 {
    font-size: 24px;
  }

  .review-workshop__metric-grid {
    grid-template-columns: 1fr;
  }

  .review-workshop__controls {
    width: 100%;
  }
}
</style>
