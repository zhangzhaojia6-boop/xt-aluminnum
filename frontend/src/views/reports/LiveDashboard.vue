<template>
  <ReferencePageFrame
    module-number="12"
    title="工厂实时态势"
    :tags="['全厂', '机列填报', '实时状态']"
    class="live-dashboard"
    data-testid="live-dashboard"
  >
    <template #actions>
      <el-date-picker v-model="targetDate" type="date" value-format="YYYY-MM-DD" />
      <div class="live-dashboard__connection">
        <span :class="['live-dashboard__connection-dot', `is-${connectionTone}`]"></span>
        <span>{{ connectionLabel }}</span>
      </div>
      <div class="live-dashboard__progress-pill">
        {{ commandSummary.dataSourceLabel }}
      </div>
      <el-button :icon="RefreshRight" @click="loadDashboardSurface()">刷新</el-button>
    </template>

    <section class="command-status-strip">
      <article class="command-status-card command-status-card--output">
        <span>今日产出</span>
        <strong>{{ formatWeight(commandSummary.todayOutput) }}</strong>
        <em>kg</em>
      </article>
      <article class="command-status-card">
        <span>提交进度</span>
        <strong>{{ commandSummary.submittedCells }}/{{ commandSummary.totalCells }}</strong>
        <em>{{ commandSummary.completionRate }}%</em>
      </article>
      <article class="command-status-card" :class="{ 'is-danger': commandSummary.missingCellCount > 0 }">
        <span>缺报单元</span>
        <strong>{{ commandSummary.missingCellCount }}</strong>
        <em>机列班次</em>
      </article>
      <article class="command-status-card" :class="{ 'is-warning': commandSummary.attentionCellCount > 0 }">
        <span>关注单元</span>
        <strong>{{ commandSummary.attentionCellCount }}</strong>
        <em>需处理</em>
      </article>
      <article class="command-status-card">
        <span>正式成材率</span>
        <strong :class="yieldToneClass(commandSummary.yieldRate)">{{ formatPercent(commandSummary.yieldRate) }}</strong>
        <em>{{ commandSummary.dataSourceLabel }}</em>
      </article>
      <article class="command-status-card">
        <span>更新时间</span>
        <strong>{{ lastRefreshLabel }}</strong>
        <em>延迟 {{ commandSummary.syncLagLabel }}</em>
      </article>
    </section>

    <div class="live-dashboard__workshops" v-loading="loading">
      <el-empty
        v-if="!loading && !sortedWorkshops.length"
        description="当前日期暂无实时卷数据"
      />

      <el-collapse v-else v-model="activePanels" class="live-dashboard__collapse">
        <el-collapse-item
          v-for="workshop in sortedWorkshops"
          :key="workshop.workshop_id"
          :name="String(workshop.workshop_id)"
          class="live-dashboard__collapse-item"
        >
          <template #title>
            <div class="live-workshop__title">
              <div>
                <strong>{{ workshop.workshop_name }}</strong>
                <span>{{ workshop.machines.length }} 台机台</span>
              </div>
              <div class="live-workshop__title-meta">
                <span>投 {{ formatWeight(workshop.workshop_total?.input) }}</span>
                <span>产 {{ formatWeight(workshop.workshop_total?.output) }}</span>
                <span>正式率 {{ formatPercent(workshop.workshop_total?.yield_rate) }}</span>
              </div>
            </div>
          </template>

          <div class="live-workshop__board" v-if="workshop.machines.length">
            <div class="live-board__scroller">
              <div class="live-board__table" :style="boardGridStyle(workshop)">
                <div class="live-board__row live-board__row--head live-board__row--grid">
                  <div class="live-board__stub">机台</div>
                  <div
                    v-for="shift in getWorkshopShifts(workshop)"
                    :key="`head-${workshop.workshop_id}-${shift.shift_id}`"
                    class="live-board__head-cell"
                  >
                    {{ shift.shift_name }}
                  </div>
                  <div class="live-board__head-cell live-board__head-cell--total">日合计</div>
                </div>

                <div
                  v-for="machine in workshop.machines"
                  :key="machine.machine_id"
                  class="live-board__row live-board__row--grid"
                >
                  <div class="live-board__stub live-board__stub--machine">{{ machine.machine_name }}</div>
                  <button
                    v-for="shift in machine.shifts"
                    :key="cellKey(workshop.workshop_id, machine.machine_id, shift.shift_id)"
                    type="button"
                    :class="[
                      'live-cell',
                      `is-${shift.submission_status}`,
                      `tone-${statusToneForCell(shift)}`,
                      { 'is-disabled': !shift.is_applicable },
                      { 'is-updated': isUpdated(cellKey(workshop.workshop_id, machine.machine_id, shift.shift_id)) }
                    ]"
                    :disabled="!shift.is_applicable"
                    @click="openDrawer(workshop, machine, shift)"
                  >
                    <span class="live-cell__symbol">{{ submissionSymbol(shift.submission_status) }}</span>
                    <strong>{{ statusTextForCell(shift) }}</strong>
                    <span class="live-cell__count">{{ shift.is_applicable ? `${shift.submitted_count} 卷` : '—' }}</span>
                    <span :class="['live-cell__yield', yieldToneClass(shift.yield_rate)]">
                      {{ shift.is_applicable ? `兼容率 ${formatPercent(shift.yield_rate)}` : '—' }}
                    </span>
                  </button>
                  <div class="live-board__total-cell">
                    <strong>投 {{ formatWeight(machine.day_total?.input) }}</strong>
                    <span>产 {{ formatWeight(machine.day_total?.output) }}</span>
                    <span>废 {{ formatWeight(machine.day_total?.scrap) }}</span>
                    <span>兼容率 {{ formatPercent(machine.day_total?.yield_rate) }}</span>
                  </div>
                </div>

                <div class="live-board__row live-board__row--grid live-board__row--attendance">
                  <div class="live-board__stub">考勤</div>
                  <div
                    v-for="shift in getAttendanceShifts(workshop)"
                    :key="attendanceKey(workshop.workshop_id, shift.shift_id)"
                    :class="[
                      'live-attendance-cell',
                      { 'is-disabled': !shift.is_applicable },
                      {
                        'is-updated': isUpdated(attendanceKey(workshop.workshop_id, shift.shift_id))
                      }
                    ]"
                  >
                    {{ formatAttendance(shift) }}
                  </div>
                  <div class="live-board__total-cell live-board__total-cell--muted">
                    自动同步考勤确认状态
                  </div>
                </div>

                <div class="live-board__row live-board__row--grid live-board__row--summary">
                  <div class="live-board__stub">合计</div>
                  <div
                    v-for="shiftTotal in getWorkshopShiftTotals(workshop)"
                    :key="`summary-${workshop.workshop_id}-${shiftTotal.shift_id}`"
                    :class="['live-summary-cell', { 'is-disabled': !shiftTotal.is_applicable }]"
                  >
                    <strong>{{ shiftTotal.is_applicable ? formatWeight(shiftTotal.total_output) : '—' }}</strong>
                    <span>{{ shiftTotal.is_applicable ? `投 ${formatWeight(shiftTotal.total_input)}` : '不适用' }}</span>
                    <span>{{ shiftTotal.is_applicable ? `兼容率 ${formatPercent(shiftTotal.yield_rate)}` : '—' }}</span>
                  </div>
                  <div class="live-board__total-cell live-board__total-cell--accent">
                    <strong>投 {{ formatWeight(workshop.workshop_total?.input) }}</strong>
                    <span>产 {{ formatWeight(workshop.workshop_total?.output) }}</span>
                    <span>废 {{ formatWeight(workshop.workshop_total?.scrap) }}</span>
                    <span>正式率 {{ formatPercent(workshop.workshop_total?.yield_rate) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </el-collapse-item>
      </el-collapse>
    </div>

    <el-card class="panel live-dashboard__bottom">
      <template #header>
        <div class="live-dashboard__table-header">
          <div>
            <strong>全厂日汇总</strong>
            <p>自动汇总，不需要手工加总。</p>
          </div>
          <el-button
            class="live-dashboard__export-button"
            type="primary"
            :icon="Download"
            circle
            aria-label="导出电子表格"
            title="导出电子表格"
            @click="exportSummary"
          />
        </div>
      </template>

      <el-table :data="factorySummaryRows" stripe>
        <el-table-column prop="workshop_name" label="车间" min-width="180" />
        <el-table-column prop="machine_count" label="机台数" width="100" />
        <el-table-column prop="submission_progress" label="提交进度" min-width="120" />
        <el-table-column label="投入" min-width="120">
          <template #default="{ row }">{{ formatWeight(row.input) }}</template>
        </el-table-column>
        <el-table-column label="产出" min-width="120">
          <template #default="{ row }">{{ formatWeight(row.output) }}</template>
        </el-table-column>
        <el-table-column label="废料" min-width="120">
          <template #default="{ row }">{{ formatWeight(row.scrap) }}</template>
        </el-table-column>
        <el-table-column label="正式成材率" min-width="120">
          <template #default="{ row }">
            <span :class="yieldToneClass(row.yield_rate)">{{ formatPercent(row.yield_rate) }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-drawer v-model="drawerVisible" size="560px" :title="drawerTitle">
      <div class="live-drawer__meta" v-if="activeCell">
        <span>{{ activeCell.workshop_name }}</span>
        <span>{{ activeCell.machine_name }}</span>
        <span>{{ activeCell.shift_name }}</span>
        <span>{{ targetDate }}</span>
      </div>

      <el-skeleton v-if="drawerLoading" :rows="8" animated />
      <el-empty v-else-if="!drawerData.items.length" description="当前机台班次暂无卷数据" />
      <el-table v-else :data="drawerData.items" stripe>
        <el-table-column prop="tracking_card_no" label="随行卡号" min-width="150" />
        <el-table-column prop="entry_status" label="状态" width="100">
          <template #default="{ row }">{{ formatEntryStatus(row.entry_status) }}</template>
        </el-table-column>
        <el-table-column prop="entry_type" label="节奏" width="110">
          <template #default="{ row }">{{ formatEntryType(row.entry_type) }}</template>
        </el-table-column>
        <el-table-column label="投入" min-width="110">
          <template #default="{ row }">{{ formatWeight(row.input_weight) }}</template>
        </el-table-column>
        <el-table-column label="产出" min-width="110">
          <template #default="{ row }">{{ formatWeight(row.output_weight) }}</template>
        </el-table-column>
        <el-table-column label="废料" min-width="110">
          <template #default="{ row }">{{ formatWeight(row.scrap_weight) }}</template>
        </el-table-column>
        <el-table-column label="兼容成材率" min-width="110">
          <template #default="{ row }">
            <span :class="yieldToneClass(row.yield_rate)">{{ formatPercent(row.yield_rate) }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-drawer>
  </ReferencePageFrame>
</template>

<script setup>
import { Download, RefreshRight } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { fetchLiveAggregation, fetchLiveCellDetail } from '../../api/realtime'
import ReferencePageFrame from '../../components/reference/ReferencePageFrame.vue'
import { useRealtimeStream } from '../../composables/useRealtimeStream'
import { useAuthStore } from '../../stores/auth'
import {
  numberValue, formatWeight, formatPercent, yieldToneClass,
  submissionSymbol, formatAttendance, formatEntryStatus, formatEntryType
} from '../../utils/liveDashboardFormatters'
import {
  buildCommandCenterSummary,
  sortWorkshopsForCommandCenter,
  statusTextForCell,
  statusToneForCell
} from '../../utils/managementCommandCenter'

const authStore = useAuthStore()

const targetDate = ref(dayjs().format('YYYY-MM-DD'))
const loading = ref(false)
const drawerVisible = ref(false)
const drawerLoading = ref(false)
const activePanels = ref([])
const activeCell = ref(null)
const aggregation = ref(createEmptyAggregation(targetDate.value))
const drawerData = ref({ items: [] })
const updatedKeys = ref({})
const lastLoadedAt = ref('')

let reloadTimer = null
const handledEventIds = new Set()

function createEmptyAggregation(businessDate) {
  return {
    business_date: businessDate,
    overall_progress: {
      submitted_cells: 0,
      total_cells: 0
    },
    workshops: [],
    yield_matrix_lane: {},
    mes_sync_status: {},
    data_source: 'work_order_runtime',
    factory_total: {
      input: 0,
      output: 0,
      scrap: 0,
      yield_rate: null
    }
  }
}

function createSummaryRow(workshop) {
  return {
    workshop_name: workshop.workshop_name,
    machine_count: workshop.machines.length,
    submission_progress: buildWorkshopProgress(workshop),
    input: workshop.workshop_total?.input ?? 0,
    output: workshop.workshop_total?.output ?? 0,
    scrap: workshop.workshop_total?.scrap ?? 0,
    yield_rate: workshop.workshop_total?.yield_rate ?? null
  }
}

function buildWorkshopProgress(workshop) {
  let submitted = 0
  let total = 0
  workshop.machines.forEach((machine) => {
    machine.shifts.forEach((shift) => {
      if (!shift.is_applicable) return
      total += 1
      if (numberValue(shift.submitted_count) > 0) {
        submitted += 1
      }
    })
  })
  return `${submitted}/${total}`
}

const factorySummaryRows = computed(() => {
  const rows = sortedWorkshops.value.map(createSummaryRow)
  rows.push({
    workshop_name: '全厂汇总',
    machine_count: rows.reduce((sum, item) => sum + numberValue(item.machine_count), 0),
    submission_progress: overallProgressText.value,
    input: aggregation.value.factory_total?.input ?? 0,
    output: aggregation.value.factory_total?.output ?? 0,
    scrap: aggregation.value.factory_total?.scrap ?? 0,
    yield_rate: aggregation.value.factory_total?.yield_rate ?? null
  })
  return rows
})

const overallProgressText = computed(() => {
  const submitted = aggregation.value.overall_progress?.submitted_cells ?? 0
  const total = aggregation.value.overall_progress?.total_cells ?? 0
  return `${submitted}/${total} 班次`
})
const commandSummary = computed(() => buildCommandCenterSummary(aggregation.value))
const sortedWorkshops = computed(() => sortWorkshopsForCommandCenter(aggregation.value.workshops || []))
const lastRefreshLabel = computed(() => (lastLoadedAt.value ? dayjs(lastLoadedAt.value).format('HH:mm:ss') : '--'))

const streamScope = computed(() => {
  if (authStore.isAdmin || authStore.isManager || authStore.role === 'statistician' || authStore.role === 'stat') {
    return 'all'
  }
  return authStore.user?.workshop_id ? String(authStore.user.workshop_id) : 'all'
})

const { status: streamStatus } = useRealtimeStream(streamScope, {
  enabled: true,
  onEvent: handleRealtimeEvent
})

const connectionTone = computed(() => {
  if (streamStatus.value === 'open') return 'good'
  if (streamStatus.value === 'connecting' || streamStatus.value === 'reconnecting') return 'warn'
  if (streamStatus.value === 'closed') return 'muted'
  return 'danger'
})

const connectionLabel = computed(() => {
  if (streamStatus.value === 'open') return '实时连接正常'
  if (streamStatus.value === 'connecting') return '正在建立连接'
  if (streamStatus.value === 'reconnecting') return '正在重连'
  if (streamStatus.value === 'closed') return '连接已关闭'
  return '连接异常'
})

const drawerTitle = computed(() => {
  if (!activeCell.value) return '批次详情'
  return `${activeCell.value.machine_name} ${activeCell.value.shift_name} 批次详情`
})

function boardGridStyle(workshop) {
  const shiftCount = Math.max(getWorkshopShifts(workshop).length, 1)
  return {
    gridTemplateColumns: `116px repeat(${shiftCount}, minmax(150px, 1fr)) minmax(220px, 260px)`
  }
}

function getWorkshopShifts(workshop) {
  return workshop?.machines?.[0]?.shifts || []
}

function getAttendanceShifts(workshop) {
  return getWorkshopShifts(workshop)
}

function getWorkshopShiftTotals(workshop) {
  return workshop?.shift_totals || []
}

function cellKey(workshopId, machineId, shiftId) {
  return `${workshopId}-${machineId}-${shiftId}`
}

function attendanceKey(workshopId, shiftId) {
  return `attendance-${workshopId}-${shiftId}`
}

function isUpdated(key) {
  return Boolean(updatedKeys.value[key])
}

function markUpdated(key) {
  updatedKeys.value = {
    ...updatedKeys.value,
    [key]: Date.now()
  }
  window.setTimeout(() => {
    const next = { ...updatedKeys.value }
    delete next[key]
    updatedKeys.value = next
  }, 1800)
}

function clearHandledEvents() {
  if (handledEventIds.size < 500) return
  handledEventIds.clear()
}

async function loadAggregation({ silent = false } = {}) {
  if (!silent) {
    loading.value = true
  }

  try {
    const data = await fetchLiveAggregation({
      business_date: targetDate.value,
      workshop_id: streamScope.value === 'all' ? undefined : Number(streamScope.value)
    })
    aggregation.value = data
    lastLoadedAt.value = new Date().toISOString()
    activePanels.value = sortWorkshopsForCommandCenter(data.workshops || []).map((item) => String(item.workshop_id))
    if (drawerVisible.value && activeCell.value) {
      await loadDrawer(activeCell.value, { preserveOpen: true })
    }
  } finally {
    loading.value = false
  }
}

async function loadDashboardSurface() {
  await loadAggregation()
}

function scheduleReload() {
  if (reloadTimer) return
  reloadTimer = window.setTimeout(async () => {
    reloadTimer = null
    await loadAggregation({ silent: true })
  }, 400)
}

function findCell(payload) {
  const workshop = aggregation.value.workshops.find((item) => item.workshop_id === payload.workshop_id)
  if (!workshop) return null
  const machine = workshop.machines.find((item) => item.machine_id === payload.machine_id)
  if (!machine) return null
  const shift = machine.shifts.find((item) => item.shift_id === payload.shift_id)
  if (!shift) return null
  return { workshop, machine, shift }
}

function syncDrawerWithSubmission(payload) {
  if (!drawerVisible.value || !activeCell.value) return
  if (
    activeCell.value.workshop_id !== payload.workshop_id ||
    activeCell.value.machine_id !== payload.machine_id ||
    activeCell.value.shift_id !== payload.shift_id
  ) {
    return
  }

  drawerData.value.items = [
    {
      tracking_card_no: payload.tracking_card_no,
      entry_id: payload.entry_id,
      work_order_id: payload.work_order_id,
      entry_status: payload.entry_status,
      entry_type: payload.entry_type,
      input_weight: payload.input_weight,
      output_weight: payload.output_weight,
      scrap_weight: payload.scrap_weight,
      yield_rate: payload.yield_rate,
      machine_id: payload.machine_id,
      shift_id: payload.shift_id
    },
    ...drawerData.value.items.filter((item) => item.entry_id !== payload.entry_id)
  ]
}

function syncDrawerWithVerification(payload) {
  if (!drawerVisible.value) return
  const match = drawerData.value.items.find((item) => item.entry_id === payload.entry_id)
  if (!match) return
  match.entry_status = payload.entry_status || match.entry_status
  match.input_weight = payload.input_weight ?? match.input_weight
  match.output_weight = payload.output_weight ?? match.output_weight
  match.scrap_weight = payload.scrap_weight ?? match.scrap_weight
  match.yield_rate = payload.yield_rate ?? match.yield_rate
}

function applyEntrySubmitted(payload) {
  if (payload.business_date && payload.business_date !== targetDate.value) return
  const match = findCell(payload)
  if (!match) {
    scheduleReload()
    return
  }

  syncDrawerWithSubmission(payload)
  markUpdated(cellKey(payload.workshop_id, payload.machine_id, payload.shift_id))
  scheduleReload()
}

function applyAttendanceConfirmed(payload) {
  if (payload.business_date && payload.business_date !== targetDate.value) return
  const workshop = aggregation.value.workshops.find((item) => item.workshop_id === payload.workshop_id)
  if (!workshop) {
    scheduleReload()
    return
  }

  workshop.machines.forEach((machine) => {
    const shift = machine.shifts.find((item) => item.shift_id === payload.shift_id)
    if (!shift) return
    shift.attendance_exception_count = numberValue(payload.exception_count)
    shift.attendance_status = numberValue(payload.exception_count) > 0 ? 'pending' : 'confirmed'
    delete shift.status_tone
    delete shift.status_text
    shift.status_tone = statusToneForCell(shift)
    shift.status_text = statusTextForCell(shift)
  })
  markUpdated(attendanceKey(payload.workshop_id, payload.shift_id))
}

function handleRealtimeEvent(type, payload, meta = {}) {
  if (meta.eventId && handledEventIds.has(meta.eventId)) {
    return
  }
  if (meta.eventId) {
    handledEventIds.add(meta.eventId)
    clearHandledEvents()
  }

  if (type === 'entry_submitted') {
    applyEntrySubmitted(payload)
    return
  }
  if (type === 'entry_verified') {
    syncDrawerWithVerification(payload)
    if (payload.workshop_id && payload.machine_id && payload.shift_id) {
      markUpdated(cellKey(payload.workshop_id, payload.machine_id, payload.shift_id))
    }
    scheduleReload()
    return
  }
  if (type === 'attendance_confirmed') {
    applyAttendanceConfirmed(payload)
  }
}

async function loadDrawer(cell, options = {}) {
  const preserveOpen = options.preserveOpen === true
  activeCell.value = cell
  drawerLoading.value = true
  if (!preserveOpen) {
    drawerVisible.value = true
  }

  try {
    drawerData.value = await fetchLiveCellDetail({
      business_date: targetDate.value,
      workshop_id: cell.workshop_id,
      machine_id: cell.machine_id,
      shift_id: cell.shift_id
    })
  } finally {
    drawerLoading.value = false
  }
}

async function openDrawer(workshop, machine, shift) {
  await loadDrawer({
    workshop_id: workshop.workshop_id,
    workshop_name: workshop.workshop_name,
    machine_id: machine.machine_id,
    machine_name: machine.machine_name,
    shift_id: shift.shift_id,
    shift_name: shift.shift_name
  })
}

function exportSummary() {
  const header = ['车间', '机台数', '提交进度', '投入', '产出', '废料', '成材率']
  const rows = factorySummaryRows.value.map((item) => [
    item.workshop_name,
    item.machine_count,
    item.submission_progress,
    formatWeight(item.input),
    formatWeight(item.output),
    formatWeight(item.scrap),
    formatPercent(item.yield_rate)
  ])

  const csv = [header, ...rows]
    .map((row) =>
      row
        .map((cell) => {
          const text = String(cell ?? '')
          return `"${text.replaceAll('"', '""')}"`
        })
        .join(',')
    )
    .join('\n')

  const blob = new Blob([`\uFEFF${csv}`], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = `live-dashboard-${targetDate.value}.csv`
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

watch(targetDate, async () => {
  drawerVisible.value = false
  activeCell.value = null
  drawerData.value = { items: [] }
  await loadDashboardSurface()
})

onMounted(async () => {
  await loadDashboardSurface()
})

onBeforeUnmount(() => {
  if (reloadTimer) {
    window.clearTimeout(reloadTimer)
    reloadTimer = null
  }
})
</script>

<style scoped>
.live-dashboard {
  --command-ink: oklch(18% 0.028 250);
  --command-rail: oklch(24% 0.026 248);
  --command-metal: oklch(96% 0.011 104);
  --command-green: oklch(53% 0.13 158);
  --command-amber: oklch(62% 0.12 75);
  --command-red: oklch(55% 0.15 28);
}

.live-dashboard :deep(.reference-page__body) {
  min-width: 0;
}

.live-dashboard__connection,
.live-dashboard__progress-pill {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  min-height: 36px;
  padding: 0 12px;
  border-radius: var(--xt-radius-lg);
  background: var(--xt-bg-panel-soft);
  color: var(--xt-text-secondary);
  font-size: 13px;
  font-weight: 700;
  box-shadow: var(--xt-shadow-xs);
}

.live-dashboard__connection-dot {
  width: 8px;
  height: 8px;
  border-radius: var(--xt-radius-pill);
  background: var(--xt-text-muted);
}

.live-dashboard__connection-dot.is-good {
  background: var(--command-green);
}

.live-dashboard__connection-dot.is-warn {
  background: var(--command-amber);
}

.live-dashboard__connection-dot.is-danger {
  background: var(--command-red);
}

.command-status-strip {
  display: grid;
  grid-template-columns: minmax(220px, 1.4fr) repeat(5, minmax(150px, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.command-status-card {
  position: relative;
  display: grid;
  gap: 5px;
  min-height: 104px;
  padding: 16px;
  overflow: hidden;
  border-radius: var(--xt-radius-xl);
  background: linear-gradient(135deg, var(--xt-bg-panel-strong), var(--command-metal));
  box-shadow: var(--xt-shadow-sm);
}

.command-status-card::after {
  content: '';
  position: absolute;
  right: 14px;
  bottom: 12px;
  width: 32px;
  height: 3px;
  border-radius: var(--xt-radius-pill);
  background: var(--xt-border-strong);
  opacity: 0.55;
}

.command-status-card span {
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-weight: 800;
}

.command-status-card strong {
  color: var(--xt-text);
  font-family: var(--xt-font-number);
  font-size: 30px;
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  letter-spacing: -0.018em;
  line-height: 1;
}

.command-status-card em {
  color: var(--xt-text-muted);
  font-size: 12px;
  font-style: normal;
  font-weight: 700;
}

.command-status-card--output {
  background: linear-gradient(135deg, var(--command-ink), var(--command-rail));
}

.command-status-card--output span,
.command-status-card--output em {
  color: rgba(255, 255, 255, 0.66);
}

.command-status-card--output strong {
  color: rgba(255, 255, 255, 0.92);
}

.command-status-card.is-danger::after {
  background: var(--command-red);
  opacity: 1;
}

.command-status-card.is-warning::after {
  background: var(--command-amber);
  opacity: 1;
}

.live-dashboard__workshops {
  display: grid;
  gap: 12px;
  min-width: 0;
}

.live-dashboard__collapse {
  min-width: 0;
  border: 0;
}

.live-dashboard__collapse :deep(.el-collapse-item) {
  margin-bottom: 12px;
  border-radius: var(--xt-radius-xl);
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-sm);
  overflow: hidden;
}

.live-dashboard__collapse :deep(.el-collapse-item__header) {
  min-height: 58px;
  padding: 0 16px;
  border-bottom: 1px solid var(--xt-border-light);
  background: var(--xt-bg-panel-strong);
}

.live-dashboard__collapse :deep(.el-collapse-item__wrap) {
  min-width: 0;
  border-bottom: 0;
}

.live-dashboard__collapse :deep(.el-collapse-item__content) {
  min-width: 0;
}

.live-workshop__title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  min-width: 0;
  gap: 16px;
}

.live-workshop__title strong {
  display: block;
  color: var(--xt-text);
  font-size: 16px;
  font-weight: 900;
}

.live-workshop__title span,
.live-workshop__title-meta span {
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-weight: 700;
}

.live-workshop__title-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  font-variant-numeric: tabular-nums;
}

.live-workshop__board {
  min-width: 0;
  overflow: hidden;
}

.live-board__scroller {
  max-width: 100%;
  min-width: 0;
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  padding: 14px;
}

.live-board__table {
  display: grid;
  min-width: 880px;
  gap: 1px;
  border-radius: var(--xt-radius-lg);
  background: var(--xt-border-light);
  overflow: hidden;
}

.live-board__row--grid {
  display: grid;
  grid-column: 1 / -1;
  grid-template-columns: subgrid;
}

.live-board__row--head {
  position: sticky;
  top: 0;
  z-index: 1;
}

.live-board__stub,
.live-board__head-cell,
.live-board__total-cell,
.live-summary-cell,
.live-attendance-cell,
.live-cell {
  min-height: 64px;
  padding: 10px 12px;
  background: var(--xt-bg-panel-strong);
}

.live-board__stub,
.live-board__head-cell {
  display: flex;
  align-items: center;
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-weight: 900;
}

.live-board__stub--machine {
  color: var(--xt-text);
}

.live-cell {
  display: grid;
  grid-template-columns: 22px 1fr;
  gap: 3px 8px;
  width: 100%;
  border: 0;
  text-align: left;
  cursor: pointer;
  touch-action: manipulation;
  transition-property: transform, box-shadow, background-color;
  transition-duration: var(--xt-motion-fast);
  transition-timing-function: var(--xt-ease);
}

.live-cell:active {
  transform: scale(0.98);
}

.live-cell:focus-visible {
  outline: none;
  box-shadow: var(--app-focus-ring);
}

.live-cell__symbol {
  grid-row: 1 / span 3;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  border-radius: var(--xt-radius-pill);
  color: #fff;
  font-size: 12px;
  font-weight: 900;
}

.live-cell strong {
  color: var(--xt-text);
  font-size: 14px;
  font-weight: 900;
}

.live-cell__count,
.live-cell__yield {
  font-size: 12px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.live-cell.tone-success {
  background: var(--xt-success-light);
}

.live-cell.tone-success .live-cell__symbol {
  background: var(--command-green);
}

.live-cell.tone-warning {
  background: var(--xt-warning-light);
}

.live-cell.tone-warning .live-cell__symbol {
  background: var(--command-amber);
}

.live-cell.tone-danger {
  background: var(--xt-danger-light);
}

.live-cell.tone-danger .live-cell__symbol {
  background: var(--command-red);
}

.live-cell.tone-muted,
.live-cell.is-disabled {
  background: var(--xt-bg-panel-muted);
  color: var(--xt-text-muted);
  cursor: default;
}

.live-cell.tone-muted .live-cell__symbol,
.live-cell.is-disabled .live-cell__symbol {
  background: var(--xt-text-muted);
}

.live-cell.is-updated {
  box-shadow: inset 0 0 0 2px var(--xt-primary);
}

.live-board__total-cell,
.live-summary-cell,
.live-attendance-cell {
  display: grid;
  gap: 3px;
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-variant-numeric: tabular-nums;
}

.live-board__total-cell strong,
.live-summary-cell strong {
  color: var(--xt-text);
  font-size: 14px;
  font-weight: 900;
}

.live-board__total-cell--accent {
  background: var(--xt-primary-light);
}

.live-board__total-cell--muted {
  color: var(--xt-text-muted);
}

.live-dashboard__bottom {
  min-width: 0;
  margin-top: 14px;
}

.live-dashboard__table-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  min-width: 0;
  gap: 16px;
}

.live-dashboard__table-header strong {
  font-size: 16px;
  font-weight: 900;
}

.live-dashboard__table-header p {
  margin: 4px 0 0;
  color: var(--xt-text-secondary);
  font-size: 12px;
}

.live-dashboard__export-button {
  flex: 0 0 auto;
}

.live-drawer__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}

.live-drawer__meta span {
  padding: 6px 9px;
  border-radius: var(--xt-radius-md);
  background: var(--xt-bg-panel-soft);
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-weight: 800;
}

@media (hover: hover) {
  .live-cell:not(.is-disabled):hover {
    transform: translateY(-1px);
    box-shadow: var(--xt-shadow-sm);
  }
}

@media (max-width: 1200px) {
  .command-status-strip {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 760px) {
  .command-status-strip {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .command-status-card {
    min-height: 92px;
  }

  .command-status-card strong {
    font-size: 24px;
  }

  .live-workshop__title {
    align-items: flex-start;
    flex-direction: column;
    gap: 6px;
  }

  .live-dashboard__table-header {
    align-items: flex-start;
  }
}
</style>
