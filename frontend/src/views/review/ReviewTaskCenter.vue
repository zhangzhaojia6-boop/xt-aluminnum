<template>
  <ReferencePageFrame
    module-number="07"
    title="异常与补录"
    :tags="['缺报', '退回', '差异', '同步滞后', '待归属', '待补重量']"
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
      <ReferenceKpiTile label="待归属" :value="pendingAssignmentCount" unit="卷" icon="归" status="warning" />
      <ReferenceKpiTile label="待补重量" :value="missingOutputWeightCount" unit="卷" icon="补" status="danger" />
    </section>

    <section class="review-task-center__main">
      <ReferenceModuleCard module-number="07" title="异常列表">
        <div class="review-task-center__toolbar">
          <el-radio-group v-model="tab" size="small">
            <el-radio-button label="missing">缺报</el-radio-button>
            <el-radio-button label="returned">退回</el-radio-button>
            <el-radio-button label="diff">差异</el-radio-button>
            <el-radio-button label="stale">同步滞后</el-radio-button>
            <el-radio-button label="pendingAssignment">待归属</el-radio-button>
            <el-radio-button label="missingOutput">待补重量</el-radio-button>
          </el-radio-group>
          <el-button size="small" :disabled="!filteredTasks.length">导出异常</el-button>
        </div>
        <ReferenceDataTable :data="filteredTasks" stripe v-loading="loading">
          <el-table-column prop="workshop" label="来源车间" min-width="130" />
          <el-table-column prop="shift" label="班次" width="90" />
          <el-table-column prop="trackingCard" label="随行卡" min-width="140" />
          <el-table-column prop="outputWeightLabel" label="产出" width="100" />
          <el-table-column prop="sourceLabel" label="录入来源" min-width="120" />
          <el-table-column prop="assignmentHint" label="归属线索" min-width="160" />
          <el-table-column prop="missingFieldLabel" label="缺失字段" min-width="130" />
          <el-table-column prop="anomaly" label="异常类型" min-width="150" />
          <el-table-column prop="aiSuggestion" label="AI 建议" min-width="220" />
          <el-table-column prop="risk" label="风险等级" width="110">
            <template #default="{ row }">
              <el-tag :type="riskTagType(row.risk)" effect="light">{{ row.risk }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="220">
            <template #default="{ row }">
              <div v-if="row.status === 'pending_assignment'" class="review-task-center__assign-action">
                <el-select
                  v-if="row.machineCandidates.length > 1 && !row.mesMachineId"
                  v-model="selectedMachineByEntry[row.entryId]"
                  size="small"
                  placeholder="选择机列"
                  filterable
                >
                  <el-option
                    v-for="machine in row.machineCandidates"
                    :key="machine.machine_id"
                    :label="machine.machine_name"
                    :value="machine.machine_id"
                  />
                </el-select>
                <el-button
                  link
                  type="primary"
                  :disabled="!row.canPromote"
                  :loading="promotingEntryId === row.entryId"
                  @click="promotePending(row)"
                >
                  绑定入账
                </el-button>
              </div>
              <div v-else-if="row.status === 'missing_output_weight'" class="review-task-center__missing-output-action">
                <el-button link type="primary" @click="openMissingOutputDialog(row)">补重量</el-button>
              </div>
              <template v-else>
                <el-button link type="primary" @click="goWorkshop(row.workshopId)">查看</el-button>
                <el-button link type="success" @click="goFactory">总览</el-button>
              </template>
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

      <div
        v-if="tab === 'pendingAssignment' || pendingAssignmentCount"
        class="review-task-center__binding-strip"
        aria-label="待归属绑定线索"
      >
        <article>
          <span>外部 MES 命中</span>
          <strong>{{ pendingAssignmentBindingSummary.mesMatched }}</strong>
          <em>卷</em>
        </article>
        <article>
          <span>唯一候选可入账</span>
          <strong>{{ pendingAssignmentBindingSummary.uniqueCandidate }}</strong>
          <em>卷</em>
        </article>
        <article>
          <span>多候选待选择</span>
          <strong>{{ pendingAssignmentBindingSummary.ambiguousCandidate }}</strong>
          <em>卷</em>
        </article>
        <article>
          <span>缺班次阻断</span>
          <strong>{{ pendingAssignmentBindingSummary.missingShift }}</strong>
          <em>卷</em>
        </article>
      </div>

      <PendingAssignmentHeatmap
        v-if="tab === 'pendingAssignment' || pendingAssignmentCount"
        :rows="pendingAssignment.items || []"
        class="review-task-center__pending-heatmap"
        aria-label="草稿待归属分布"
      />
    </section>

    <el-dialog
      v-model="missingOutputDialogVisible"
      title="补产出重量"
      width="min(440px, calc(100vw - 24px))"
      class="review-task-center__missing-output-dialog"
    >
      <div v-if="activeMissingOutput" class="review-task-center__missing-output-meta">
        <span>{{ activeMissingOutput.workshop }}</span>
        <span>{{ activeMissingOutput.assignmentHint }}</span>
        <span>{{ activeMissingOutput.trackingCard }}</span>
      </div>
      <div class="review-task-center__missing-output-form">
        <label>
          <span>产出重量</span>
          <el-input-number
            v-model="missingOutputForm.output_weight"
            :min="0"
            :max="activeMissingOutputInputLimit || undefined"
            :precision="3"
            :step="0.1"
            controls-position="right"
          />
          <em>吨</em>
        </label>
        <label>
          <span>补正原因</span>
          <el-input v-model="missingOutputForm.reason" type="textarea" :rows="3" maxlength="2000" show-word-limit />
        </label>
      </div>
      <template #footer>
        <el-button @click="missingOutputDialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          :loading="missingOutputSubmitting"
          :disabled="!canSubmitMissingOutput"
          @click="submitMissingOutputWeight"
        >
          确认补正
        </el-button>
      </template>
    </el-dialog>
  </ReferencePageFrame>
</template>

<script setup>
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import ReferenceDataTable from '../../components/reference/ReferenceDataTable.vue'
import ReferenceKpiTile from '../../components/reference/ReferenceKpiTile.vue'
import ReferenceModuleCard from '../../components/reference/ReferenceModuleCard.vue'
import ReferencePageFrame from '../../components/reference/ReferencePageFrame.vue'
import PendingAssignmentHeatmap from '../../components/charts/PendingAssignmentHeatmap.vue'
import { executeAssistantAction } from '../../api/ai-assistant'
import { fetchFactoryDashboard } from '../../api/dashboard'
import { fetchLiveActiveDate, fetchLiveAggregation, fetchPendingAssignmentEntries, resolveMissingOutputWeight } from '../../api/realtime'
import { formatWeight } from '../../utils/liveDashboardFormatters'

const router = useRouter()
const route = useRoute()
const targetDate = ref(dayjs().format('YYYY-MM-DD'))
const loading = ref(false)
const promotingEntryId = ref(null)
const missingOutputSubmitting = ref(false)
const missingOutputDialogVisible = ref(false)
const activeMissingOutput = ref(null)
const missingOutputForm = ref({ output_weight: null, reason: '' })
const selectedMachineByEntry = ref({})
const dashboard = ref({})
const pendingAssignment = ref({ summary: {}, items: [] })
const liveAggregation = ref({})
const VALID_TABS = new Set(['missing', 'returned', 'diff', 'stale', 'pendingAssignment', 'missingOutput'])
const tab = ref(resolveInitialTab())

function normalizeTab(value) {
  const text = typeof value === 'string' ? value : ''
  return VALID_TABS.has(text) ? text : ''
}

function resolveInitialTab() {
  return normalizeTab(route.query.tab) || 'missing'
}

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
      trackingCard: '-',
      outputWeightLabel: '-',
      sourceLabel: '-',
      assignmentHint: '-',
      missingFieldLabel: '-',
      anomaly: row.status_hint || status,
      aiSuggestion: buildSuggestionByStatus(status),
      risk
    })
  }
  return list
})

