<template>
  <section
    class="live-dashboard-page"
    data-testid="manage-live"
    data-visual-pass="stitch-image2-second-pass"
    :data-stitch-project-id="stitchSurface.stitch.projectId"
    :data-stitch-screen-id="stitchSurface.stitch.screenId"
  >
    <header class="live-dashboard-page__header">
      <div class="live-dashboard-page__title">
        <span class="live-dashboard-page__eyebrow">鑫泰铝业 数据中枢 / 生产实时</span>
        <h1>全厂实时调度墙</h1>
        <p>实时流转 / 机列矩阵 / 来源核验</p>
      </div>
      <div class="live-dashboard-page__actions">
        <span class="live-dashboard-page__chip">{{ targetDate }}</span>
        <span class="live-dashboard-page__connection" :class="`is-${connectionTone}`">
          <i></i>
          {{ connectionLabel }}
        </span>
        <span class="live-dashboard-page__chip">LAST {{ lastUpdateLabel || '--:--:--' }}</span>
        <el-date-picker v-model="targetDate" type="date" value-format="YYYY-MM-DD" @change="loadDashboardSurface" />
        <button class="live-dashboard-page__refresh" type="button" @click="loadDashboardSurface">刷新</button>
      </div>
    </header>

    <div class="xt-second-pass-source-strip" data-testid="second-pass-source-strip" aria-label="数据来源">
      <span class="xt-second-pass-source-strip__item">MES 外部数据</span>
      <span class="xt-second-pass-source-strip__item">人工填报</span>
      <span class="xt-second-pass-source-strip__item">算法数据</span>
    </div>

    <LiveMarketTicker :items="tickerItems" />
    <LiveProcessFlow :items="processFlowItems" />

    <section class="live-dashboard-page__priority" aria-label="今日优先处理">
      <header>
        <span>今日优先处理</span>
        <strong>{{ priorityItems.length ? '先处理这 3 件事' : '暂无紧急事项' }}</strong>
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
  if (dashboardLoadPromise) return dashboardLoadPromise
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
      void loadDashboardSurface()
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
  position: relative;
  min-height: calc(100vh - 96px);
  display: grid;
  gap: 16px;
  padding: 18px;
  overflow: hidden;
  isolation: isolate;
  border: 1px solid rgba(0, 242, 255, 0.18);
  border-radius: 22px;
  background:
    radial-gradient(circle at 16% 0%, rgba(0, 173, 255, 0.28), transparent 28%),
    radial-gradient(circle at 82% 8%, rgba(0, 242, 255, 0.2), transparent 32%),
    linear-gradient(135deg, #06101f 0%, #071b31 48%, #03101f 100%);
  color: rgba(225, 253, 255, 0.94);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.08),
    0 12px 28px rgba(0, 29, 68, 0.28);
}

.live-dashboard-page::before,
.live-dashboard-page::after {
  position: absolute;
  inset: 0;
  pointer-events: none;
  content: "";
}

.live-dashboard-page::before {
  z-index: -2;
  opacity: 0.34;
  background:
    linear-gradient(rgba(0, 242, 255, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 242, 255, 0.08) 1px, transparent 1px);
  background-size: 44px 44px;
  mask-image: linear-gradient(180deg, rgba(0, 0, 0, 0.95), transparent 92%);
}

.live-dashboard-page::after {
  z-index: -1;
  background:
    linear-gradient(120deg, transparent 0%, rgba(0, 242, 255, 0.12) 44%, transparent 62%),
    repeating-linear-gradient(180deg, rgba(225, 253, 255, 0.035) 0 1px, transparent 1px 7px);
  opacity: 0.42;
}

.live-dashboard-page__header,
.live-dashboard-page__priority,
.live-dashboard-page__grid,
.live-market-ticker,
.live-metric-compare,
.live-data-state-panel {
  position: relative;
  z-index: 1;
}

.live-dashboard-page__priority {
  position: relative;
  overflow: hidden;
  display: grid;
  grid-template-columns: minmax(180px, 240px) minmax(0, 1fr);
  gap: 12px;
  align-items: stretch;
  border: 1px solid rgba(255, 171, 0, 0.26);
  border-radius: 18px;
  padding: 14px;
  background:
    linear-gradient(105deg, rgba(255, 171, 0, 0.14), transparent 42%),
    rgba(3, 16, 31, 0.84);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.07);
}

