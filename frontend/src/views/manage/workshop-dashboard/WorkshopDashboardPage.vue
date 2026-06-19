<template>
  <section class="workshop-board" data-testid="workshop-dashboard" data-visual-pass="stitch-image2-second-pass">
    <header class="workshop-board__hero">
      <div>
        <span class="workshop-board__eyebrow">车间看板</span>
        <h1>{{ workshopTitle }}</h1>
      </div>
      <DateSwitcher
        :model-value="targetDate"
        :loading="loading"
        :freshness="freshness"
        @step="stepDate"
        @refresh="load"
        @pick="pickDate"
      />
      <div v-if="canChooseWorkshop" class="workshop-board__filter" data-testid="workshop-dashboard-filter">
        <span>车间</span>
        <select v-model.number="selectedWorkshopId" aria-label="筛选车间">
          <option v-for="workshop in workshops" :key="workshop.id" :value="workshop.id">{{ workshop.name }}</option>
        </select>
      </div>
      <button
        class="workshop-board__export"
        type="button"
        :disabled="exportingMissingReport || (canChooseWorkshop && !workshopId)"
        data-testid="workshop-dashboard-missing-export"
        @click="downloadMissingReport"
      >
        <el-icon><Download /></el-icon>
        <span>{{ exportingMissingReport ? '导出中' : '导出缺报' }}</span>
      </button>
      <div class="workshop-board__signal" :class="`is-${freshness}`">
        <i></i>
        <span>{{ loading ? '同步中' : '链路在线' }}</span>
      </div>
    </header>

    <div class="xt-second-pass-source-strip" data-testid="second-pass-source-strip" aria-label="数据来源">
      <span class="xt-second-pass-source-strip__item">MES 外部数据</span>
      <span class="xt-second-pass-source-strip__item">MES 车间报表</span>
      <span class="xt-second-pass-source-strip__item">MES 在制料统计</span>
      <span class="xt-second-pass-source-strip__item">人工填报</span>
      <span class="xt-second-pass-source-strip__item">算法数据</span>
    </div>

    <div class="workshop-board__kpis">
      <article v-for="item in kpis" :key="item.key" class="workshop-board__kpi" :class="`tone-${item.tone}`">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
        <small>{{ item.unit }}</small>
      </article>
    </div>

    <main class="workshop-board__grid" data-testid="workshop-dashboard-page">
      <section class="workshop-board__panel workshop-board__panel--ledger">
        <header class="workshop-board__panel-head">
          <h2>机列填报明细</h2>
          <span>{{ machineRows.length }} 条</span>
        </header>
        <div class="workshop-board__table">
          <table>
            <thead>
              <tr>
                <th>机列</th>
                <th>班次</th>
                <th>责任人</th>
                <th>填报时间</th>
                <th>随行卡</th>
                <th>内容</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="loading">
                <td colspan="7">加载中...</td>
              </tr>
              <tr v-else-if="machineRows.length === 0">
                <td colspan="7">暂无机列填报</td>
              </tr>
              <template v-else>
                <tr v-for="row in machineRows" :key="row.rowId">
                  <td><strong>{{ row.machineName }}</strong></td>
                  <td>{{ row.shiftName }}</td>
                  <td>{{ row.responsibleText }}</td>
                  <td>{{ row.submittedText }}</td>
                  <td>{{ row.tracking_card_no || '-' }}</td>
                  <td>{{ row.contentText }}</td>
                  <td><span class="workshop-board__status">{{ row.statusLabel }}</span></td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </section>

      <aside class="workshop-board__side">
        <section class="workshop-board__panel">
          <header class="workshop-board__panel-head">
            <h2>电工填报明细</h2>
            <span>{{ energyRows.length }} 条</span>
          </header>
          <article v-for="row in energyRows" :key="row.rowId" class="workshop-board__mini-row">
            <div>
              <strong>{{ row.machineName }}</strong>
              <span>{{ row.responsibleText }} · {{ row.submittedText }}</span>
            </div>
            <b>{{ energyText(row) }}</b>
          </article>
          <p v-if="!loading && energyRows.length === 0" class="workshop-board__empty">暂无能耗明细</p>
        </section>

        <section class="workshop-board__panel">
          <header class="workshop-board__panel-head">
            <h2>外部 MES 明细</h2>
            <span>{{ mesRows.length }} 条</span>
          </header>
          <article v-for="row in mesRows" :key="row.key" class="workshop-board__mes-row">
            <i :class="{ 'is-alert': row.unmatched }"></i>
            <div>
              <strong>{{ row.title }}</strong>
              <span>{{ row.flow }}</span>
            </div>
          </article>
          <p v-if="mesRows.length === 0" class="workshop-board__empty">{{ mesEmptyText }}</p>
        </section>

        <section class="workshop-board__panel" data-testid="workshop-dashboard-mes-gap-panel">
          <header class="workshop-board__panel-head">
            <h2>MES 对照异常</h2>
            <span>{{ mesGapRows.length }} 条</span>
          </header>
          <article v-for="row in mesGapRows" :key="rowKey(row)" class="workshop-board__mes-gap-row">
            <div>
              <strong>{{ mesGapStatusText(row.status) }}</strong>
              <span>{{ row.process_name || '-' }} · {{ row.tracking_card_no || row.batch_no || '-' }}</span>
            </div>
            <b>{{ mesGapWeightText(row) }}</b>
          </article>
          <p v-if="!loading && mesGapRows.length === 0" class="workshop-board__empty">暂无 MES 对照异常</p>
        </section>

        <section class="workshop-board__panel">
          <header class="workshop-board__panel-head">
            <h2>在制料明细</h2>
            <span>{{ wipRows.length }} 条</span>
          </header>
          <article v-for="row in wipRows" :key="row.key" class="workshop-board__mini-row">
            <div>
              <strong>{{ row.title }}</strong>
              <span>{{ row.subtitle }}</span>
            </div>
            <b>{{ formatNumber(row.weight, 2) }} 吨</b>
          </article>
          <p v-if="wipRows.length === 0" class="workshop-board__empty">{{ wipEmptyText }}</p>
        </section>

        <section class="workshop-board__panel">
          <header class="workshop-board__panel-head">
            <h2>异常事务</h2>
            <span>{{ exceptionRows.length }} 类</span>
          </header>
          <article v-for="row in exceptionRows" :key="row.key" class="workshop-board__exception" :class="`tone-${row.tone}`">
            <span>{{ row.label }}</span>
            <strong>{{ row.value }}</strong>
          </article>
        </section>

        <MissingReportPanel
          title="本车间缺报"
          :rows="missingRows"
          :loading="loading"
          :compact="compactMissingPanel"
        />
      </aside>
    </main>
  </section>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { Download } from '@element-plus/icons-vue'