const missingTasks = computed(() => rawTasks.value.filter((item) => ['unreported', 'late', 'draft'].includes(item.status)))
const returnedTasks = computed(() => rawTasks.value.filter((item) => item.status === 'returned'))
const reconciliationOpenCount = computed(() => Number(dashboard.value.exception_lane?.reconciliation_open_count || 0) || 0)
const diffTasks = computed(() => {
  const count = reconciliationOpenCount.value
  if (count <= 0) return []
  return [
    {
      status: 'diff_open',
      workshop: '全厂',
      workshopId: null,
      shift: '-',
      trackingCard: '-',
      outputWeightLabel: '-',
      sourceLabel: '-',
      assignmentHint: '-',
      missingFieldLabel: '-',
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
      trackingCard: '-',
      outputWeightLabel: '-',
      sourceLabel: '-',
      assignmentHint: '-',
      missingFieldLabel: '-',
      anomaly: syncAnomalyLabel(syncStatus),
      aiSuggestion: buildSuggestionByStatus('sync_stale'),
      risk: status === 'failed' || status === 'migration_missing' || lagSeconds > 900 ? '高' : '中'
    }
  ]
})
const pendingAssignmentTasks = computed(() => {
  const rows = pendingAssignment.value.items || []
  return rows.map((item) => {
    const entryId = item.entry_id || null
    const selectedMachineId = entryId ? selectedMachineByEntry.value[entryId] : null
    const machineCandidates = normalizeMachineCandidates(item)
    return {
      status: 'pending_assignment',
      entryId,
      workshop: item.workshop_name || '-',
      workshopId: item.workshop_id || null,
      shift: item.shift_name || '-',
      shiftId: item.shift_id || null,
      trackingCard: item.tracking_card_no || '-',
      outputWeightLabel: `${formatWeight(item.output_weight)} 吨`,
      sourceLabel: formatAssignmentSource(item),
      assignmentHint: formatAssignmentHint(item),
      missingFieldLabel: formatMissingFields(item.missing_fields),
      anomaly: formatEntryState(item),
      aiSuggestion: buildSuggestionByStatus('pending_assignment'),
      risk: (item.missing_fields || []).length > 1 ? '高' : '中',
      mesMachineId: item.mes_machine_id || null,
      selectedMachineId,
      machineCandidates,
      canPromote: canPromotePendingAssignment(item, selectedMachineId)
    }
  })
})
const missingOutputWeight = computed(() => liveAggregation.value?.data_quality?.missing_output_weight || {})
const missingOutputWeightTasks = computed(() => {
  const rows = missingOutputWeight.value.items || []
  return rows.map((item) => ({
    status: 'missing_output_weight',
    entryId: item.entry_id || null,
    workshop: item.workshop_name || '-',
    workshopId: item.workshop_id || null,
    shift: item.shift_name || '-',
    shiftId: item.shift_id || null,
    trackingCard: item.tracking_card_no || '-',
    inputWeight: numberValue(item.input_weight),
    outputWeightLabel: '缺产出',
    sourceLabel: '卷级直录',
    assignmentHint: `${item.machine_name || '-'} / ${item.shift_name || '-'}`,
    missingFieldLabel: '产出重量',
    anomaly: '正式卷缺产出重量',
    aiSuggestion: buildSuggestionByStatus('missing_output_weight'),
    risk: '高'
  }))
})

