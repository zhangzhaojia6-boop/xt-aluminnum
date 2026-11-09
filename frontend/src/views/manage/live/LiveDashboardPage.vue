<template>
  <section
    class="live-dashboard-page"
    data-testid="manage-live"
    data-visual-pass="stitch-image2-second-pass"
    :data-stitch-project-id="stitchSurface.stitch.projectId"
    :data-stitch-screen-id="stitchSurface.stitch.screenId"
  >
    <header class="live-dashboard-page__header" aria-label="实时流转 / 机列矩阵 / 来源核验">
      <h1>全厂实时调度墙</h1>
      <div class="live-dashboard-page__actions">
        <span class="live-dashboard-page__connection" :class="`is-${connectionTone}`">
          <i></i>
          {{ connectionLabel }}
        </span>
        <span class="live-dashboard-page__chip">更新 {{ lastUpdateLabel || '--:--:--' }}</span>
        <el-date-picker v-model="targetDate" type="date" value-format="YYYY-MM-DD" @change="loadDashboardSurface" />
        <button class="live-dashboard-page__refresh" type="button" @click="loadDashboardSurface">刷新</button>
      </div>
    </header>

    <LiveMarketTicker :items="tickerItems" />
    <LiveProcessFlow :items="processFlowItems" />

    <section class="live-dashboard-page__priority" aria-label="今日优先处理">
      <header>
        <strong>{{ priorityItems.length ? `先处理这 ${priorityItems.length} 件事` : '暂无紧急事项' }}</strong>
      </header>
      <div v-if="priorityItems.length" class="live-dashboard-page__priority-list">
        <article v-for="item in priorityItems" :key="`${item.rank}-${item.title}-${item.text}`" :class="`is-${item.tone}`">
          <b>{{ item.rank }}</b>
          <div>
            <span>{{ item.title }}</span>
            <strong>{{ item.text }}</strong>
          </div>
        </article>
      </div>
      <p v-else>实时连接与核心口径当前未发现高优先级异常。</p>
    </section>

    <main class="live-dashboard-page__grid">
      <LiveMachineMatrix :matrix="machineMatrix" :loading="loading" @select="openMachine" />
      <LiveEventRail :events="eventItems" :stream-status="streamStatus" :connection-text="connectionLabel" :last-event-at="lastUpdateLabel" />
    </main>

    <LiveMetricCompareCard :items="compareItems" />
    <LiveDataStatePanel :states="dataStates" />

    <footer class="live-dashboard-page__bottom-status" data-testid="stitch-bottom-status" aria-label="系统状态">
      <span
        v-for="item in bottomStatusItems"
        :key="item.key"
        class="live-dashboard-page__status-pill"
        :class="`tone-${item.tone}`"
      >
        <i aria-hidden="true" />
        <b>{{ item.label }}</b>
        <strong>{{ item.value }}</strong>
      </span>
    </footer>

    <LiveMachineDrawer
      :open="drawerOpen"
      :machine="activeMachine"
      :detail-rows="detailRows"
      :detail-loading="detailLoading"
      :detail-error="detailError"
      @close="drawerOpen = false"
    />
  </section>
</template>

<script setup>
import dayjs from 'dayjs'
import { computed, onMounted, onUnmounted, ref } from 'vue'

import { fetchLiveActiveDate, fetchLiveAggregation, fetchLiveCellDetail, fetchLiveFillDetails } from '../../../api/realtime'
import { useRealtimeStream } from '../../../composables/useRealtimeStream'
import { useAuthStore } from '../../../stores/auth'
import { inferBusinessDate } from '../../../utils/shiftClock'
import LiveDataStatePanel from './LiveDataStatePanel.vue'
import LiveEventRail from './LiveEventRail.vue'
import LiveMachineDrawer from './LiveMachineDrawer.vue'
import LiveMachineMatrix from './LiveMachineMatrix.vue'
import LiveMarketTicker from './LiveMarketTicker.vue'
import LiveMetricCompareCard from './LiveMetricCompareCard.vue'
import LiveProcessFlow from './LiveProcessFlow.vue'
import { buildLiveStitchSurface } from '../../../utils/stitchManageSurface'
import {
  mergeRealtimeEventPatch,
  shouldReloadForRealtimeEvent,
} from '../../../utils/liveDashboardPhase2'