.live-dashboard-page__priority::before {
  position: absolute;
  top: 0;
  right: 14px;
  left: 14px;
  height: 1px;
  pointer-events: none;
  content: "";
  background: linear-gradient(90deg, transparent, rgba(255, 171, 0, 0.14), transparent);
}

.live-dashboard-page__priority header,
.live-dashboard-page__priority-list,
.live-dashboard-page__priority p {
  position: relative;
  z-index: 1;
}

.live-dashboard-page__priority header {
  display: grid;
  align-content: center;
  gap: 5px;
}

.live-dashboard-page__priority header span {
  color: rgba(255, 212, 128, 0.78);
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.14em;
}

.live-dashboard-page__priority header strong {
  color: rgba(255, 242, 210, 0.94);
  font-family: var(--xt-font-display, "Hanken Grotesk", sans-serif);
  font-size: 22px;
  letter-spacing: -0.04em;
}

.live-dashboard-page__priority-list {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.live-dashboard-page__priority-list article {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr);
  gap: 10px;
  align-items: center;
  min-height: 78px;
  border: 1px solid rgba(255, 171, 0, 0.18);
  border-radius: 14px;
  padding: 10px;
  background: rgba(2, 16, 31, 0.78);
}

.live-dashboard-page__priority-list article.is-danger {
  border-color: rgba(255, 93, 77, 0.42);
}

.live-dashboard-page__priority-list b {
  display: grid;
  width: 34px;
  height: 34px;
  place-items: center;
  border-radius: 50%;
  background: rgba(255, 171, 0, 0.16);
  color: #ffd480;
  font-family: var(--xt-font-mono, "JetBrains Mono", monospace);
}

.live-dashboard-page__priority-list article.is-danger b {
  background: rgba(255, 93, 77, 0.18);
  color: #ff8b7f;
}

.live-dashboard-page__priority-list span,
.live-dashboard-page__priority-list strong {
  display: block;
}

.live-dashboard-page__priority-list span {
  color: rgba(185, 223, 235, 0.62);
  font-size: 12px;
}

.live-dashboard-page__priority-list strong {
  margin-top: 4px;
  color: rgba(225, 253, 255, 0.9);
  font-size: 13px;
  line-height: 1.35;
}

.live-dashboard-page__priority p {
  margin: 0;
  align-self: center;
  color: rgba(185, 223, 235, 0.72);
}

.live-dashboard-page__header {
  display: grid;
  grid-template-columns: minmax(280px, 1fr) auto;
  gap: 18px;
  align-items: center;
  border: 1px solid rgba(0, 242, 255, 0.2);
  border-radius: 18px;
  padding: 16px;
  background:
    linear-gradient(90deg, rgba(5, 22, 43, 0.88), rgba(8, 43, 74, 0.66)),
    linear-gradient(135deg, rgba(255, 255, 255, 0.06), transparent 36%);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.08),
    0 10px 24px rgba(0, 29, 68, 0.2);
}

.live-dashboard-page__title {
  min-width: 0;
}

.live-dashboard-page__eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: rgba(116, 245, 255, 0.82);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.live-dashboard-page__eyebrow::before {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #00f2ff;
  box-shadow: 0 0 0 4px rgba(0, 242, 255, 0.18);
  content: "";
}

.live-dashboard-page__header h1 {
  margin: 6px 0 0;
  font-family: var(--xt-font-display, "Hanken Grotesk", sans-serif);
  font-size: clamp(28px, 3vw, 44px);
  line-height: 0.96;
  letter-spacing: -0.05em;
  white-space: nowrap;
}

.live-dashboard-page__title p {
  margin: 8px 0 0;
  color: rgba(185, 223, 235, 0.62);
  font-family: var(--xt-font-mono, "JetBrains Mono", monospace);
  font-size: 11px;
  letter-spacing: 0.16em;
}

.live-dashboard-page__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 9px;
  align-items: center;
}

