<template>
  <div class="page-stack live-dashboard" data-testid="live-dashboard">
    <div class="page-header live-dashboard__header">
      <div>
        <h1>实时运营看板</h1>
        <p>按车间、机台、班次实时查看提交情况，自动汇总产出与考勤确认状态。</p>
      </div>
      <div class="header-actions live-dashboard__actions">
        <el-date-picker v-model="targetDate" type="date" value-format="YYYY-MM-DD" />
        <div class="live-dashboard__connection">
          <span :class="['live-dashboard__connection-dot', `is-${connectionTone}`]"></span>
          <span>{{ connectionLabel }}</span>
        </div>
        <div class="live-dashboard__progress-pill">
          全厂提交进度 {{ overallProgressText }}
        </div>
        <div class="live-dashboard__progress-pill">
          数据源 {{ aggregation.data_source === 'mes_projection' ? 'MES 投影' : '工单兼容口径' }}
        </div>
        <div class="live-dashboard__progress-pill">
          MES Lag {{ syncLagText }}
        </div>
        <el-button :icon="RefreshRight" @click="loadAggregation()">刷新</el-button>
      </div>
    </div>

    <el-alert
      type="info"
      :closable="false"
      class="live-dashboard__truth-note"
      title="正式口径：全厂/车间总成材率优先使用成品率矩阵；机台/班次/批次层仍显示 runtime compat 成材率。"
    />

    <div class="live-dashboard__summary">
      <div class="stat-card">
        <div class="stat-label">已提交班次</div>
        <div class="stat-value">{{ aggregation.overall_progress?.submitted_cells ?? 0 }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">全厂投入</div>
        <div class="stat-value">{{ formatWeight(aggregation.factory_total?.input) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">全厂产出</div>
        <div class="stat-value">{{ formatWeight(aggregation.factory_total?.output) }}</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">全厂正式成材率</div>
        <div :class="['stat-value', yieldToneClass(aggregation.factory_total?.yield_rate)]">
          {{ formatPercent(aggregation.factory_total?.yield_rate) }}
        </div>
      </div>
    </div>

    <div class="live-dashboard__workshops" v-loading="loading">
      <el-empty
        v-if="!loading && !aggregation.workshops.length"
        description="当前日期暂无实时卷数据"
      />

      <el-collapse v-else v-model="activePanels" class="live-dashboard__collapse">
        <el-collapse-item
          v-for="workshop in aggregation.workshops"
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
                      { 'is-disabled': !shift.is_applicable },
                      { 'is-updated': isUpdated(cellKey(workshop.workshop_id, machine.machine_id, shift.shift_id)) }
                    ]"
                    :disabled="!shift.is_applicable"
                    @click="openDrawer(workshop, machine, shift)"
                  >
                    <span class="live-cell__symbol">{{ submissionSymbol(shift.submission_status) }}</span>
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
          <el-button type="primary" plain :icon="Download" @click="exportSummary">导出电子表格</el-button>
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
  </div>
</template>

<script setup>
import { Download, RefreshRight } from '@element-plus/icons-vue'
import dayjs from 'dayjs'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import { fetchLiveAggregation, fetchLiveCellDetail } from '../../api/realtime'
import { useRealtimeStream } from '../../composables/useRealtimeStream'
import { useAuthStore } from '../../stores/auth'
import { formatNumber } from '../../utils/display'

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

function numberValue(value) {
  const num = Number(value ?? 0)
  return Number.isFinite(num) ? num : 0
}

function formatWeight(value) {
  return formatNumber(value ?? 0, 2)
}

function formatPercent(value) {
  if (value === null || value === undefined || value === '') return '--'
  return `${formatNumber(value, 2)}%`
}

function yieldToneClass(value) {
  const num = Number(value)
  if (!Number.isFinite(num)) return 'is-yield-neutral'
  if (num >= 97) return 'is-yield-good'
  if (num >= 94) return 'is-yield-warn'
  return 'is-yield-danger'
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
  const rows = aggregation.value.workshops.map(createSummaryRow)
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
const syncLagText = computed(() => {
  const lag = Number(aggregation.value.mes_sync_status?.lag_seconds)
  if (!Number.isFinite(lag)) return '--'
  if (lag < 60) return `${lag.toFixed(0)}s`
  return `${(lag / 60).toFixed(1)}m`
})

const streamScope = computed(() => {
  if (authStore.isAdmin || authStore.isManager || authStore.role === 'statistician' || authStore.role === 'stat') {
    return 'all'
  }
  return authStore.user?.workshop_id ? String(authStore.user.workshop_id) : 'all'
})

const { status: streamStatus, lastEventAt } = useRealtimeStream(streamScope, {
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

function submissionSymbol(status) {
  if (status === 'not_applicable') return '—'
  if (status === 'all_submitted') return '✓'
  if (status === 'in_progress') return '⏳'
  return '○'
}

function formatAttendance(shift) {
  if (!shift.is_applicable || shift.attendance_status === 'not_applicable') return '—'
  const exceptionCount = numberValue(shift.attendance_exception_count)
  if (shift.attendance_status === 'confirmed' && exceptionCount === 0) return '✓ 已确认'
  if (exceptionCount > 0) return `⚠ ${exceptionCount} 人异常`
  if (shift.attendance_status === 'pending') return '⏳ 待确认'
  return '○ 未开始'
}

function formatEntryStatus(status) {
  if (status === 'submitted') return '已提交'
  if (status === 'verified') return '已核对'
  if (status === 'approved') return '已通过系统校验'
  if (status === 'synced') return 'MES 已同步'
  return '草稿'
}

function formatEntryType(type) {
  if (type === 'mes_projection') return 'MES 投影'
  return type === 'completed' ? '本班完工' : '接续生产'
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
    activePanels.value = data.workshops.map((item) => String(item.workshop_id))
    if (drawerVisible.value && activeCell.value) {
      await loadDrawer(activeCell.value, { preserveOpen: true })
    }
  } finally {
    loading.value = false
  }
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
  await loadAggregation()
})

onMounted(async () => {
  await loadAggregation()
})

onBeforeUnmount(() => {
  if (reloadTimer) {
    window.clearTimeout(reloadTimer)
    reloadTimer = null
  }
})
</script>