const authStore = useAuthStore()
const targetDate = ref(inferBusinessDate())
const loading = ref(true)
const loadError = ref('')
const aggregation = ref({})
const fillDetails = ref({ items: [] })
const drawerOpen = ref(false)
const activeMachine = ref(null)
const detailRows = ref([])
const detailLoading = ref(false)
const detailError = ref('')
const latestRealtimeEvent = ref(null)
const lastSnapshotAt = ref('')
let snapshotPollTimer = null
let realtimeReloadTimer = null
let dashboardLoadPromise = null
const SNAPSHOT_POLL_MS = 30000
const REALTIME_RELOAD_DEBOUNCE_MS = 5000

const streamScope = computed(() => {
  if (authStore.isAdmin || authStore.isManager || authStore.role === 'statistician' || authStore.role === 'stat') {
    return 'all'
  }
  return authStore.user?.workshop_id ? String(authStore.user.workshop_id) : 'all'
})

const { status: streamStatus, lastEventAt, reconnectCount } = useRealtimeStream(streamScope, {
  enabled: true,
  connectionTimeoutMs: 10000,
  onEvent: handleRealtimeEvent,
})

const stitchSurface = computed(() => buildLiveStitchSurface({
  targetDate: targetDate.value,
  streamStatus: streamStatus.value,
  loadError: loadError.value,
  aggregation: aggregation.value,
}))
const tickerItems = computed(() => stitchSurface.value.marketTicker)
const processFlowItems = computed(() => stitchSurface.value.processFlow)
const machineMatrix = computed(() => stitchSurface.value.machineMatrix)
const compareItems = computed(() => stitchSurface.value.realtimeKpiStrip)
const eventItems = computed(() => stitchSurface.value.eventRail)
const priorityItems = computed(() => stitchSurface.value.priorityItems)
const bottomStatusItems = computed(() => stitchSurface.value.bottomStatus)
const hasSnapshotPayload = computed(() => Boolean(
  lastSnapshotAt.value
  || aggregation.value?.business_date
  || (Array.isArray(aggregation.value?.workshops) && aggregation.value.workshops.length)
))

const connectionTone = computed(() => {
  if (streamStatus.value === 'open') return 'success'
  if (hasSnapshotPayload.value) return 'warning'
  if (streamStatus.value === 'connecting' || streamStatus.value === 'reconnecting') return 'warning'
  return 'danger'
})

const connectionLabel = computed(() => {
  if (streamStatus.value === 'open') return '实时连接正常'
  if (hasSnapshotPayload.value) {
    return streamStatus.value === 'reconnecting' || reconnectCount.value > 0
      ? '快照可用 · 实时重连'
      : '快照刷新中'
  }
  if (loading.value) return '快照加载中'
  if (streamStatus.value === 'connecting') return '接口核验中 · 快照兜底'
  if (streamStatus.value === 'reconnecting') return '正在重连'
  return '连接待核'
})

const lastEventLabel = computed(() => {
  if (lastEventAt.value) return dayjs(lastEventAt.value).format('HH:mm:ss')
  if (latestRealtimeEvent.value?.time) return dayjs(latestRealtimeEvent.value.time).format('HH:mm:ss')
  return ''
})
const lastSnapshotLabel = computed(() => lastSnapshotAt.value ? dayjs(lastSnapshotAt.value).format('HH:mm:ss') : '')
const lastUpdateLabel = computed(() => lastEventLabel.value || lastSnapshotLabel.value)

const dataStates = computed(() => [
  { label: '加载', value: loading.value ? '进行中' : '完成', tone: loading.value ? 'warning' : 'success' },
  { label: '实时', value: connectionLabel.value, tone: connectionTone.value },
  { label: '机列', value: `${machineMatrix.value.machineCount} 台`, tone: machineMatrix.value.machineCount ? 'success' : 'warning' },
  { label: '待归属', value: `${machineMatrix.value.pendingMachines.length} 台`, tone: machineMatrix.value.pendingMachines.length ? 'warning' : 'success' },
  { label: '明细', value: `${(fillDetails.value.items || []).length} 条`, tone: (fillDetails.value.items || []).length ? 'success' : 'muted' },
])

async function initializeActiveBusinessDate() {
  try {
    const payload = await fetchLiveActiveDate()
    const activeDate = payload?.active_business_date || payload?.business_date || payload?.date
    return activeDate || ''
  } catch {
    return ''
  }
}