.live-dashboard-page__chip,
.live-dashboard-page__connection,
.live-dashboard-page__refresh {
  min-height: 34px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  border: 1px solid rgba(0, 242, 255, 0.22);
  border-radius: 6px;
  background: rgba(1, 16, 31, 0.72);
  color: rgba(225, 253, 255, 0.88);
  font-family: var(--xt-font-mono, "JetBrains Mono", monospace);
  font-size: 12px;
  letter-spacing: 0.04em;
}

.live-dashboard-page__chip,
.live-dashboard-page__connection {
  padding: 7px 11px;
}

.live-dashboard-page__connection i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentcolor;
  box-shadow: 0 0 0 3px color-mix(in srgb, currentcolor 22%, transparent);
}

.live-dashboard-page__connection.is-success { color: #00f2ff; }
.live-dashboard-page__connection.is-warning { color: #ffab00; }
.live-dashboard-page__connection.is-danger { color: #ff5d4d; }

.live-dashboard-page__refresh {
  position: relative;
  overflow: hidden;
  padding: 0 14px;
  cursor: pointer;
  transition: border-color 160ms ease, box-shadow 160ms ease, transform 160ms ease;
}

.live-dashboard-page__refresh::before {
  position: absolute;
  inset: 0;
  background: linear-gradient(110deg, transparent, rgba(0, 242, 255, 0.24), transparent);
  transform: translateX(-115%);
  content: "";
}

.live-dashboard-page__refresh:hover {
  border-color: rgba(0, 242, 255, 0.68);
  box-shadow: 0 6px 16px rgba(0, 29, 68, 0.18);
  transform: translateY(-1px);
}

.live-dashboard-page :deep(.el-date-editor) {
  --el-date-editor-width: 150px;
}

.live-dashboard-page :deep(.el-input__wrapper) {
  min-height: 34px;
  border-radius: 6px;
  background: rgba(1, 16, 31, 0.74);
  box-shadow:
    inset 0 -1px 0 rgba(0, 242, 255, 0.36),
    inset 0 0 0 1px rgba(0, 242, 255, 0.18);
}

.live-dashboard-page :deep(.el-input__inner) {
  color: rgba(225, 253, 255, 0.92);
  font-family: var(--xt-font-mono, "JetBrains Mono", monospace);
}

.live-dashboard-page__grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 340px;
  gap: 14px;
  align-items: stretch;
}

.live-dashboard-page__bottom-status {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  border: 1px solid rgba(0, 242, 255, 0.2);
  border-radius: 16px;
  padding: 12px;
  background:
    linear-gradient(90deg, rgba(0, 242, 255, 0.1), transparent 46%),
    rgba(1, 16, 31, 0.78);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.07);
}

.live-dashboard-page__status-pill {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 32px;
  padding: 6px 11px;
  border: 1px solid rgba(0, 242, 255, 0.18);
  border-radius: 999px;
  background: rgba(3, 16, 31, 0.72);
  color: rgba(225, 253, 255, 0.72);
  font-size: 12px;
  font-weight: 850;
}

.live-dashboard-page__status-pill i {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentcolor;
  box-shadow: 0 0 0 3px color-mix(in srgb, currentcolor 20%, transparent);
}

.live-dashboard-page__status-pill b {
  color: rgba(185, 223, 235, 0.66);
}

.live-dashboard-page__status-pill strong {
  color: rgba(225, 253, 255, 0.94);
  font-family: var(--xt-font-mono, "JetBrains Mono", monospace);
}

.live-dashboard-page__status-pill.tone-success { color: #00f2ff; }
.live-dashboard-page__status-pill.tone-warning { color: #ffab00; }
.live-dashboard-page__status-pill.tone-danger { color: #ff5d4d; }

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
}

@media (max-width: 720px) {
  .live-dashboard-page {
    padding: 12px;
    border-radius: 16px;
  }

  .live-dashboard-page__header {
    padding: 13px;
  }

  .live-dashboard-page__header h1 {
    white-space: normal;
  }
}

@media (prefers-reduced-motion: reduce) {
  .live-dashboard-page__refresh {
    transition: none;
  }
}
</style>
