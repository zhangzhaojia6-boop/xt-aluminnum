<template>
  <ReferencePageFrame
    module-number="07"
    title="审阅中心"
    :tags="['待审', '已审', '已驳回']"
    data-testid="review-task-center"
  >
    <template #actions>
      <el-date-picker v-model="targetDate" type="date" value-format="YYYY-MM-DD" />
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
    </template>

    <section class="review-task-center__kpis">
      <ReferenceKpiTile label="待审" :value="pendingCount" unit="项" icon="待" status="warning" />
      <ReferenceKpiTile label="已审" :value="approvedCount" unit="项" icon="审" status="success" />
      <ReferenceKpiTile label="已驳回" :value="rejectedCount" unit="项" icon="驳" status="danger" />
    </section>

    <section class="review-task-center__main">
      <ReferenceModuleCard module-number="07" title="任务列表">
        <template #actions>
          <el-radio-group v-model="tab" size="small">
            <el-radio-button label="pending">待审</el-radio-button>
            <el-radio-button label="approved">已审</el-radio-button>
            <el-radio-button label="rejected">已驳回</el-radio-button>
          </el-radio-group>
          <el-button size="small" :disabled="!filteredTasks.length">批量通过</el-button>
          <el-button size="small" :disabled="!filteredTasks.length">批量驳回</el-button>
          <el-button size="small" :disabled="!filteredTasks.length">导出清单</el-button>
        </template>
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
const tab = ref('pending')
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

const pendingTasks = computed(() => rawTasks.value.filter((item) => ['unreported', 'late', 'returned', 'draft', 'submitted'].includes(item.status)))
const approvedTasks = computed(() => rawTasks.value.filter((item) => ['reviewed', 'auto_confirmed'].includes(item.status)))
const rejectedTasks = computed(() => rawTasks.value.filter((item) => item.status === 'returned'))

const filteredTasks = computed(() => {
  if (tab.value === 'approved') return approvedTasks.value
  if (tab.value === 'rejected') return rejectedTasks.value
  return pendingTasks.value
})

const pendingCount = computed(() => pendingTasks.value.length)
const approvedCount = computed(() => approvedTasks.value.length)
const rejectedCount = computed(() => rejectedTasks.value.length)

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
  if (status === 'submitted') return '检查来源完整性并推进自动确认。'
  if (status === 'reviewed' || status === 'auto_confirmed') return '保持当前节奏，关注新增异常。'
  return '按班次闭环，优先处理阻塞项。'
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