import DateSwitcher from '../../../components/manage/DateSwitcher.vue'
import MissingReportPanel from '../../../components/manage/MissingReportPanel.vue'
import { fetchWorkshopDashboard } from '../../../api/dashboard.js'
import { exportMissingReportExcel, fetchLiveAggregation, fetchLiveFillDetails, fetchMesFillGaps, fetchPendingAssignmentEntries } from '../../../api/realtime.js'
import { fetchMesWipTotalSnapshots, fetchMesWorkshopProcessRecords } from '../../../api/mes.js'
import { fetchWorkshops } from '../../../api/master.js'
import { useAuthStore } from '../../../stores/auth.js'
import { inferBusinessDate } from '../../../utils/shiftClock.js'
import { downloadBlob } from '../../../utils/downloadBlob.js'
import {
  buildFillLedgerRows,
  explainWorkshopDataEmptyState,
  isEnergyLedgerRow,
  isMachineProductionLedgerRow,
} from '../../../utils/manageFillDetailsAudit.js'
import { buildMissingReportRows } from '../../../utils/missingReportRows.js'

const WORKSHOP_DETAIL_PAGE_LIMIT = 800
const auth = useAuthStore()
const targetDate = ref(inferBusinessDate())
const loading = ref(false)
const freshness = ref('yellow')
const dashboard = ref({})
const live = ref({})
const detailRows = ref([])
const pending = ref({})
const mesGapData = ref({})
const mesProcessRows = ref([])
const mesMaterialRows = ref([])
const workshops = ref([])
const workshopsLoaded = ref(false)
const selectedWorkshopId = ref(null)
const suppressWorkshopSelectionWatch = ref(false)
const compactMissingPanel = ref(false)
const exportingMissingReport = ref(false)
let compactMediaQuery = null
let loadRequestId = 0