const filteredTasks = computed(() => {
  if (tab.value === 'returned') return returnedTasks.value
  if (tab.value === 'diff') return diffTasks.value
  if (tab.value === 'stale') return staleTasks.value
  if (tab.value === 'pendingAssignment') return pendingAssignmentTasks.value
  if (tab.value === 'missingOutput') return missingOutputWeightTasks.value
  return missingTasks.value
})

const missingCount = computed(() => missingTasks.value.length)
const returnedCount = computed(() => returnedTasks.value.length)
const diffCount = reconciliationOpenCount
const pendingAssignmentCount = computed(() => Number(pendingAssignment.value.summary?.entry_count ?? pendingAssignment.value.total ?? 0) || 0)
const missingOutputWeightCount = computed(() => Number(missingOutputWeight.value.entry_count ?? missingOutputWeightTasks.value.length ?? 0) || 0)
const pendingAssignmentBindingSummary = computed(() => {
  const summary = {
    mesMatched: 0,
    uniqueCandidate: 0,
    ambiguousCandidate: 0,
    missingShift: 0
  }
  for (const item of pendingAssignment.value.items || []) {
    const missingFields = item.missing_fields || []
    const isMissingShift = missingFields.includes('shift_id')
    const mesMatched = Number(item.mes_match_count || 0) > 0
    const candidateCount = Number(item.machine_candidate_count || 0)
    if (mesMatched) summary.mesMatched += 1
    if (isMissingShift) {
      summary.missingShift += 1
      continue
    }
    if (!mesMatched && candidateCount === 1) summary.uniqueCandidate += 1
    if (!mesMatched && candidateCount > 1) summary.ambiguousCandidate += 1
  }
  return summary
})
const activeMissingOutputInputLimit = computed(() => numberValue(activeMissingOutput.value?.inputWeight))
const canSubmitMissingOutput = computed(() => {
  if (!activeMissingOutput.value?.entryId) return false
  const outputWeight = numberValue(missingOutputForm.value.output_weight)
  if (outputWeight <= 0) return false
  if (activeMissingOutputInputLimit.value > 0 && outputWeight > activeMissingOutputInputLimit.value) return false
  return Boolean(String(missingOutputForm.value.reason || '').trim())
})

