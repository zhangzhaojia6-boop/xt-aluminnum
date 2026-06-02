<template>
  <section class="workshop-board" data-testid="workshop-dashboard-page">
    <header class="workshop-board__hero">
      <div>
        <span class="workshop-board__eyebrow">WORKSHOP COMMAND</span>
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
      <div class="workshop-board__signal" :class="`is-${freshness}`">
        <i></i>
        <span>{{ loading ? '同步中' : '链路在线' }}</span>
      </div>
    </header>

    <div class="workshop-board__kpis">
      <article v-for="item in kpis" :key="item.key" class="workshop-board__kpi" :class="`tone-${item.tone}`">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
        <small>{{ item.unit }}</small>
      </article>
    </div>

    <main class="workshop-board__grid">
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
                <th>随行卡</th>
                <th>内容</th>
                <th>状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="loading">
                <td colspan="6">加载中...</td>
              </tr>
              <tr v-else-if="machineRows.length === 0">
                <td colspan="6">暂无机列填报</td>
              </tr>
              <template v-else>
                <tr v-for="row in machineRows" :key="row.rowId">
                  <td><strong>{{ row.machineName }}</strong></td>
                  <td>{{ row.shiftName }}</td>
                  <td>{{ row.responsibleText }}</td>
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
          <p v-if="!loading && mesRows.length === 0" class="workshop-board__empty">暂无 MES 明细</p>
        </section>

        <section class="workshop-board__panel">
          <header class="workshop-board__panel-head">
            <h2>在制料明细</h2>
            <span>{{ wipRows.length }} 条</span>
          </header>
          <article v-for="row in wipRows" :key="row.key" class="workshop-board__mini-row">
            <div>
              <strong>{{ row.material_code || row.line_name || '-' }}</strong>
              <span>{{ row.alloy_grade || '-' }} · {{ row.spec_display || row.position_name || '-' }}</span>
            </div>
            <b>{{ formatNumber(row.weight_tons, 2) }} 吨</b>
          </article>
          <p v-if="!loading && wipRows.length === 0" class="workshop-board__empty">暂无在制料</p>
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
      </aside>
    </main>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import dayjs from 'dayjs'

import DateSwitcher from '../../../components/manage/DateSwitcher.vue'
import { fetchWorkshopDashboard } from '../../../api/dashboard.js'
import { fetchLiveAggregation, fetchLiveFillDetails, fetchPendingAssignmentEntries } from '../../../api/realtime.js'
import { fetchMesMaterialRecords, fetchMesWorkshopProcessRecords } from '../../../api/mes.js'
import { useAuthStore } from '../../../stores/auth.js'
import { inferBusinessDate } from '../../../utils/shiftClock.js'
import { buildFillLedgerRows } from '../../../utils/manageFillDetailsAudit.js'

const auth = useAuthStore()
const targetDate = ref(inferBusinessDate())
const loading = ref(false)
const freshness = ref('yellow')
const dashboard = ref({})
const live = ref({})
const detailRows = ref([])
const pending = ref({})
const mesProcessRows = ref([])
const mesMaterialRows = ref([])

const workshopId = computed(() => auth.user?.workshop_id || null)
const workshopTitle = computed(() => {
  const liveWorkshop = (live.value.workshops || [])[0]
  return liveWorkshop?.workshop_name || liveWorkshop?.name || dashboard.value.workshop_name || '各车间看板'
})
const ledgerRows = computed(() => buildFillLedgerRows(detailRows.value))
const machineRows = computed(() => ledgerRows.value.filter((row) => ['work_order_entry', 'mobile_shift_report'].includes(row.sourceType)).slice(0, 12))
const energyRows = computed(() => ledgerRows.value.filter((row) => row.sourceType === 'machine_energy' || row.energy_kwh != null || row.gas_m3 != null).slice(0, 4))
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
    title: row.batch_no || row.source_id || row.process_name || 'MES 过站',
    flow: `${row.workshop_name || '-'} / ${row.process_name || '-'} / ${row.device_name || '-'}`,
    unmatched: !row.device_name,
  }))
  return [...projectionRows, ...processRows].slice(0, 8)
})
const wipRows = computed(() => mesMaterialRows.value.slice(0, 6).map((row, index) => ({ ...row, key: row.source_id || `wip-${index}` })))
const exceptionRows = computed(() => {
  const mes = live.value.mes_machine_binding || {}
  const missingOutput = live.value.quality?.missing_output_weight || live.value.overall_progress?.missing_output_weight || {}
  return [
    { key: 'pending', label: '待归属机列', value: Number(pending.value?.summary?.entry_count || live.value.overall_progress?.pending_assignment?.entry_count || 0), tone: 'warning' },
    { key: 'missing-output', label: '填报但没产量', value: Number(missingOutput.entry_count || 0), tone: 'warning' },
    { key: 'mes-unmatched', label: 'MES 未匹配机列', value: Number(mes.unresolved_machine_count || 0) + Number(mes.upstream_machine_code_missing_count || 0), tone: 'danger' },
    { key: 'energy', label: '能耗缺失', value: energyRows.value.length ? 0 : 1, tone: energyRows.value.length ? 'success' : 'warning' },
  ]
})
const kpis = computed(() => [
  { key: 'process', label: '今日下机量', value: formatNumber(dashboard.value.process_output ?? dashboard.value.total_output, 2), unit: '吨', tone: 'primary' },
  { key: 'finished', label: '成品口径产量', value: formatNumber(dashboard.value.total_output, 2), unit: '吨', tone: 'success' },
  { key: 'pass', label: '道次总数', value: formatNumber(dashboard.value.pass_count_total, 0), unit: '道', tone: 'primary' },
  { key: 'exception', label: '异常数量', value: formatNumber(exceptionRows.value.reduce((sum, row) => sum + Number(row.value || 0), 0), 0), unit: '项', tone: 'danger' },
])