const MES_GAP_STATUS_LABELS = {
  missing_local_entry: 'MES有工序本地未填',
  mes_batch_unmapped: '批号未映射',
  local_entry_unassigned: '本地未归机列',
  weight_mismatch: '重量不一致',
}

const canChooseWorkshop = computed(() => auth.isAdmin || (auth.hasGlobalReviewScope && !auth.isWorkshopDirector))
const workshopId = computed(() => canChooseWorkshop.value ? selectedWorkshopId.value : (auth.user?.workshop_id || null))
const selectedWorkshop = computed(() => workshops.value.find((item) => Number(item.id) === Number(workshopId.value)) || null)
const workshopTitle = computed(() => {
  const liveWorkshop = (live.value.workshops || [])[0]
  return selectedWorkshop.value?.name || liveWorkshop?.workshop_name || liveWorkshop?.name || dashboard.value.workshop_name || '各车间看板'
})
const ledgerRows = computed(() => buildFillLedgerRows(detailRows.value))
const machineRows = computed(() => ledgerRows.value.filter(isMachineProductionLedgerRow).slice(0, 12))
const energyRows = computed(() => ledgerRows.value.filter(isEnergyLedgerRow).slice(0, 4))
const mesSyncStatus = computed(() => live.value.mes_sync_status || live.value.mesSyncStatus || {})
const mesRows = computed(() => {
  const projectionRows = ledgerRows.value
    .filter((row) => row.sourceType === 'mes_projection')
    .slice(0, 4)
    .map((row) => ({
      key: row.rowId,
      title: row.tracking_card_no || row.machineName || 'MES 投影',
      flow: `${row.workshopName || '-'} / ${row.machineName || '-'}`,
      unmatched: row.machineName === '未匹配机列',
    }))
  const processRows = mesProcessRows.value.slice(0, 6).map((row, index) => ({
    key: `process-${row.source_id || index}`,
    title: mesProcessTitle(row),
    flow: mesProcessFlow(row),
    unmatched: isUnmatchedMesDevice(row),
  }))
  return [...projectionRows, ...processRows].slice(0, 8)
})
const mesGapRows = computed(() => {
  const items = Array.isArray(mesGapData.value?.items) ? mesGapData.value.items : []
  return items.filter((row) => row.status && row.status !== 'matched').slice(0, 5)
})
const wipRows = computed(() => mesMaterialRows.value.slice(0, 6).map((row, index) => ({
  ...row,
  key: row.source_id || `wip-${index}`,
  title: row.process_name || row.workshop_name || '-',
  subtitle: `${row.workshop_name || '-'} · ${formatNumber(row.doing_count, 0)} 卷 · ${row.source_page || row.sourcePage || 'MES 在制料统计'}`,
  weight: row.doing_weight_tons ?? 0,
})))
const hasWorkshop = computed(() => Boolean(workshopId.value))
const mesEmptyText = computed(() => explainWorkshopDataEmptyState({
  loading: loading.value,
  hasWorkshop: hasWorkshop.value,
  kind: 'mes',
  syncStatus: mesSyncStatus.value,
}))
const wipEmptyText = computed(() => explainWorkshopDataEmptyState({
  loading: loading.value,
  hasWorkshop: hasWorkshop.value,
  kind: 'wip',
  syncStatus: mesSyncStatus.value,
}))
const missingRows = computed(() => buildMissingReportRows(live.value))
const exceptionRows = computed(() => {
  const mes = live.value.mes_machine_binding || {}
  const missingOutput = live.value.quality?.missing_output_weight || live.value.overall_progress?.missing_output_weight || {}
  return [
    { key: 'pending', label: '待归属机列', value: Number(pending.value?.summary?.entry_count || live.value.overall_progress?.pending_assignment?.entry_count || 0), tone: 'warning' },
    { key: 'missing-output', label: '填报但没产量', value: Number(missingOutput.entry_count || 0), tone: 'warning' },
    { key: 'mes-unmatched', label: 'MES 未匹配机列', value: Number(mes.unresolved_machine_count || 0), tone: 'danger' },
    { key: 'energy', label: '能耗缺失', value: energyRows.value.length ? 0 : 1, tone: energyRows.value.length ? 'success' : 'warning' },
  ]
})
const factoryMesHomeFact = computed(() => dashboard.value.factory_packaging_fact || dashboard.value.factory_mes_home_packaging_fact || dashboard.value.factoryMesHomePackagingFact || {})
const factoryProductionFact = computed(() => dashboard.value.factory_production_fact || dashboard.value.factoryProductionFact || {})
const liveWorkshopTotal = computed(() => {
  const liveWorkshop = (live.value.workshops || [])[0] || {}
  return liveWorkshop.workshop_total || liveWorkshop.workshopTotal || {}
})
const kpis = computed(() => [
  { key: 'workshop-feeding', label: '车间投料量 / 上机量', value: formatNumber(liveWorkshopTotal.value.input ?? dashboard.value.input_weight ?? dashboard.value.inputWeight, 2), unit: '吨', tone: 'primary' },
  { key: 'process', label: '车间下机量', value: formatNumber(dashboard.value.process_output ?? liveWorkshopTotal.value.output ?? dashboard.value.total_output, 2), unit: '吨', tone: 'primary' },
  { key: 'finished', label: '车间口径产量', value: formatNumber(dashboard.value.total_output, 2), unit: '吨', tone: 'success' },
  { key: 'factory-feeding', label: '全厂投料', value: formatNumber(factoryProductionFact.value.factory_feeding_daily_input, 2), unit: '吨', tone: 'primary' },
  { key: 'factory-mes-daily', label: '全厂包装', value: formatNumber(factoryMesHomeFact.value.factory_packaging_daily_output ?? factoryMesHomeFact.value.mes_home_daily_output, 2), unit: '吨', tone: 'success' },
  { key: 'factory-inbound', label: '成品入库', value: formatNumber(factoryProductionFact.value.factory_finished_inbound_daily_output, 2), unit: '吨', tone: 'success' },
  { key: 'factory-yield', label: '全厂成品率', value: formatNumber(factoryProductionFact.value.daily_yield_rate, 2), unit: '%', tone: 'primary' },
  { key: 'factory-mes-month', label: '包装月累计', value: formatNumber(factoryMesHomeFact.value.factory_packaging_month_to_date_output ?? factoryMesHomeFact.value.mes_home_month_to_date_output, 2), unit: '吨', tone: 'primary' },
  { key: 'pass', label: '道次总数', value: formatNumber(dashboard.value.pass_count_total, 0), unit: '道', tone: 'primary' },
  { key: 'exception', label: '异常数量', value: formatNumber(exceptionRows.value.reduce((sum, row) => sum + Number(row.value || 0), 0), 0), unit: '项', tone: 'danger' },
])