const riskHighlights = computed(() => {
  const exceptionLane = dashboard.value.exception_lane || {}
  const items = []
  if (Number(exceptionLane.unreported_shift_count || 0) > 0) items.push(`缺报班次 ${exceptionLane.unreported_shift_count} 项`)
  if (Number(exceptionLane.returned_shift_count || 0) > 0) items.push(`退回班次 ${exceptionLane.returned_shift_count} 项`)
  if (Number(exceptionLane.reconciliation_open_count || 0) > 0) items.push(`差异待处理 ${exceptionLane.reconciliation_open_count} 项`)
  if (pendingAssignmentCount.value > 0) items.push(`待归属填报 ${pendingAssignmentCount.value} 卷`)
  if (missingOutputWeightCount.value > 0) items.push(`待补产出 ${missingOutputWeightCount.value} 卷`)
  return items
})

function buildSuggestionByStatus(status) {
  if (status === 'returned') return '优先补齐异常字段，并补充图片说明后重提。'
  if (status === 'late') return '先确认班次关键字段，提交后再补扩展项。'
  if (status === 'unreported') return '先触达责任人补报，避免影响日报发布。'
  if (status === 'submitted') return '检查来源完整性并定位差异。'
  if (status === 'reviewed' || status === 'auto_confirmed') return '保持当前节奏，关注新增异常。'
  if (status === 'sync_stale' || status === 'stale') return '先核对数据同步状态，再处理受影响记录。'
  if (status === 'pending_assignment') return '先确认机列或班次归属，保持草稿不进入产量。'
  if (status === 'missing_output_weight') return '按现场复核产出重量补正，补正后重新刷新实时聚合。'
  return '按班次闭环，优先处理阻塞项。'
}

function numberValue(value) {
  const parsed = Number(value ?? 0)
  return Number.isFinite(parsed) ? parsed : 0
}

