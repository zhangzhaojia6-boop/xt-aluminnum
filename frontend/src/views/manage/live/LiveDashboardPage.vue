<template>
  <section class="live-dashboard-page">
    <header class="live-dashboard-page__header">
      <div>
        <span>鑫泰铝业 数据中枢 / 生产实时</span>
        <h1>全厂实时调度墙</h1>
      </div>
      <div class="live-dashboard-page__actions">
        <el-date-picker v-model="targetDate" type="date" value-format="YYYY-MM-DD" @change="loadDashboardSurface" />
        <span class="live-dashboard-page__connection" :class="`is-${connectionTone}`">{{ connectionLabel }}</span>
        <el-button @click="loadDashboardSurface">刷新</el-button>
      </div>
    </header>

    <LiveMarketTicker :items="tickerItems" />

    <main class="live-dashboard-page__grid">
      <LiveMachineMatrix :matrix="machineMatrix" :loading="loading" @select="openMachine" />
      <LiveEventRail :events="eventItems" :stream-status="streamStatus" :last-event-at="lastEventLabel" />
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
import { computed, onMounted, ref } from 'vue'

import { fetchLiveActiveDate, fetchLiveAggregation, fetchLiveCellDetail, fetchLiveFillDetails } from '../../../api/realtime'
import { useRealtimeStream } from '../../../composables/useRealtimeStream'
import { useAuthStore } from '../../../stores/auth'
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
const targetDate = ref(dayjs().format('YYYY-MM-DD'))
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

const streamScope = computed(() => {
  if (authStore.isAdmin || authStore.isManager || authStore.role === 'statistician' || authStore.role === 'stat') {
    return 'all'
  }
  return authStore.user?.workshop_id ? String(authStore.user.workshop_id) : 'all'
})

const { status: streamStatus, lastEventAt } = useRealtimeStream(streamScope, {
  enabled: true,
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

const connectionTone = computed(() => {
  if (streamStatus.value === 'open') return 'success'
  if (streamStatus.value === 'connecting' || streamStatus.value === 'reconnecting') return 'warning'
  return 'danger'
})

const connectionLabel = computed(() => {
  if (streamStatus.value === 'open') return '实时连接正常'
  if (streamStatus.value === 'connecting') return '正在连接'
  if (streamStatus.value === 'reconnecting') return '正在重连'
  return '连接待核'
})

const lastEventLabel = computed(() => {
  if (lastEventAt.value) return dayjs(lastEventAt.value).format('HH:mm:ss')
  if (latestRealtimeEvent.value?.time) return dayjs(latestRealtimeEvent.value.time).format('HH:mm:ss')
  return ''
})

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
    targetDate.value = targetDate.value || dayjs().format('YYYY-MM-DD')
  }
}

async function loadDashboardSurface() {
  loading.value = true
  loadError.value = ''
  try {
    const liveData = await fetchLiveAggregation({ business_date: targetDate.value })
    aggregation.value = liveData || {}
  } catch (error) {
    loadError.value = error?.message || '接口失败'
  } finally {
    loading.value = false
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
})
</script>

<style scoped>
.live-dashboard-page {
  min-height: calc(100vh - 96px);
  display: grid;
  gap: 16px;
  padding: 18px;
  overflow: hidden;
  border: 1px solid rgba(148, 196, 255, 0.14);
  border-radius: 22px;
  background:
    radial-gradient(circle at 20% 10%, rgba(240, 184, 74, 0.14), transparent 24%),
    radial-gradient(circle at 78% 0%, rgba(94, 184, 255, 0.16), transparent 30%),
    linear-gradient(135deg, rgba(3, 13, 26, 0.98), rgba(7, 24, 45, 0.94) 56%, rgba(3, 12, 23, 0.98));
  color: rgba(232, 242, 255, 0.94);
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
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: center;
}

.live-dashboard-page__header span,
.live-section-head span {
  color: rgba(178, 202, 232, 0.68);
  font-size: 12px;
  letter-spacing: 0.14em;
}