function scopedParams(extra = {}) {
  return workshopId.value ? { ...extra, workshop_id: workshopId.value } : extra
}

async function loadWorkshops() {
  if (workshopsLoaded.value) return
  if (!canChooseWorkshop.value) {
    workshopsLoaded.value = true
    return
  }
  try {
    workshops.value = await fetchWorkshops({ limit: 300 })
    if (canChooseWorkshop.value && !selectedWorkshopId.value && workshops.value.length) {
      suppressWorkshopSelectionWatch.value = true
      selectedWorkshopId.value = workshops.value[0].id
    }
  } catch {
    workshops.value = []
  } finally {
    workshopsLoaded.value = true
  }
}

function formatNumber(value, digits = 2) {
  const num = Number(value)
  if (!Number.isFinite(num)) return '-'
  return num.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: digits })
}

function energyText(row) {
  const parts = []
  if (row.energy_kwh != null) parts.push(`${formatNumber(row.energy_kwh, 1)} kWh`)
  if (row.gas_m3 != null) parts.push(`${formatNumber(row.gas_m3, 1)} m³`)
  return parts.join(' / ') || row.contentText || '-'
}

function mesGapStatusText(status) {
  return MES_GAP_STATUS_LABELS[status] || status || '-'
}

function mesGapWeightText(row) {
  const mes = formatNumber(row?.mes_output_weight, 1)
  const local = formatNumber(row?.local_output_weight, 1)
  return `${mes} / ${local} kg`
}