function formatMissingFields(fields = []) {
  const labels = {
    machine_id: '机列',
    shift_id: '班次'
  }
  const mapped = fields.map((field) => labels[field] || field).filter(Boolean)
  return mapped.length ? mapped.join('、') : '-'
}

function formatEntryState(item = {}) {
  const status = item.entry_status === 'draft' ? '草稿' : item.entry_status || '-'
  const type = item.entry_type === 'mobile_coil' ? '卷级直录' : item.entry_type || '-'
  return `${status} / ${type}`
}

function formatAssignmentSource(item = {}) {
  if (!item.created_by_user_id) return '无账号录入'
  return item.created_by_user_name || item.created_by_username || `账号 ${item.created_by_user_id}`
}

function formatAssignmentHint(item = {}) {
  const mesMatchCount = Number(item.mes_match_count || 0)
  if (mesMatchCount > 0 && item.mes_machine_name) return `外部MES：${item.mes_machine_name}`
  if (mesMatchCount > 0) return '外部MES已匹配'
  const candidateCount = Number(item.machine_candidate_count || 0)
  if (candidateCount > 0) return `车间候选 ${candidateCount} 台`
  return '无机列候选'
}

function normalizeMachineCandidates(item = {}) {
  if (Array.isArray(item.machine_candidates) && item.machine_candidates.length) {
    return item.machine_candidates.map((machine) => ({
      machine_id: machine.machine_id,
      machine_name: machine.machine_name || `机列 ${machine.machine_id}`
    }))
  }
  return (item.machine_candidate_names || []).map((name, index) => ({
    machine_id: null,
    machine_name: name || `候选 ${index + 1}`
  }))
}

function canPromotePendingAssignment(item = {}, selectedMachineId = null) {
  if (item.entry_status !== 'draft') return false
  const missingFields = item.missing_fields || []
  if (missingFields.includes('shift_id')) return false
  if (item.mes_machine_id) return true
  const candidateCount = Number(item.machine_candidate_count || 0)
  if (candidateCount === 1) return true
  return candidateCount > 1 && Boolean(selectedMachineId)
}

function resolvePromoteMachineId(row) {
  if (row.mesMachineId) return row.mesMachineId
  if (row.selectedMachineId) return row.selectedMachineId
  if (row.machineCandidates.length === 1) return row.machineCandidates[0].machine_id || undefined
  return undefined
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

async function promotePending(row) {
  if (!row?.entryId || !row.canPromote || promotingEntryId.value) return
  promotingEntryId.value = row.entryId
  try {
    await executeAssistantAction({
      action: 'promote_draft_entry',
      target_type: 'work_order_entry',
      target_id: row.entryId,
      machine_id: resolvePromoteMachineId(row),
      shift_id: row.shiftId || undefined,
      reason: 'pending_assignment'
    })
    ElMessage.success('已绑定入账')
    await load()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '处理失败')
  } finally {
    promotingEntryId.value = null
  }
}

function openMissingOutputDialog(row) {
  activeMissingOutput.value = row
  missingOutputForm.value = { output_weight: null, reason: '' }
  missingOutputDialogVisible.value = true
}

async function submitMissingOutputWeight() {
  if (!canSubmitMissingOutput.value || missingOutputSubmitting.value) return
  missingOutputSubmitting.value = true
  try {
    await resolveMissingOutputWeight(activeMissingOutput.value.entryId, {
      output_weight: numberValue(missingOutputForm.value.output_weight),
      reason: String(missingOutputForm.value.reason || '').trim()
    })
    ElMessage.success('产出重量已补正')
    missingOutputDialogVisible.value = false
    activeMissingOutput.value = null
    await load()
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '补正失败')
  } finally {
    missingOutputSubmitting.value = false
  }
}