function scopedParams(extra = {}) {
  return workshopId.value ? { ...extra, workshop_id: workshopId.value } : extra
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

async function load() {
  loading.value = true
  freshness.value = 'yellow'
  try {
    const [dashboardResult, liveResult, detailResult, pendingResult, processResult, materialResult] = await Promise.allSettled([
      fetchWorkshopDashboard(scopedParams({ target_date: targetDate.value })),
      fetchLiveAggregation(scopedParams({ business_date: targetDate.value })),
      fetchLiveFillDetails(scopedParams({ business_date: targetDate.value, limit: 1200 })),
      fetchPendingAssignmentEntries(scopedParams({ business_date: targetDate.value })),
      fetchMesWorkshopProcessRecords({ business_date: targetDate.value, limit: 80 }),
      fetchMesMaterialRecords({ business_date: targetDate.value, limit: 80 }),
    ])
    dashboard.value = dashboardResult.status === 'fulfilled' ? dashboardResult.value || {} : {}
    live.value = liveResult.status === 'fulfilled' ? liveResult.value || {} : {}
    detailRows.value = detailResult.status === 'fulfilled' ? detailResult.value?.items || [] : []
    pending.value = pendingResult.status === 'fulfilled' ? pendingResult.value || {} : {}
    mesProcessRows.value = processResult.status === 'fulfilled' ? processResult.value || [] : []
    mesMaterialRows.value = materialResult.status === 'fulfilled' ? materialResult.value || [] : []
    freshness.value = [dashboardResult, liveResult, detailResult].some((item) => item.status === 'rejected') ? 'yellow' : 'green'
  } catch {
    freshness.value = 'red'
  } finally {
    loading.value = false
  }
}

function stepDate(delta) {
  targetDate.value = dayjs(targetDate.value).add(delta, 'day').format('YYYY-MM-DD')
}

function pickDate(value) {
  targetDate.value = value
}

watch(targetDate, load)
load()
</script>

<style scoped>
.workshop-board {
  position: relative;
  display: grid;
  gap: 16px;
  padding: 18px;
  overflow: hidden;
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
}

.workshop-board__hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  gap: 16px;
  align-items: center;
  padding: 18px;
  border: 1px solid rgba(0, 242, 255, 0.18);
  border-radius: 18px;
  background: linear-gradient(90deg, rgba(5, 22, 43, 0.9), rgba(8, 43, 74, 0.62));
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
  border: 1px solid rgba(0, 242, 255, 0.18);
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(9, 34, 61, 0.9), rgba(5, 18, 35, 0.82));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06), 0 18px 48px rgba(0, 24, 54, 0.28);
  backdrop-filter: blur(12px);
}

.workshop-board__kpi {
  padding: 16px;
}

.workshop-board__kpi strong {
  display: block;
  margin-top: 10px;
  color: #e1fdff;
  font-family: var(--xt-font-display);
  font-size: clamp(26px, 3vw, 38px);
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
}

.workshop-board__panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.workshop-board__panel-head h2 {
  font-size: 18px;
}

.workshop-board__table {
  overflow: auto;
}

.workshop-board table {
  width: 100%;
  border-collapse: collapse;
  min-width: 820px;
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
.workshop-board__exception {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid rgba(0, 242, 255, 0.1);
}

.workshop-board__mini-row div,
.workshop-board__mes-row div {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.workshop-board__mini-row span,
.workshop-board__mes-row span {
  overflow: hidden;
  color: rgba(185, 223, 235, 0.68);
  font-size: 12px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.workshop-board__mini-row b,
.workshop-board__exception strong {
  color: #e1fdff;
  font-family: var(--xt-font-display);
}

.workshop-board__mes-row {
  justify-content: flex-start;
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
</style>