async function refreshFillDetails(businessDate = targetDate.value) {
  const details = await fetchLiveFillDetails({ business_date: businessDate, limit: 200 })
  if (businessDate !== targetDate.value) return
  fillDetails.value = details || { items: [] }
}

async function loadDashboardSurface(options = {}) {
  const force = options.force === true
  if (dashboardLoadPromise && !force) return dashboardLoadPromise
  const silent = options.silent === true
  const includeDetails = options.includeDetails !== false
  dashboardLoadPromise = (async () => {
    if (!silent) loading.value = true
    loadError.value = ''
    const businessDate = targetDate.value

    try {
      const liveData = await fetchLiveAggregation({ business_date: businessDate })
      if (businessDate !== targetDate.value) return
      aggregation.value = liveData || {}
      lastSnapshotAt.value = new Date().toISOString()
      if (includeDetails) {
        void refreshFillDetails(businessDate).catch(() => {
          if (businessDate === targetDate.value) fillDetails.value = { items: [] }
        })
      }
    } catch (error) {
      loadError.value = error?.message || '接口失败'
    } finally {
      if (!silent) loading.value = false
      dashboardLoadPromise = null
    }
  })()
  return dashboardLoadPromise
}

function scheduleRealtimeSnapshotReload(options = {}) {
  if (realtimeReloadTimer) return
  realtimeReloadTimer = window.setTimeout(() => {
    realtimeReloadTimer = null
    void loadDashboardSurface(options)
  }, REALTIME_RELOAD_DEBOUNCE_MS)
}

function handleRealtimeEvent(type, payload = {}) {
  latestRealtimeEvent.value = { type, payload, time: new Date().toISOString() }
  const patchedAggregation = mergeRealtimeEventPatch(aggregation.value, { payload, targetDate: targetDate.value })
  if (patchedAggregation) {
    aggregation.value = patchedAggregation
  }
  if (shouldReloadForRealtimeEvent({ type, payload, targetDate: targetDate.value })) {
    const streamOpen = streamStatus.value === 'open'
    if (streamOpen && patchedAggregation) return
    scheduleRealtimeSnapshotReload({ silent: streamOpen, includeDetails: !streamOpen })
  }
}

function startSnapshotPolling() {
  if (snapshotPollTimer) return
  snapshotPollTimer = window.setInterval(() => {
    if (streamStatus.value !== 'open') {
      void loadDashboardSurface({ silent: true, includeDetails: false })
    }
  }, SNAPSHOT_POLL_MS)
}

function stopSnapshotPolling() {
  if (!snapshotPollTimer) return
  window.clearInterval(snapshotPollTimer)
  snapshotPollTimer = null
}

async function openMachine(machine) {
  activeMachine.value = machine
  drawerOpen.value = true
  detailRows.value = []
  detailError.value = ''
  const firstShift = machine.shifts?.find((shift) => shift.isApplicable !== false)
  if (!firstShift?.shiftId || !machine.machineId || !machine.workshopId) return

  detailLoading.value = true
  try {
    const payload = await fetchLiveCellDetail({
      business_date: targetDate.value,
      workshop_id: machine.workshopId,
      machine_id: machine.machineId,
      shift_id: firstShift.shiftId,
    })
    detailRows.value = payload?.entries || payload?.items || []
  } catch (error) {
    detailError.value = error?.message || '明细读取失败'
    detailRows.value = []
  } finally {
    detailLoading.value = false
  }
}

onMounted(() => {
  void loadDashboardSurface()
  void initializeActiveBusinessDate().then((activeDate) => {
    if (activeDate && activeDate !== targetDate.value) {
      targetDate.value = activeDate
      void loadDashboardSurface({ force: true })
    }
  })
  startSnapshotPolling()
})

onUnmounted(() => {
  stopSnapshotPolling()
  if (realtimeReloadTimer) {
    window.clearTimeout(realtimeReloadTimer)
    realtimeReloadTimer = null
  }
})
</script>

<style scoped>
.live-dashboard-page {
  display: grid;
  gap: var(--xt-space-8);
  color: var(--xt-text);
}

.live-dashboard-page__header {
  display: grid;
  grid-template-columns: minmax(280px, 1fr) auto;
  gap: var(--xt-space-4);
  align-items: center;
}

