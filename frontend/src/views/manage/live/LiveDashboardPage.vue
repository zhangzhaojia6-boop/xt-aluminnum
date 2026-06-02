<template>
  <section class="live-dashboard-page" data-testid="manage-live">
    <header class="live-dashboard-page__header">
      <div class="live-dashboard-page__title">
        <span class="live-dashboard-page__eyebrow">鑫泰铝业 数据中枢 / 生产实时</span>
        <h1>全厂实时调度墙</h1>
        <p>FINAL STAGE · MACHINE MATRIX · DATA CREDIT</p>
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

    <LiveMarketTicker :items="tickerItems" />

    <main class="live-dashboard-page__grid">
      <LiveMachineMatrix :matrix="machineMatrix" :loading="loading" @select="openMachine" />
      <LiveEventRail :events="eventItems" :stream-status="streamStatus" :connection-text="connectionLabel" :last-event-at="lastUpdateLabel" />
    </main>

    <LiveMetricCompareCard :items="compareItems" />
    <LiveDataStatePanel :states="dataStates" />

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
import {
  buildLiveEventItems,
  buildLiveMachineMatrix,
  buildLiveMetricCompareItems,
  buildLiveTickerItems,
  shouldReloadForRealtimeEvent,
} from '../../../utils/liveDashboardPhase2'

const authStore = useAuthStore()
const targetDate = ref(inferBusinessDate())
const loading = ref(false)
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
const SNAPSHOT_POLL_MS = 30000

const streamScope = computed(() => {
  if (authStore.isAdmin || authStore.isManager || authStore.role === 'statistician' || authStore.role === 'stat') {
    return 'all'
  }
  return authStore.user?.workshop_id ? String(authStore.user.workshop_id) : 'all'
})

const { status: streamStatus, lastEventAt, reconnectCount } = useRealtimeStream(streamScope, {
  enabled: true,
  connectionTimeoutMs: 15000,
  onEvent: handleRealtimeEvent,
})

const tickerItems = computed(() => buildLiveTickerItems(aggregation.value))
const machineMatrix = computed(() => buildLiveMachineMatrix(aggregation.value.workshops || []))
const compareItems = computed(() => buildLiveMetricCompareItems(aggregation.value))
const eventItems = computed(() => buildLiveEventItems({
  streamStatus: streamStatus.value,
  loadError: loadError.value,
  aggregation: aggregation.value,
}))
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
  if (streamStatus.value === 'connecting') return '正在连接'
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
    if (activeDate) {
      targetDate.value = activeDate
    }
  } catch {
    targetDate.value = targetDate.value || inferBusinessDate()
  }
}

async function loadDashboardSurface(options = {}) {
  const silent = options.silent === true
  if (!silent) loading.value = true
  loadError.value = ''
  try {
    const liveData = await fetchLiveAggregation({ business_date: targetDate.value })
    aggregation.value = liveData || {}
    lastSnapshotAt.value = new Date().toISOString()
  } catch (error) {
    loadError.value = error?.message || '接口失败'
  } finally {
    if (!silent) loading.value = false
  }

  try {
    const details = await fetchLiveFillDetails({ business_date: targetDate.value, limit: 200 })
    fillDetails.value = details || { items: [] }
  } catch {
    fillDetails.value = { items: [] }
  }
}

function handleRealtimeEvent(type, payload = {}) {
  latestRealtimeEvent.value = { type, payload, time: new Date().toISOString() }
  if (shouldReloadForRealtimeEvent({ type, payload, targetDate: targetDate.value })) {
    void loadDashboardSurface()
  }
}

function startSnapshotPolling() {
  if (snapshotPollTimer) return
  snapshotPollTimer = window.setInterval(() => {
    if (streamStatus.value !== 'open') {
      void loadDashboardSurface({ silent: true })
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

onMounted(async () => {
  await initializeActiveBusinessDate()
  await loadDashboardSurface()
  startSnapshotPolling()
})

onUnmounted(() => {
  stopSnapshotPolling()
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
    0 22px 70px rgba(0, 29, 68, 0.38);
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
  transform: translateX(-42%);
  animation: livePageScan 7s linear infinite;
}

.live-dashboard-page__header,
.live-dashboard-page__grid,
.live-market-ticker,
.live-metric-compare,
.live-data-state-panel {
  position: relative;
  z-index: 1;
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
    0 0 34px rgba(0, 242, 255, 0.08);
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
  box-shadow: 0 0 18px rgba(0, 242, 255, 0.88);
  content: "";
  animation: liveLedPulse 1.6s ease-in-out infinite;
}

.live-dashboard-page__header h1 {
  margin: 6px 0 0;
  font-family: var(--xt-font-display, "Hanken Grotesk", sans-serif);
  font-size: clamp(30px, 4vw, 56px);
  line-height: 0.96;
  letter-spacing: -0.05em;
  text-shadow: 0 0 26px rgba(0, 242, 255, 0.22);
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
  box-shadow: 0 0 14px currentcolor;
  animation: liveLedPulse 1.4s ease-in-out infinite;
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
  box-shadow: 0 0 22px rgba(0, 242, 255, 0.16);
  transform: translateY(-1px);
}

.live-dashboard-page__refresh:hover::before {
  animation: liveButtonScan 0.8s ease;
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

@keyframes livePageScan {
  0% { transform: translateX(-52%); }
  100% { transform: translateX(52%); }
}

@keyframes liveButtonScan {
  0% { transform: translateX(-115%); }
  100% { transform: translateX(115%); }
}

@keyframes liveLedPulse {
  0%, 100% { opacity: 0.64; }
  50% { opacity: 1; }
}

@media (max-width: 1180px) {
  .live-dashboard-page__grid,
  .live-dashboard-page__header {
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
}

@media (prefers-reduced-motion: reduce) {
  .live-dashboard-page::after,
  .live-dashboard-page__eyebrow::before,
  .live-dashboard-page__connection i {
    animation: none;
  }

  .live-dashboard-page__refresh {
    transition: none;
  }
}
</style>
