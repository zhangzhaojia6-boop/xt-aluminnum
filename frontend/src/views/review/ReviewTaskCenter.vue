<template>
  <ReferencePageFrame
    module-number="07"
    title="异常与补录"
    :tags="['缺报', '退回', '差异', '同步滞后']"
    data-testid="review-task-center"
  >
    <template #actions>
      <el-date-picker v-model="targetDate" type="date" value-format="YYYY-MM-DD" />
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
    </template>

    <section class="review-task-center__kpis">
      <ReferenceKpiTile label="缺报" :value="missingCount" unit="项" icon="缺" status="warning" />
      <ReferenceKpiTile label="退回" :value="returnedCount" unit="项" icon="退" status="danger" />
      <ReferenceKpiTile label="差异" :value="diffCount" unit="项" icon="差" status="warning" />
    </section>

    <section class="review-task-center__main">
      <ReferenceModuleCard module-number="07" title="异常列表">
        <div class="review-task-center__toolbar">
          <el-radio-group v-model="tab" size="small">
            <el-radio-button label="missing">缺报</el-radio-button>
            <el-radio-button label="returned">退回</el-radio-button>
            <el-radio-button label="diff">差异</el-radio-button>
            <el-radio-button label="stale">同步滞后</el-radio-button>
          </el-radio-group>
          <el-button size="small" :disabled="!filteredTasks.length">导出异常</el-button>
        </div>
        <ReferenceDataTable :data="filteredTasks" stripe v-loading="loading">
          <el-table-column prop="workshop" label="来源车间" min-width="130" />
          <el-table-column prop="shift" label="班次" width="90" />
          <el-table-column prop="anomaly" label="异常类型" min-width="150" />
          <el-table-column prop="aiSuggestion" label="AI 建议" min-width="220" />
          <el-table-column prop="risk" label="风险等级" width="110">
            <template #default="{ row }">
              <el-tag :type="riskTagType(row.risk)" effect="light">{{ row.risk }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150">
            <template #default="{ row }">
              <el-button link type="primary" @click="goWorkshop(row.workshopId)">查看</el-button>
              <el-button link type="success" @click="goFactory">总览</el-button>
            </template>
          </el-table-column>
        </ReferenceDataTable>
        <div v-if="!filteredTasks.length" class="template-empty">当前分组暂无任务</div>
      </ReferenceModuleCard>

      <ReferenceModuleCard module-number="09" title="风险卡">
        <ul class="review-task-center__risk-list">
          <li v-for="item in riskHighlights" :key="item">{{ item }}</li>
          <li v-if="!riskHighlights.length">暂无高风险项</li>
        </ul>
      </ReferenceModuleCard>
    </section>
  </ReferencePageFrame>
</template>

<script setup>
import dayjs from 'dayjs'
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import ReferenceDataTable from '../../components/reference/ReferenceDataTable.vue'
import ReferenceKpiTile from '../../components/reference/ReferenceKpiTile.vue'
import ReferenceModuleCard from '../../components/reference/ReferenceModuleCard.vue'
import ReferencePageFrame from '../../components/reference/ReferencePageFrame.vue'
import { fetchFactoryDashboard } from '../../api/dashboard'

const router = useRouter()
const targetDate = ref(dayjs().format('YYYY-MM-DD'))
const loading = ref(false)
const tab = ref('missing')
const dashboard = ref({})

const rawTasks = computed(() => {
  const list = []
  const reportingRows = dashboard.value.workshop_reporting_status || []
  for (const row of reportingRows) {
    const status = String(row.report_status || 'unreported')
    const risk = status === 'returned' || status === 'late' ? '高' : status === 'unreported' ? '中' : '低'
    list.push({
      status,
      workshop: row.workshop_name || '-',
      workshopId: row.workshop_id || null,
      shift: row.shift_code || '-',
      anomaly: row.status_hint || status,
      aiSuggestion: buildSuggestionByStatus(status),
      risk
    })
  }
  return list
})

const missingTasks = computed(() => rawTasks.value.filter((item) => ['unreported', 'late', 'draft'].includes(item.status)))
const returnedTasks = computed(() => rawTasks.value.filter((item) => item.status === 'returned'))
const diffTasks = computed(() => {
  const count = Number(dashboard.value.exception_lane?.reconciliation_open_count || 0)
  if (count <= 0) return []
  return [
    {
      status: 'diff_open',
      workshop: '全厂',
      workshopId: null,
      shift: '-',
      anomaly: `差异核对 ${count} 项`,
      aiSuggestion: '先核对系统口径与补录来源，关闭影响日报的差异。',
      risk: count > 3 ? '高' : '中'
    }
  ]
})
const staleTasks = computed(() => {
  const syncStatus = dashboard.value.mes_sync_status || {}
  const status = String(syncStatus.status || syncStatus.last_run_status || '')
  const lagSeconds = Number(syncStatus.lag_seconds || 0)
  if (!['stale', 'failed', 'migration_missing', 'unconfigured', 'offline_or_blocked'].includes(status) && lagSeconds <= 300) return []
  return [
    {
      status: status || 'sync_stale',
      workshop: '数据接入',
      workshopId: null,
      shift: '-',
      anomaly: syncAnomalyLabel(syncStatus),
      aiSuggestion: buildSuggestionByStatus('sync_stale'),
      risk: status === 'failed' || status === 'migration_missing' || lagSeconds > 900 ? '高' : '中'
    }
  ]
})

const filteredTasks = computed(() => {
  if (tab.value === 'returned') return returnedTasks.value
  if (tab.value === 'diff') return diffTasks.value
  if (tab.value === 'stale') return staleTasks.value
  return missingTasks.value
})

const missingCount = computed(() => missingTasks.value.length)
const returnedCount = computed(() => returnedTasks.value.length)
const diffCount = computed(() => diffTasks.value.length)

const riskHighlights = computed(() => {
  const exceptionLane = dashboard.value.exception_lane || {}
  const items = []
  if (Number(exceptionLane.unreported_shift_count || 0) > 0) items.push(`缺报班次 ${exceptionLane.unreported_shift_count} 项`)
  if (Number(exceptionLane.returned_shift_count || 0) > 0) items.push(`退回班次 ${exceptionLane.returned_shift_count} 项`)
  if (Number(exceptionLane.reconciliation_open_count || 0) > 0) items.push(`差异待处理 ${exceptionLane.reconciliation_open_count} 项`)
  return items
})

function buildSuggestionByStatus(status) {
  if (status === 'returned') return '优先补齐异常字段，并补充图片说明后重提。'
  if (status === 'late') return '先确认班次关键字段，提交后再补扩展项。'
  if (status === 'unreported') return '先触达责任人补报，避免影响日报发布。'
  if (status === 'submitted') return '检查来源完整性并定位差异。'
  if (status === 'reviewed' || status === 'auto_confirmed') return '保持当前节奏，关注新增异常。'
  if (status === 'sync_stale' || status === 'stale') return '先核对数据同步状态，再处理受影响记录。'
  return '按班次闭环，优先处理阻塞项。'
}

function syncAnomalyLabel(syncStatus = {}) {
  const status = String(syncStatus.status || syncStatus.last_run_status || '')
  if (status === 'failed') return '同步失败'
  if (status === 'migration_missing') return '投影未就绪'
  if (status === 'unconfigured') return 'MES 未配置'
  const lagSeconds = Number(syncStatus.lag_seconds || 0)
  if (lagSeconds > 0) return `同步滞后 ${Math.ceil(lagSeconds / 60)} 分钟`
  return '同步滞后'
}

function riskTagType(risk) {
  if (risk === '高') return 'danger'
  if (risk === '中') return 'warning'
  return 'success'
}

function goWorkshop(workshopId) {
  if (!workshopId) {
    router.push({ name: 'workshop-dashboard' })
    return
  }
  router.push({ name: 'workshop-dashboard', query: { workshop_id: String(workshopId) } })
}

function goFactory() {
  router.push({ name: 'factory-dashboard' })
}

async function load() {
  loading.value = true
  try {
    dashboard.value = await fetchFactoryDashboard({ target_date: targetDate.value })
  } finally {
    loading.value = false
  }
}

watch(targetDate, load)
onMounted(load)
</script>

<style scoped>
.review-task-center__kpis,
.review-task-center__main {
  display: grid;
  gap: 10px;
}

.review-task-center__kpis {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.review-task-center__main {
  grid-template-columns: minmax(0, 1fr) 320px;
}

.review-task-center__toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 10px;
  flex-wrap: wrap;
}

.review-task-center__risk-list {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 8px;
}

@media (max-width: 1100px) {
  .review-task-center__kpis,
  .review-task-center__main {
    grid-template-columns: 1fr;
  }
}
</style>