.live-dashboard-page__header h1 {
  margin: 0;
  font-size: clamp(28px, 3vw, 44px);
  font-weight: 600;
  letter-spacing: -0.02em;
  white-space: nowrap;
}

.live-dashboard-page__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--xt-space-3);
  align-items: center;
}

.live-dashboard-page__chip,
.live-dashboard-page__connection {
  display: inline-flex;
  align-items: center;
  gap: var(--xt-space-2);
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-sm);
  font-variant-numeric: tabular-nums;
}

.live-dashboard-page__connection i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentcolor;
}

.live-dashboard-page__connection.is-success { color: var(--xt-success); }
.live-dashboard-page__connection.is-warning { color: var(--xt-warning); }
.live-dashboard-page__connection.is-danger { color: var(--xt-danger); }

.live-dashboard-page__refresh {
  min-height: 34px;
  padding: 0 var(--xt-space-3);
  border: 1px solid var(--xt-border);
  border-radius: 4px;
  background: transparent;
  color: var(--xt-text);
  font-size: var(--xt-text-sm);
  cursor: pointer;
}

.live-dashboard-page :deep(.el-date-editor) {
  --el-date-editor-width: 150px;
}

.live-dashboard-page :deep(.el-input__wrapper) {
  min-height: 34px;
  border-radius: 4px;
  background: transparent;
}

.live-dashboard-page__priority {
  display: grid;
  grid-template-columns: minmax(160px, 220px) minmax(0, 1fr);
  gap: var(--xt-space-4);
  align-items: start;
}

.live-dashboard-page__priority header strong {
  color: var(--xt-text);
  font-size: var(--xt-text-lg);
  font-weight: 600;
}

.live-dashboard-page__priority-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--xt-space-6);
}

.live-dashboard-page__priority-list article {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: var(--xt-space-3);
  padding-top: var(--xt-space-2);
  border-top: 2px solid var(--xt-warning);
}

.live-dashboard-page__priority-list article.is-danger {
  border-top-color: var(--xt-danger);
}

.live-dashboard-page__priority-list b {
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-lg);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.live-dashboard-page__priority-list span,
.live-dashboard-page__priority-list strong {
  display: block;
}

.live-dashboard-page__priority-list span {
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-xs);
}

.live-dashboard-page__priority-list strong {
  margin-top: 2px;
  color: var(--xt-text);
  font-size: var(--xt-text-sm);
  font-weight: 600;
}

.live-dashboard-page__priority p {
  margin: 0;
  color: var(--xt-text-secondary);
}

.live-dashboard-page__grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: var(--xt-space-8);
  align-items: start;
}

.live-dashboard-page__bottom-status {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--xt-space-2) var(--xt-space-6);
  padding-top: var(--xt-space-3);
  border-top: 1px solid var(--xt-border);
}

.live-dashboard-page__status-pill {
  display: inline-flex;
  align-items: center;
  gap: var(--xt-space-2);
  color: var(--xt-text);
  font-size: var(--xt-text-xs);
}

.live-dashboard-page__status-pill i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentcolor;
}

.live-dashboard-page__status-pill b {
  color: var(--xt-text-secondary);
  font-weight: 400;
}

.live-dashboard-page__status-pill strong {
  color: var(--xt-text);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

.live-dashboard-page__status-pill.tone-success { color: var(--xt-success); }
.live-dashboard-page__status-pill.tone-warning { color: var(--xt-warning); }
.live-dashboard-page__status-pill.tone-danger { color: var(--xt-danger); }

/* 子区块统一成白纸细线：去掉外框、光效和等宽大字 */
.live-dashboard-page :deep(.live-market-ticker),
.live-dashboard-page :deep(.live-process-flow),
.live-dashboard-page :deep(.live-machine-matrix),
.live-dashboard-page :deep(.live-event-rail),
.live-dashboard-page :deep(.live-metric-compare),
.live-dashboard-page :deep(.live-data-state-panel) {
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  box-shadow: none;
}

.live-dashboard-page :deep(.live-machine-matrix::before),
.live-dashboard-page :deep(.live-event-rail::before),
.live-dashboard-page :deep(.live-metric-compare::before),
.live-dashboard-page :deep(.live-market-ticker__item::before),
.live-dashboard-page :deep(.live-market-ticker__item::after),
.live-dashboard-page :deep(.live-metric-compare__grid article::before),
.live-dashboard-page :deep(.live-event-rail__list article::after) {
  display: none;
}

.live-dashboard-page :deep(.live-market-ticker) {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: var(--xt-space-6);
}

.live-dashboard-page :deep(.live-market-ticker__item) {
  min-height: 0;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  transform: none;
}

.live-dashboard-page :deep(.live-market-ticker__label) {
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-sm);
  font-weight: 400;
  letter-spacing: 0;
}