function mesProcessTitle(row) {
  return row?.batch_no || row?.customer_alias || row?.source_id || row?.process_name || 'MES 过站'
}

function mesProcessWeightText(row) {
  const input = row?.input_weight_tons
  const output = row?.output_weight_tons
  if (input == null && output == null) return ''
  return `上${formatNumber(input, 2)}吨 / 下${formatNumber(output, 2)}吨`
}

function mesProcessFlow(row) {
  const route = `${row?.workshop_name || '-'} / ${row?.process_name || '-'} / ${row?.device_name || '-'}`
  return [route, mesProcessWeightText(row), row?.worker_name || '', formatDateTime(row?.end_time)].filter(Boolean).join(' · ')
}

function isUnmatchedMesDevice(row) {
  const device = String(row?.device_name || '').trim().toLowerCase()
  return !device || device === 'pc'
}

function formatDateTime(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  return date.toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function rowKey(row) {
  return `${row.status || 'gap'}-${row.local_entry_id || row.tracking_card_no || row.batch_no || 'unknown'}`
}

async function load() {
  const requestId = ++loadRequestId
  loading.value = true
  freshness.value = 'yellow'
  try {
    await loadWorkshops()
    if (requestId !== loadRequestId) return
    if (canChooseWorkshop.value && !workshopId.value) {
      dashboard.value = {}
      live.value = {}
      detailRows.value = []
      pending.value = {}
      mesGapData.value = {}
      mesProcessRows.value = []
      mesMaterialRows.value = []
      freshness.value = 'yellow'
      return
    }
    const [dashboardResult, liveResult, detailResult, pendingResult, mesGapResult, processResult, materialResult] = await Promise.allSettled([
      fetchWorkshopDashboard(scopedParams({ target_date: targetDate.value })),
      fetchLiveAggregation(scopedParams({ business_date: targetDate.value })),
      fetchLiveFillDetails(scopedParams({ business_date: targetDate.value, limit: WORKSHOP_DETAIL_PAGE_LIMIT })),
      fetchPendingAssignmentEntries(scopedParams({ business_date: targetDate.value })),
      fetchMesFillGaps(scopedParams({ business_date: targetDate.value })),
      fetchMesWorkshopProcessRecords(scopedParams({ business_date: targetDate.value, limit: 80 })),
      fetchMesWipTotalSnapshots(scopedParams({ business_date: targetDate.value, limit: 80 })),
    ])
    if (requestId !== loadRequestId) return
    dashboard.value = dashboardResult.status === 'fulfilled' ? dashboardResult.value || {} : {}
    live.value = liveResult.status === 'fulfilled' ? liveResult.value || {} : {}
    detailRows.value = detailResult.status === 'fulfilled' ? detailResult.value?.items || [] : []
    pending.value = pendingResult.status === 'fulfilled' ? pendingResult.value || {} : {}
    mesGapData.value = mesGapResult.status === 'fulfilled' ? mesGapResult.value || {} : {}
    mesProcessRows.value = processResult.status === 'fulfilled' ? processResult.value || [] : []
    mesMaterialRows.value = materialResult.status === 'fulfilled' ? materialResult.value || [] : []
    freshness.value = [dashboardResult, liveResult, detailResult, mesGapResult].some((item) => item.status === 'rejected') ? 'yellow' : 'green'
  } catch {
    if (requestId !== loadRequestId) return
    mesGapData.value = {}
    freshness.value = 'red'
  } finally {
    if (requestId === loadRequestId) loading.value = false
  }
}

function stepDate(delta) {
  targetDate.value = dayjs(targetDate.value).add(delta, 'day').format('YYYY-MM-DD')
}

function pickDate(value) {
  targetDate.value = value
}

function safeFilenameText(value) {
  return String(value || '').replace(/[\\/:*?"<>|]/g, '-')
}

async function downloadMissingReport() {
  exportingMissingReport.value = true
  try {
    const data = await exportMissingReportExcel(scopedParams({ business_date: targetDate.value }))
    downloadBlob(data, `缺报明细-${safeFilenameText(workshopTitle.value)}-${targetDate.value}.xlsx`)
    ElMessage.success('缺报Excel已导出')
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '缺报Excel导出失败')
  } finally {
    exportingMissingReport.value = false
  }
}

function syncCompactMissingPanel() {
  compactMissingPanel.value = Boolean(compactMediaQuery?.matches)
}

onMounted(() => {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return
  compactMediaQuery = window.matchMedia('(max-width: 760px)')
  syncCompactMissingPanel()
  compactMediaQuery.addEventListener?.('change', syncCompactMissingPanel)
})

onUnmounted(() => {
  compactMediaQuery?.removeEventListener?.('change', syncCompactMissingPanel)
})

watch(targetDate, load)
watch(selectedWorkshopId, () => {
  if (suppressWorkshopSelectionWatch.value) {
    suppressWorkshopSelectionWatch.value = false
    return
  }
  load()
})
load()
</script>

<style scoped>
.workshop-board {
  position: relative;
  display: grid;
  gap: 16px;
  box-sizing: border-box;
  width: 100%;
  min-width: 0;
  max-width: 100%;
  padding: 18px;
  overflow: clip;
  border: 1px solid rgba(0, 242, 255, 0.16);
  border-radius: 24px;
  background:
    radial-gradient(circle at 12% 0%, rgba(0, 145, 255, 0.24), transparent 28%),
    radial-gradient(circle at 86% 8%, rgba(0, 242, 255, 0.14), transparent 30%),
    linear-gradient(135deg, #06101f 0%, #071b31 48%, #03101f 100%);
  color: rgba(225, 253, 255, 0.94);
}

.workshop-board::before,
.workshop-board::after {
  position: absolute;
  inset: 0;
  pointer-events: none;
  content: "";
}

.workshop-board::before {
  opacity: 0.28;
  background:
    linear-gradient(rgba(0, 242, 255, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 242, 255, 0.08) 1px, transparent 1px);
  background-size: 36px 36px;
}

.workshop-board::after {
  background: linear-gradient(110deg, transparent, rgba(0, 242, 255, 0.12), transparent);
  transform: translateX(-120%);
  animation: workshopScan 8s linear infinite;
}

.workshop-board__hero,
.workshop-board__kpis,
.workshop-board__grid {
  position: relative;
  z-index: 1;
  min-width: 0;
}

.workshop-board__hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto auto auto;
  gap: 16px;
  align-items: center;
  padding: 18px;
  border: 1px solid rgba(0, 242, 255, 0.18);
  border-radius: 18px;
  background: linear-gradient(90deg, rgba(5, 22, 43, 0.9), rgba(8, 43, 74, 0.62));
}

.workshop-board__hero > div {
  min-width: 0;
}

.workshop-board__filter {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border: 1px solid rgba(0, 242, 255, 0.22);
  border-radius: 999px;
  background: rgba(4, 21, 41, 0.72);
}

.workshop-board__filter span {
  color: rgba(185, 223, 235, 0.72);
  font-size: 12px;
  font-weight: 900;
}

.workshop-board__filter select {
  min-width: 168px;
  border: 0;
  background: transparent;
  color: rgba(225, 253, 255, 0.96);
  font-weight: 800;
  outline: none;
}

.workshop-board__filter option {
  color: #06101f;
}

.workshop-board__eyebrow,
.workshop-board__panel-head span,
.workshop-board__kpi span,
.workshop-board__kpi small {
  color: rgba(185, 223, 235, 0.68);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.workshop-board h1,
.workshop-board h2 {
  margin: 0;
  color: #e1fdff;
  font-family: var(--xt-font-display);
}

.workshop-board h1 {
  font-size: clamp(28px, 3vw, 42px);
  letter-spacing: -0.04em;
  line-height: 1.08;
  overflow-wrap: anywhere;
}

.workshop-board__signal {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border: 1px solid rgba(0, 242, 255, 0.22);
  border-radius: 999px;
  background: rgba(0, 242, 255, 0.08);
  font-weight: 800;
}

.workshop-board__export {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 42px;
  padding: 0 14px;
  border: 1px solid rgba(0, 242, 255, 0.3);
  border-radius: 999px;
  background: rgba(0, 242, 255, 0.1);
  color: rgba(225, 253, 255, 0.96);
  cursor: pointer;
  font-weight: 900;
  white-space: nowrap;
}

.workshop-board__export:disabled {
  cursor: wait;
  opacity: 0.62;
}

.workshop-board__signal i,
.workshop-board__mes-row i {
  width: 9px;
  height: 9px;
  border-radius: 999px;
  background: #00f2ff;
  box-shadow: 0 0 18px rgba(0, 242, 255, 0.9);
}

.workshop-board__signal.is-red i,
.workshop-board__mes-row i.is-alert {
  background: #ff3d00;
  box-shadow: 0 0 18px rgba(255, 61, 0, 0.9);
}

.workshop-board__kpis {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.workshop-board__kpi,
.workshop-board__panel {
  min-width: 0;
  max-width: 100%;
  border: 1px solid rgba(0, 242, 255, 0.18);
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(9, 34, 61, 0.9), rgba(5, 18, 35, 0.82));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06), 0 18px 48px rgba(0, 24, 54, 0.28);
  backdrop-filter: blur(12px);
}

.workshop-board__kpi {
  padding: 16px;
  overflow: hidden;
}

.workshop-board__kpi strong {
  display: block;
  margin-top: 10px;
  color: #e1fdff;
  font-family: var(--xt-font-display);
  font-size: clamp(26px, 3vw, 38px);
  line-height: 1.05;
  overflow-wrap: anywhere;
  text-shadow: 0 0 24px rgba(0, 242, 255, 0.26);
}

.workshop-board__kpi.tone-danger strong {
  color: #ffb199;
  text-shadow: 0 0 24px rgba(255, 61, 0, 0.34);
}

.workshop-board__grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(360px, 0.65fr);
  gap: 14px;
}

.workshop-board__panel {
  padding: 14px;
}

.workshop-board__side {
  display: grid;
  gap: 14px;
  min-width: 0;
}

.workshop-board__panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.workshop-board__panel-head > * {
  min-width: 0;
}

.workshop-board__panel-head h2 {
  font-size: 18px;
  overflow-wrap: anywhere;
}

.workshop-board__table {
  overflow: auto;
  max-width: 100%;
  -webkit-overflow-scrolling: touch;
}

.workshop-board table {
  width: 100%;
  border-collapse: collapse;
  min-width: 920px;
}

.workshop-board th,
.workshop-board td {
  padding: 11px 10px;
  border-bottom: 1px solid rgba(0, 242, 255, 0.1);
  text-align: left;
  white-space: nowrap;
}

.workshop-board th {
  color: rgba(185, 223, 235, 0.7);
  font-size: 12px;
}

.workshop-board td {
  color: rgba(225, 253, 255, 0.86);
  font-size: 13px;
}

.workshop-board__status {
  display: inline-flex;
  padding: 4px 8px;
  border: 1px solid rgba(0, 242, 255, 0.24);
  border-radius: 999px;
  color: #9ff8ff;
  background: rgba(0, 242, 255, 0.08);
}

.workshop-board__mini-row,
.workshop-board__mes-row,
.workshop-board__mes-gap-row,
.workshop-board__exception {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid rgba(0, 242, 255, 0.1);
  min-width: 0;
}

.workshop-board__mini-row div,
.workshop-board__mes-row div,
.workshop-board__mes-gap-row div {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.workshop-board__mini-row strong,
.workshop-board__mes-row strong,
.workshop-board__mes-gap-row strong {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workshop-board__mini-row span,
.workshop-board__mes-row span,
.workshop-board__mes-gap-row span {
  overflow: hidden;
  color: rgba(185, 223, 235, 0.68);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workshop-board__mini-row b,
.workshop-board__mes-gap-row b,
.workshop-board__exception strong {
  min-width: 0;
  max-width: 45%;
  flex-shrink: 0;
  color: #e1fdff;
  font-family: var(--xt-font-display);
  overflow-wrap: anywhere;
  text-align: right;
}

.workshop-board__mes-row {
  justify-content: flex-start;
}

.workshop-board__mes-gap-row b {
  color: #ffd27a;
}

.workshop-board__exception.tone-danger strong {
  color: #ffb199;
}

.workshop-board__exception.tone-warning strong {
  color: #ffd27a;
}

.workshop-board__empty {
  margin: 0;
  color: rgba(185, 223, 235, 0.58);
}

@keyframes workshopScan {
  to {
    transform: translateX(120%);
  }
}

@media (max-width: 1100px) {
  .workshop-board__hero,
  .workshop-board__grid,
  .workshop-board__kpis {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .workshop-board {
    gap: 10px;
    min-height: 100dvh;
    margin: 0;
    padding: 10px;
    border-radius: 0;
    overflow-x: hidden;
  }

  .workshop-board::before {
    opacity: 0.18;
    background-size: 26px 26px;
  }

  .workshop-board::after {
    display: none;
  }

  .workshop-board__hero {
    grid-template-columns: 1fr;
    gap: 10px;
    padding: 12px;
    border-radius: 16px;
  }

  .workshop-board h1 {
    font-size: clamp(22px, 7vw, 28px);
    letter-spacing: -0.03em;
  }

  .workshop-board__signal,
  .workshop-board__export,
  .workshop-board__filter {
    width: 100%;
    min-width: 0;
    justify-content: space-between;
    border-radius: 14px;
  }

  .workshop-board__filter select {
    min-width: 0;
    max-width: 100%;
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .workshop-board__kpis {
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  .workshop-board__kpi {
    min-height: 104px;
    padding: 12px;
    border-radius: 16px;
  }

  .workshop-board__kpi strong {
    margin-top: 8px;
    font-size: clamp(20px, 7vw, 26px);
  }

  .workshop-board__grid,
  .workshop-board__side {
    gap: 10px;
  }

  .workshop-board__side {
    order: -1;
  }

  .workshop-board__side .xt-missing-report {
    order: -1;
  }

  .workshop-board__panel {
    padding: 12px;
    border-radius: 16px;
    overflow: hidden;
  }

  .workshop-board__panel-head {
    margin-bottom: 8px;
  }

  .workshop-board__panel-head h2 {
    font-size: 16px;
  }

  .workshop-board table {
    min-width: 680px;
  }

  .workshop-board th,
  .workshop-board td {
    padding: 9px 8px;
  }

      .workshop-board__mini-row,
      .workshop-board__mes-row,
      .workshop-board__mes-gap-row,
      .workshop-board__exception {
    gap: 8px;
    padding: 8px 0;
  }
}

@media (max-width: 420px) {
  .workshop-board__kpis {
    grid-template-columns: 1fr 1fr;
  }

  .workshop-board__kpi strong {
    font-size: 22px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .workshop-board::after {
    display: none;
  }
}
</style>