async function load() {
  loading.value = true
  try {
    const [dashboardResult, pendingAssignmentResult, liveAggregationResult] = await Promise.allSettled([
      fetchFactoryDashboard({ target_date: targetDate.value }),
      fetchPendingAssignmentEntries({ business_date: targetDate.value }),
      fetchLiveAggregation({ business_date: targetDate.value })
    ])
    if (dashboardResult.status === 'fulfilled') {
      dashboard.value = dashboardResult.value
    } else {
      throw dashboardResult.reason
    }
    pendingAssignment.value =
      pendingAssignmentResult.status === 'fulfilled' ? pendingAssignmentResult.value || { summary: {}, items: [] } : { summary: {}, items: [] }
    liveAggregation.value =
      liveAggregationResult.status === 'fulfilled' ? liveAggregationResult.value || {} : {}
  } finally {
    loading.value = false
  }
}

async function initializeActiveBusinessDate() {
  try {
    const payload = await fetchLiveActiveDate()
    if (payload?.business_date && payload.business_date !== targetDate.value) {
      targetDate.value = payload.business_date
      return true
    }
  } catch (_error) {
    return false
  }
  return false
}

watch(targetDate, () => {
  missingOutputDialogVisible.value = false
  activeMissingOutput.value = null
  load()
})
watch(() => route.query.tab, (value) => {
  const next = normalizeTab(value)
  if (next) tab.value = next
})
onMounted(async () => {
  const dateChanged = await initializeActiveBusinessDate()
  if (!dateChanged) {
    await load()
  }
})
</script>

<style scoped>
.review-task-center__kpis,
.review-task-center__main {
  display: grid;
  gap: 10px;
}

.review-task-center__kpis {
  grid-template-columns: repeat(5, minmax(0, 1fr));
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

.review-task-center__pending-heatmap {
  grid-column: 1 / -1;
  min-width: 0;
  min-height: 300px;
}

.review-task-center__binding-strip {
  grid-column: 1 / -1;
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1px;
  min-width: 0;
  overflow: hidden;
  border: 1px solid #d6dee8;
  border-radius: 8px;
  background: #d6dee8;
}

.review-task-center__binding-strip article {
  min-width: 0;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: baseline;
  gap: 4px;
  padding: 10px 12px;
  background: #fff;
}

.review-task-center__binding-strip span {
  min-width: 0;
  color: #4f6278;
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.review-task-center__binding-strip strong {
  color: #0c2d57;
  font-family: var(--xt-font-number, inherit);
  font-size: 20px;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
}

.review-task-center__binding-strip em {
  color: #667382;
  font-size: 12px;
  font-style: normal;
}

.review-task-center__assign-action {
  display: flex;
  align-items: center;
  gap: 8px;
}

.review-task-center__missing-output-action {
  display: flex;
  align-items: center;
}

.review-task-center__assign-action :deep(.el-select) {
  width: 116px;
}

.review-task-center__missing-output-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 14px;
}

.review-task-center__missing-output-meta span {
  min-width: 0;
  border: 1px solid #d6dee8;
  background: #f6f9fc;
  border-radius: 6px;
  padding: 5px 8px;
  font-size: 12px;
  color: #314154;
}

.review-task-center__missing-output-form {
  display: grid;
  gap: 12px;
}

.review-task-center__missing-output-form label {
  display: grid;
  gap: 6px;
}

.review-task-center__missing-output-form label:nth-child(1) {
  grid-template-columns: minmax(72px, auto) minmax(0, 1fr) auto;
  align-items: center;
}

.review-task-center__missing-output-form span {
  font-size: 13px;
  font-weight: 700;
  color: #1e2b3a;
}

.review-task-center__missing-output-form em {
  font-style: normal;
  color: #667382;
}

.review-task-center__missing-output-form :deep(.el-input-number) {
  width: 100%;
}

@media (max-width: 1100px) {
  .review-task-center__kpis,
  .review-task-center__main {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .review-task-center__binding-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