.live-dashboard-page :deep(.live-market-ticker__label i) {
  display: none;
}

.live-dashboard-page :deep(.live-market-ticker__item strong) {
  margin-top: var(--xt-space-1);
  color: var(--xt-text);
  font-family: inherit;
  font-size: clamp(22px, 2vw, 30px);
  font-weight: 600;
  letter-spacing: 0;
  line-height: 1.2;
  white-space: nowrap;
}

.live-dashboard-page :deep(.live-market-ticker__item em) {
  color: var(--xt-text-muted);
  font-size: var(--xt-text-xs);
  font-style: normal;
}

.live-dashboard-page :deep(.live-process-flow__node) {
  border: 0;
  border-top: 2px solid var(--xt-primary);
  border-radius: 0;
  padding: var(--xt-space-3) var(--xt-space-3) 0 0;
  background: transparent;
  transform: none;
}

.live-dashboard-page :deep(.live-process-flow__node.is-muted) {
  border-top-color: var(--xt-border);
}

.live-dashboard-page :deep(.live-process-flow__node.is-warning) {
  border-top-color: var(--xt-warning);
}

.live-dashboard-page :deep(.live-process-flow__node::after) {
  display: none;
}

.live-dashboard-page :deep(.live-process-flow__node b) {
  justify-self: start;
  width: auto;
  height: auto;
  border: 0;
  background: transparent;
  color: var(--xt-text-muted);
  font-family: inherit;
}

.live-dashboard-page :deep(.live-section-head span),
.live-dashboard-page :deep(.live-process-flow__head span) {
  display: none;
}

.live-dashboard-page :deep(.live-section-head strong),
.live-dashboard-page :deep(.live-process-flow__head strong) {
  font-family: inherit;
  font-size: var(--xt-text-lg);
  font-weight: 600;
  letter-spacing: 0;
}

.live-dashboard-page :deep(.live-section-head em),
.live-dashboard-page :deep(.live-process-flow__head em) {
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-xs);
  font-style: normal;
}

.live-dashboard-page :deep(.live-event-rail__list article) {
  padding: var(--xt-space-2) 0;
  border: 0;
  border-top: 1px solid var(--xt-border);
  border-radius: 0;
  background: transparent;
}

.live-dashboard-page :deep(.live-metric-compare__grid) {
  gap: var(--xt-space-6);
}

.live-dashboard-page :deep(.live-metric-compare__grid article) {
  min-height: 0;
  padding: var(--xt-space-3) 0 0;
  border: 0;
  border-top: 1px solid var(--xt-border);
  border-radius: 0;
  background: transparent;
}

.live-dashboard-page :deep(.live-metric-compare__grid article > strong) {
  font-family: inherit;
  font-size: clamp(22px, 2vw, 30px);
  font-weight: 600;
  letter-spacing: 0;
}

.live-dashboard-page :deep(.live-data-state-panel) {
  display: flex;
  flex-wrap: wrap;
  gap: var(--xt-space-2) var(--xt-space-6);
}

.live-dashboard-page :deep(.live-data-state-panel span) {
  min-height: 0;
  padding: 0;
  border: 0;
  background: transparent;
  font-size: var(--xt-text-xs);
}

@media (max-width: 1180px) {
  .live-dashboard-page__grid,
  .live-dashboard-page__priority,
  .live-dashboard-page__header {
    grid-template-columns: 1fr;
  }

  .live-dashboard-page__priority-list {
    grid-template-columns: 1fr;
  }

  .live-dashboard-page__actions {
    justify-content: flex-start;
  }

  .live-dashboard-page :deep(.live-market-ticker) {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .live-dashboard-page__header h1 {
    white-space: normal;
  }

  .live-dashboard-page :deep(.live-market-ticker) {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