.live-dashboard-page__header h1 {
  margin: 4px 0 0;
  font-size: clamp(28px, 4vw, 52px);
  line-height: 0.96;
  letter-spacing: -0.05em;
}

.live-dashboard-page__actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
  align-items: center;
}

.live-dashboard-page__connection {
  border: 1px solid rgba(148, 196, 255, 0.2);
  border-radius: 999px;
  padding: 7px 12px;
  font-size: 12px;
}

.live-dashboard-page__connection.is-success { color: #4ecb8a; }
.live-dashboard-page__connection.is-warning { color: #f0b84a; }
.live-dashboard-page__connection.is-danger { color: #ff6b78; }

.live-market-ticker {
  display: grid;
  grid-template-columns: repeat(7, minmax(120px, 1fr));
  gap: 10px;
  overflow-x: auto;
}

.live-market-ticker__item,
.live-machine-matrix,
.live-event-rail,
.live-metric-compare,
.live-data-state-panel,
.live-machine-workshop {
  border: 1px solid rgba(148, 196, 255, 0.16);
  background: linear-gradient(180deg, rgba(15, 35, 62, 0.72), rgba(8, 22, 40, 0.76));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06);
}

.live-market-ticker__item {
  min-width: 120px;
  border-radius: 16px;
  padding: 13px 14px;
}

.live-market-ticker__item strong {
  display: block;
  margin-top: 8px;
  font-family: var(--xt-hud-font-mono, monospace);
  font-size: 22px;
  letter-spacing: -0.04em;
}

.live-market-ticker__item em,
.live-event-rail em,
.live-data-state-panel em {
  color: rgba(178, 202, 232, 0.62);
  font-style: normal;
  font-size: 12px;
}

.live-market-ticker__item.is-warning strong { color: #f0b84a; }
.live-market-ticker__item.is-danger strong { color: #ff6b78; }
.live-market-ticker__item.is-success strong { color: #4ecb8a; }

.live-dashboard-page__grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 14px;
  align-items: stretch;
}

.live-machine-matrix,
.live-event-rail,
.live-metric-compare {
  border-radius: 20px;
  padding: 16px;
}

.live-section-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 14px;
}

.live-section-head strong {
  display: block;
  margin-top: 3px;
  font-size: 18px;
}

.live-section-head em {
  color: #f0b84a;
  font-style: normal;
  font-size: 12px;
}

.live-machine-matrix__workshops {
  display: grid;
  gap: 12px;
}

.live-machine-workshop {
  border-radius: 18px;
  padding: 12px;
}

.live-machine-workshop__head {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
}

.live-machine-workshop__head span {
  color: #f0b84a;
  font-family: var(--xt-hud-font-mono, monospace);
}

.live-machine-workshop__grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(142px, 1fr));
  gap: 10px;
}

.live-machine-card,
.live-machine-matrix__pending button {
  text-align: left;
  color: inherit;
  border: 1px solid rgba(148, 196, 255, 0.14);
  border-radius: 14px;
  background: rgba(4, 14, 28, 0.72);
  padding: 12px;
  cursor: pointer;
  transition: transform 160ms ease, border-color 160ms ease, background 160ms ease;
}

.live-machine-card:hover,
.live-machine-matrix__pending button:hover {
  transform: translateY(-2px);
  border-color: rgba(240, 184, 74, 0.44);
}

.live-machine-card__status {
  color: #f0b84a;
  font-size: 12px;
}

.live-machine-card strong {
  display: block;
  margin-top: 8px;
  font-size: 16px;
}

.live-machine-card em {
  color: rgba(178, 202, 232, 0.64);
  font-style: normal;
}

.live-machine-card__metric {
  display: flex;
  justify-content: space-between;
  margin: 12px 0;
  color: rgba(232, 242, 255, 0.86);
}

.live-machine-card__metric b {
  font-family: var(--xt-hud-font-mono, monospace);
}

.live-machine-card__shifts {
  display: grid;
  gap: 5px;
  color: rgba(178, 202, 232, 0.68);
  font-size: 12px;
}

.live-machine-card.is-success { border-color: rgba(78, 203, 138, 0.34); }
.live-machine-card.is-warning { border-color: rgba(240, 184, 74, 0.4); }
.live-machine-card.is-danger { border-color: rgba(255, 107, 120, 0.44); }

.live-machine-matrix__pending {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 8px;
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid rgba(148, 196, 255, 0.12);
}

.live-machine-matrix__pending strong {
  grid-column: 1 / -1;
  color: #f0b84a;
}

.live-machine-matrix__pending button {
  display: grid;
  gap: 4px;
}

.live-machine-matrix__pending em {
  color: rgba(232, 242, 255, 0.9);
  font-style: normal;
}

.live-machine-matrix__skeleton {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 10px;
}

.live-machine-matrix__skeleton i {
  height: 120px;
  border-radius: 14px;
  background: linear-gradient(90deg, rgba(148, 196, 255, 0.08), rgba(148, 196, 255, 0.18), rgba(148, 196, 255, 0.08));
  animation: livePulse 1.2s ease-in-out infinite;
}

.live-machine-matrix__empty,
.live-event-rail__empty {
  display: grid;
  min-height: 180px;
  place-items: center;
  color: rgba(178, 202, 232, 0.7);
}

.live-event-rail__list {
  display: grid;
  gap: 10px;
}

.live-event-rail__list article {
  border-left: 3px solid rgba(148, 196, 255, 0.26);
  border-radius: 12px;
  background: rgba(4, 14, 28, 0.66);
  padding: 11px 12px;
}

.live-event-rail__list article.is-warning { border-left-color: #f0b84a; }
.live-event-rail__list article.is-danger { border-left-color: #ff6b78; }

.live-event-rail__list span,
.live-event-rail__list strong {
  display: block;
}

.live-event-rail__list strong {
  margin-top: 5px;
  color: rgba(232, 242, 255, 0.86);
}

.live-metric-compare__grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.live-metric-compare__grid article {
  border: 1px solid rgba(148, 196, 255, 0.14);
  border-radius: 16px;
  background: rgba(4, 14, 28, 0.62);
  padding: 14px;
}

.live-metric-compare__grid article > strong {
  display: block;
  margin: 8px 0;
  font-family: var(--xt-hud-font-mono, monospace);
  font-size: 26px;
  color: #f0b84a;
}

.live-metric-compare__grid div {
  display: flex;
  justify-content: space-between;
  gap: 10px;
}

.live-metric-compare__grid b,
.live-metric-compare__grid em {
  font-size: 12px;
  font-style: normal;
}

.live-metric-compare__grid em {
  color: rgba(178, 202, 232, 0.66);
}

.live-data-state-panel {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  border-radius: 999px;
  padding: 10px;
}

.live-data-state-panel span {
  display: inline-flex;
  gap: 8px;
  align-items: center;
  border-radius: 999px;
  background: rgba(4, 14, 28, 0.66);
  padding: 7px 11px;
}

.live-data-state-panel b {
  font-size: 12px;
}

.live-data-state-panel .is-warning b { color: #f0b84a; }
.live-data-state-panel .is-danger b { color: #ff6b78; }
.live-data-state-panel .is-success b { color: #4ecb8a; }

@keyframes livePulse {
  0%, 100% { opacity: 0.58; }
  50% { opacity: 1; }
}

@media (max-width: 1180px) {
  .live-market-ticker {
    grid-template-columns: repeat(4, minmax(140px, 1fr));
  }

  .live-dashboard-page__grid,
  .live-metric-compare__grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .live-dashboard-page {
    padding: 12px;
    border-radius: 16px;
  }

  .live-dashboard-page__header {
    align-items: stretch;
    flex-direction: column;
  }

  .live-dashboard-page__actions {
    justify-content: flex-start;
  }

  .live-market-ticker {
    grid-template-columns: repeat(2, minmax(136px, 1fr));
  }
}

@media (prefers-reduced-motion: reduce) {
  .live-machine-card,
  .live-machine-matrix__pending button {
    transition: none;
  }

  .live-machine-matrix__skeleton i {
    animation: none;
  }
}
</style>
