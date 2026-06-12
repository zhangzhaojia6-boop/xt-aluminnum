<template>
  <section
    class="xt-fill-details"
    data-testid="manage-fill-details"
    data-visual-pass="stitch-image2-second-pass"
    :data-stitch-project-id="stitchSurface.stitch.projectId"
    :data-stitch-screen-id="stitchSurface.stitch.screenId"
  >
    <header class="xt-fill-details__hero">
      <div class="xt-fill-details__hero-copy">
        <span class="xt-fill-details__eyebrow">数据链路</span>
        <h1>填报明细</h1>
      </div>
      <DateSwitcher
        :model-value="targetDate"
        :loading="loading"
        :freshness="freshness"
        @step="stepDate"
        @refresh="load"
        @pick="pickDate"
      />
      <button
        class="xt-fill-details__export"
        type="button"
        :disabled="exportingMissingReport"
        data-testid="fill-details-missing-export"
        @click="downloadMissingReport"
      >
        <el-icon><Download /></el-icon>
        <span>{{ exportingMissingReport ? '导出中' : '导出缺报' }}</span>
      </button>
      <div class="xt-fill-details__hero-status" aria-hidden="true">
        <span></span>
        <strong>{{ stitchSurface.statusBar.filteredCount }}</strong>
        <small>当前筛选</small>
      </div>
    </header>

    <div class="xt-second-pass-source-strip" data-testid="second-pass-source-strip" aria-label="数据来源">
      <span class="xt-second-pass-source-strip__item">MES 外部数据</span>
      <span class="xt-second-pass-source-strip__item">人工填报</span>
      <span class="xt-second-pass-source-strip__item">算法数据</span>
    </div>

    <div class="xt-fill-details__audit-ticker" data-testid="data-audit-ticker">
      <article
        v-for="item in auditTickerItems"
        :key="item.key"
        class="xt-fill-details__audit-card"
        :class="`tone-${item.tone}`"
      >
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </article>
    </div>

    <div class="xt-fill-details__main-grid">
      <aside class="xt-fill-details__source-chain" data-testid="source-chain-panel">
        <header class="xt-fill-details__panel-head">
          <h2>口径对照</h2>
          <span>算法主值在前，填报值作对照</span>
        </header>
        <article
          v-for="item in sourceChainCards"
          :key="item.key"
          class="xt-fill-details__source-card"
          :class="`tone-${item.tone}`"
        >
          <div class="xt-fill-details__source-title">{{ item.title }}</div>
          <div class="xt-fill-details__source-row">
            <span>{{ item.primaryLabel }}</span>
            <b>{{ item.primaryValue }}</b>
          </div>
          <div class="xt-fill-details__source-row is-muted">
            <span>{{ item.compareLabel }}</span>
            <b>{{ item.compareValue }}</b>
          </div>
        </article>
      </aside>

      <section class="xt-fill-details__ledger-panel">
        <div class="xt-fill-details__tools">
          <input
            v-model.trim="keyword"
            class="xt-fill-details__search"
            type="search"
            placeholder="搜索机列、责任人、车间、随行卡"
            aria-label="搜索填报明细"
          >
          <select v-model="sourceType" class="xt-fill-details__select" aria-label="筛选来源">
            <option value="">全部来源</option>
            <option v-for="item in sourceOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
          </select>
          <select
            v-if="canChooseWorkshop"
            v-model.number="selectedWorkshopId"
            class="xt-fill-details__select"
            aria-label="筛选车间"
            data-testid="fill-details-workshop-filter"
          >
            <option :value="0">全部车间</option>
            <option v-for="workshop in workshops" :key="workshop.id" :value="workshop.id">{{ workshop.name }}</option>
          </select>
        </div>

        <div class="xt-fill-details__cards">
          <article v-for="item in kpis" :key="item.key">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
            <small>{{ item.unit }}</small>
          </article>
        </div>

        <div v-if="errorText" class="xt-fill-details__error">{{ errorText }}</div>

        <div class="xt-fill-details__table-wrap">
          <table class="xt-fill-details__table">
            <thead>
              <tr>
                <th scope="col">来源</th>
                <th scope="col">车间</th>
                <th scope="col">机列/岗位</th>
                <th scope="col">班次</th>
                <th scope="col">责任人</th>
                <th scope="col">填报时间</th>
                <th scope="col">内容</th>
                <th scope="col">状态</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="loading">
                <td colspan="8" class="xt-fill-details__empty">加载中...</td>
              </tr>
              <tr v-else-if="filteredRows.length === 0">
                <td colspan="8" class="xt-fill-details__empty">暂无明细</td>
              </tr>
              <template v-else>
                <tr v-for="row in filteredRows" :key="row.rowId">
                  <td data-label="来源"><span class="xt-fill-details__tag">{{ row.sourceLabel }}</span></td>
                  <td data-label="车间">{{ row.workshopName }}</td>
                  <td data-label="机列/岗位">
                    <strong>{{ row.machineName }}</strong>
                    <small v-if="row.tracking_card_no">{{ row.tracking_card_no }}</small>
                  </td>
                  <td data-label="班次">{{ row.shiftName }}</td>
                  <td data-label="责任人">
                    <strong>{{ row.responsibleText }}</strong>
                    <small v-if="row.responsibleUsername">{{ row.responsibleUsername }}</small>
                  </td>
                  <td data-label="填报时间">{{ row.submittedText }}</td>
                  <td data-label="内容">{{ row.contentText }}</td>
                  <td data-label="状态">{{ row.statusLabel }}</td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <section class="xt-fill-details__issues" data-testid="issue-queue-panel">
      <article
        v-for="item in issueQueues"
        :key="item.key"
        class="xt-fill-details__issue"
        :class="`tone-${item.tone}`"
      >
        <header>
          <span>{{ item.title }}</span>
          <strong>{{ item.count }}</strong>
        </header>
        <p v-for="line in item.items" :key="line">{{ line }}</p>
      </article>
    </section>

    <section class="xt-fill-details__mes-gap" data-testid="fill-details-mes-gap-panel">
      <header class="xt-fill-details__panel-head">
        <h2>MES 对照异常</h2>
        <span>{{ mesGapRows.length }} 条</span>
      </header>
      <div v-if="mesGapRows.length" class="xt-fill-details__mes-gap-grid">
        <article v-for="row in mesGapRows" :key="rowKey(row)" class="xt-fill-details__mes-gap-row">
          <header>
            <strong>{{ mesGapStatusText(row.status) }}</strong>
            <em>{{ mesGapSequenceText(row) }}</em>
          </header>
          <b>{{ row.tracking_card_no || row.batch_no || '-' }}</b>
          <span>{{ row.workshop_name || '-' }} · {{ row.process_name || '-' }}</span>
          <div class="xt-fill-details__mes-gap-tags">
            <i>{{ row.customer_alias || '客户未同步' }}</i>
            <i>{{ row.alloy_grade || '合金未同步' }}</i>
            <i>{{ row.material_state || '状态未同步' }}</i>
          </div>
          <small>{{ mesGapSpecText(row) }}</small>
          <small>{{ mesGapWeightText(row) }}</small>
          <small>{{ mesGapMachineText(row) }}</small>
          <small>{{ mesGapBindingText(row) }}</small>
          <small>{{ mesGapOperatorText(row) }}</small>
          <p>{{ mesGapCauseText(row) }}</p>
        </article>
      </div>
      <p v-else class="xt-fill-details__empty">暂无 MES 对照异常</p>
    </section>

    <footer class="xt-fill-details__bottom-status" data-testid="stitch-bottom-status" aria-label="系统状态">
      <span
        v-for="item in bottomStatusItems"
        :key="item.key"
        class="xt-fill-details__status-pill"
        :class="`tone-${item.tone}`"
      >
        <i></i>
        <b>{{ item.label }}</b>
        <strong>{{ item.value }}</strong>
      </span>
    </footer>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { Download } from '@element-plus/icons-vue'

import DateSwitcher from '../../../components/manage/DateSwitcher.vue'
import { fetchDailyProduction } from '../../../api/dashboard.js'
import { exportMissingReportExcel, fetchLiveAggregation, fetchLiveFillDetails, fetchMesFillGaps } from '../../../api/realtime.js'
import { fetchWorkshops } from '../../../api/master.js'
import { useAuthStore } from '../../../stores/auth.js'
import { inferLastCompletedBusinessDate } from '../../../utils/shiftClock.js'
import { downloadBlob } from '../../../utils/downloadBlob.js'
import { filterActiveWorkshopRows } from '../../../utils/activeWorkshops.js'
import { buildFillDetailsStitchSurface } from '../../../utils/stitchManageSurface.js'
import {
  buildAuditTickerItems,
  buildFillLedgerRows,
  buildIssueQueues,
  buildSourceChainCards,
  filterFillLedgerRows,
  MISSING_AUDIT_VALUE,
} from '../../../utils/manageFillDetailsAudit.js'

const targetDate = ref(inferLastCompletedBusinessDate())
const auth = useAuthStore()
const loading = ref(false)
const errorText = ref('')
const freshness = ref('yellow')
const keyword = ref('')
const sourceType = ref('')
const selectedWorkshopId = ref(0)
const rows = ref([])
const summary = ref({})
const dailyOverview = ref({})
const liveAggregation = ref({})
const mesGapData = ref({})
const workshops = ref([])
const workshopsLoaded = ref(false)
const exportingMissingReport = ref(false)

const MES_GAP_STATUS_LABELS = {
  missing_local_entry: 'MES有工序本地未填',
  mes_batch_unmapped: '批号未映射',
  local_entry_unassigned: '本地未归机列',
  weight_mismatch: '重量不一致',
}

const MATERIAL_CATEGORY_LABELS = {
  cold_roll_pass: '冷轧道次',
  hot_roll_process: '热轧工序',
  cast_roll_process: '铸轧工序',
  casting_ingot_reference: '铸锭参考',
  billet_reference: '坯料参考',
  coil_process: '卷材工序',
}

const sourceOptions = [
  { value: 'machine_energy', label: '机台能耗' },
  { value: 'work_order_entry', label: '机台填报' },
  { value: 'owner_daily', label: '每日一录' },
  { value: 'mobile_shift_report', label: '班次汇总' }
]

const rawLedgerRows = computed(() => buildFillLedgerRows(rows.value))
const rawAuditTickerItems = computed(() => buildAuditTickerItems({
  dailyOverview: dailyOverview.value,
  liveAggregation: liveAggregation.value,
}))
const rawSourceChainCards = computed(() => buildSourceChainCards(dailyOverview.value))
const rawIssueQueues = computed(() => buildIssueQueues({
  dailyOverview: dailyOverview.value,
  liveAggregation: liveAggregation.value,
}))
const rawFilteredRows = computed(() => filterFillLedgerRows(rawLedgerRows.value, {
  keyword: keyword.value,
  sourceType: sourceType.value,
}))
const hasLedgerEnergy = computed(() => rawLedgerRows.value.some((row) => {
  if (row.energy_kwh !== null && row.energy_kwh !== undefined) return true
  return (row.metrics || []).some((item) => /electric|energy|用电|能耗/i.test(`${item?.key || ''} ${item?.label || ''}`) && item?.value != null)
}))
const hasLedgerGas = computed(() => rawLedgerRows.value.some((row) => row.gas_m3 !== null && row.gas_m3 !== undefined))
const canChooseWorkshop = computed(() => auth.isAdmin || (auth.hasGlobalReviewScope && !auth.isWorkshopDirector))

const rawKpis = computed(() => [
  { key: 'entry', label: '明细', value: summary.value.entry_count ?? rawLedgerRows.value.length, unit: '条' },
  { key: 'machine', label: '机列', value: summary.value.machine_count ?? 0, unit: '台' },
  { key: 'owner', label: '责任人', value: summary.value.owner_count ?? 0, unit: '人' },
  { key: 'output', label: '产量', value: formatNumber(summary.value.output, 2), unit: '吨' },
  { key: 'energy', label: '用电', value: hasLedgerEnergy.value ? formatNumber(summary.value.energy_kwh, 1) : MISSING_AUDIT_VALUE, unit: hasLedgerEnergy.value ? 'kWh' : '' },
  { key: 'gas', label: '天然气', value: hasLedgerGas.value ? formatNumber(summary.value.gas_m3, 1) : MISSING_AUDIT_VALUE, unit: hasLedgerGas.value ? 'm³' : '' }
])

const stitchSurface = computed(() => buildFillDetailsStitchSurface({
  targetDate: targetDate.value,
  kpiItems: rawKpis.value,
  auditTicker: rawAuditTickerItems.value,
  sourceChain: rawSourceChainCards.value,
  issueQueues: rawIssueQueues.value,
  ledgerRows: rawLedgerRows.value,
  filteredRows: rawFilteredRows.value,
  runtimeState: {
    loading: loading.value,
    errorText: errorText.value,
  },
}))
const auditTickerItems = computed(() => stitchSurface.value.auditTicker)
const sourceChainCards = computed(() => stitchSurface.value.sourceChain)
const issueQueues = computed(() => stitchSurface.value.issueQueues)
const filteredRows = computed(() => stitchSurface.value.filteredRows)
const kpis = computed(() => stitchSurface.value.kpiStrip)
const bottomStatusItems = computed(() => stitchSurface.value.bottomStatus)
const mesGapRows = computed(() => {
  const items = Array.isArray(mesGapData.value?.items) ? mesGapData.value.items : []
  return items.filter((row) => row.status && row.status !== 'matched').slice(0, 6)
})

function formatNumber(value, digits = 2) {
  const num = Number(value)
  if (!Number.isFinite(num)) return '-'
  return num.toLocaleString('zh-CN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  })
}

function scopedParams(extra = {}) {
  return selectedWorkshopId.value ? { ...extra, workshop_id: selectedWorkshopId.value } : extra
}

function mesGapStatusText(status) {
  return MES_GAP_STATUS_LABELS[status] || status || '-'
}

function mesGapWeightText(row) {
  const mes = formatNumber(row?.mes_output_weight, 1)
  const local = formatNumber(row?.local_output_weight, 1)
  return `MES ${mes} kg / 本地 ${local} kg`
}

function mesGapSequenceText(row) {
  const sequence = row?.process_sequence
  if (typeof sequence === 'string') return sequence
  return sequence?.pass_label || MATERIAL_CATEGORY_LABELS[row?.material_category] || '工序'
}

function mesGapSpecText(row) {
  const input = row?.input_spec || '-'
  const output = row?.output_spec || '-'
  return `规格 ${input} -> ${output}`
}

function mesGapMachineText(row) {
  const mes = row?.mes_machine_name || '-'
  const resolved = row?.mes_resolved_machine_name || '-'
  const local = row?.local_machine_name || '-'
  return `机列 MES:${mes} / 归属:${resolved} / 本地:${local}`
}

function mesGapBindingText(row) {
  const source = row?.mes_machine_binding_source || '未同步'
  const confidence = row?.mes_machine_binding_confidence || '未知'
  return `匹配 ${source} / 可信度 ${confidence}`
}

function mesGapOperatorText(row) {
  const worker = row?.mes_worker_name || '操作人未同步'
  const seenAt = row?.mes_last_seen_at ? dayjs(row.mes_last_seen_at).format('MM-DD HH:mm') : '同步时间未知'
  return `操作 ${worker} / 同步 ${seenAt}`
}

function mesGapCauseText(row) {
  return row?.gap_cause || mesGapStatusText(row?.status)
}

function rowKey(row) {
  return `${row.status || 'gap'}-${row.mes_process_record_id || row.local_entry_id || row.tracking_card_no || row.batch_no || 'unknown'}`
}

async function loadWorkshops() {
  if (workshopsLoaded.value || !canChooseWorkshop.value) return
  try {
    workshops.value = filterActiveWorkshopRows(await fetchWorkshops({ limit: 300 }))
  } catch {
    workshops.value = []
  } finally {
    workshopsLoaded.value = true
  }
}

async function load() {
  loading.value = true
  errorText.value = ''
  try {
    await loadWorkshops()
    const [detailResult, dailyResult, liveResult, mesGapResult] = await Promise.allSettled([
      fetchLiveFillDetails(scopedParams({ business_date: targetDate.value, limit: 2000 })),
      fetchDailyProduction({ target_date: targetDate.value }),
      fetchLiveAggregation(scopedParams({ business_date: targetDate.value })),
      fetchMesFillGaps(scopedParams({ business_date: targetDate.value })),
    ])

    if (detailResult.status === 'fulfilled') {
      rows.value = Array.isArray(detailResult.value.items) ? detailResult.value.items : []
      summary.value = detailResult.value.summary || {}
    } else {
      rows.value = []
      summary.value = {}
      errorText.value = detailResult.reason?.response?.data?.detail || detailResult.reason?.message || '加载填报明细失败'
    }

    dailyOverview.value = dailyResult.status === 'fulfilled' ? dailyResult.value || {} : {}
    liveAggregation.value = liveResult.status === 'fulfilled' ? liveResult.value || {} : {}
    mesGapData.value = mesGapResult.status === 'fulfilled' ? mesGapResult.value || {} : {}
    freshness.value = detailResult.status === 'rejected'
      ? 'red'
      : (dailyResult.status === 'rejected' || liveResult.status === 'rejected' || mesGapResult.status === 'rejected' ? 'yellow' : 'green')
  } catch (error) {
    rows.value = []
    summary.value = {}
    dailyOverview.value = {}
    liveAggregation.value = {}
    mesGapData.value = {}
    freshness.value = 'red'
    errorText.value = error?.response?.data?.detail || error?.message || '加载填报明细失败'
  } finally {
    loading.value = false
  }
}

function stepDate(delta) {
  targetDate.value = dayjs(targetDate.value).add(delta, 'day').format('YYYY-MM-DD')
}

function pickDate(dateValue) {
  targetDate.value = dateValue
}

async function downloadMissingReport() {
  exportingMissingReport.value = true
  try {
    const data = await exportMissingReportExcel(scopedParams({ business_date: targetDate.value }))
    downloadBlob(data, `缺报明细-${targetDate.value}.xlsx`)
    ElMessage.success('缺报Excel已导出')
  } catch (error) {
    ElMessage.error(error?.response?.data?.detail || '缺报Excel导出失败')
  } finally {
    exportingMissingReport.value = false
  }
}

watch(targetDate, load)
watch(selectedWorkshopId, load)
load()
</script>

<style scoped>
.xt-fill-details {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: var(--xt-space-4);
}

.xt-fill-details::before {
  position: fixed;
  inset: 0;
  z-index: -1;
  background:
    radial-gradient(circle at 16% 0%, color-mix(in srgb, var(--xt-primary) 13%, transparent), transparent 30%),
    linear-gradient(color-mix(in srgb, var(--xt-primary) 5%, transparent) 1px, transparent 1px),
    linear-gradient(90deg, color-mix(in srgb, var(--xt-primary) 5%, transparent) 1px, transparent 1px);
  background-size: auto, 34px 34px, 34px 34px;
  content: "";
  pointer-events: none;
}

.xt-fill-details__hero,
.xt-fill-details__audit-card,
.xt-fill-details__source-card,
.xt-fill-details__ledger-panel,
.xt-fill-details__issue,
.xt-fill-details__mes-gap {
  position: relative;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--xt-primary) 18%, var(--xt-border));
  border-radius: var(--xt-radius-xl);
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--xt-text-inverse) 7%, transparent), transparent),
    color-mix(in srgb, var(--xt-bg-ink-panel) 88%, var(--xt-bg-panel));
  box-shadow:
    inset 0 1px 0 color-mix(in srgb, var(--xt-text-inverse) 8%, transparent),
    0 12px 28px color-mix(in srgb, var(--xt-bg-ink) 34%, transparent);
}

.xt-fill-details__hero::before,
.xt-fill-details__audit-card::before,
.xt-fill-details__source-card::before,
.xt-fill-details__ledger-panel::before,
.xt-fill-details__issue::before,
.xt-fill-details__mes-gap::before {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 92% 10%, color-mix(in srgb, var(--xt-primary) 14%, transparent), transparent 34%),
    linear-gradient(135deg, color-mix(in srgb, var(--xt-primary) 7%, transparent), transparent 48%);
  content: "";
  pointer-events: none;
}

.xt-fill-details__hero::after,
.xt-fill-details__ledger-panel::after {
  position: absolute;
  top: 0;
  right: var(--xt-space-4);
  left: var(--xt-space-4);
  height: 1px;
  background: linear-gradient(90deg, transparent, color-mix(in srgb, var(--xt-primary) 18%, transparent), transparent);
  content: "";
  pointer-events: none;
}

.xt-fill-details__hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto auto;
  align-items: center;
  gap: var(--xt-space-4);
  min-height: 132px;
  padding: var(--xt-space-5);
}

.xt-fill-details__hero-copy,
.xt-fill-details__hero :deep(.xt-date-switcher),
.xt-fill-details__export,
.xt-fill-details__hero-status {
  position: relative;
  z-index: 1;
}

.xt-fill-details__hero h1 {
  margin: 0;
  color: var(--xt-text-inverse);
  font-family: var(--xt-font-display);
  font-size: clamp(var(--xt-text-2xl), 3vw, 42px);
  font-weight: 900;
  letter-spacing: -0.04em;
}

.xt-fill-details__export {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  min-height: 42px;
  padding: 0 var(--xt-space-3);
  border: 1px solid color-mix(in srgb, var(--xt-primary) 32%, var(--xt-border));
  border-radius: var(--xt-radius-lg);
  background: color-mix(in srgb, var(--xt-primary) 16%, var(--xt-bg-ink));
  color: var(--xt-text-inverse);
  cursor: pointer;
  font-size: var(--xt-text-sm);
  font-weight: 900;
  white-space: nowrap;
}

.xt-fill-details__export:disabled {
  cursor: wait;
  opacity: 0.62;
}

.xt-fill-details__hero-status {
  display: grid;
  min-width: 98px;
  justify-items: center;
  gap: 2px;
  padding: var(--xt-space-3);
  border: 1px solid color-mix(in srgb, var(--xt-primary) 24%, var(--xt-border));
  border-radius: var(--xt-radius-lg);
  background: color-mix(in srgb, var(--xt-bg-ink) 42%, transparent);
}

.xt-fill-details__hero-status span {
  width: 8px;
  height: 8px;
  border-radius: var(--xt-radius-pill);
  background: var(--xt-primary);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--xt-primary) 18%, transparent);
}

.xt-fill-details__hero-status strong {
  color: var(--xt-text-inverse);
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-xl);
  font-weight: 900;
}

.xt-fill-details__hero-status small {
  color: color-mix(in srgb, var(--xt-text-inverse) 52%, transparent);
  font-size: var(--xt-text-xs);
  font-weight: 850;
}

.xt-fill-details__eyebrow {
  display: block;
  margin-bottom: 4px;
  color: color-mix(in srgb, var(--xt-primary) 72%, var(--xt-text-inverse));
  font-size: var(--xt-text-xs);
  font-weight: 900;
  letter-spacing: 0.08em;
}

.xt-fill-details__audit-ticker {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: var(--xt-space-2);
}

.xt-fill-details__audit-card {
  display: grid;
  gap: 4px;
  min-height: 112px;
  padding: var(--xt-space-3);
}

.xt-fill-details__audit-card > span,
.xt-fill-details__source-row span,
.xt-fill-details__issue p {
  position: relative;
  z-index: 1;
  color: color-mix(in srgb, var(--xt-text-inverse) 50%, transparent);
  font-size: var(--xt-text-xs);
  font-weight: 800;
}

.xt-fill-details__audit-card strong {
  position: relative;
  z-index: 1;
  color: var(--xt-text-inverse);
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-lg);
  font-weight: 900;
  font-variant-numeric: tabular-nums;
}

.xt-fill-details__audit-card.tone-warning,
.xt-fill-details__source-card.tone-warning,
.xt-fill-details__issue.tone-warning {
  border-color: color-mix(in srgb, var(--xt-warning) 46%, var(--xt-border));
}

.xt-fill-details__audit-card.tone-danger,
.xt-fill-details__source-card.tone-danger,
.xt-fill-details__issue.tone-danger {
  border-color: color-mix(in srgb, var(--xt-danger) 48%, var(--xt-border));
}

.xt-fill-details__audit-card.tone-success,
.xt-fill-details__source-card.tone-success {
  border-color: color-mix(in srgb, var(--xt-success) 48%, var(--xt-border));
}

.xt-fill-details__main-grid {
  display: grid;
  grid-template-columns: minmax(280px, 0.34fr) minmax(0, 0.66fr);
  gap: var(--xt-space-4);
  align-items: start;
}

.xt-fill-details__source-chain,
.xt-fill-details__ledger-panel {
  display: grid;
  gap: var(--xt-space-3);
  min-width: 0;
}

.xt-fill-details__ledger-panel {
  padding: var(--xt-space-4);
}

.xt-fill-details__panel-head {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--xt-space-3);
}

.xt-fill-details__panel-head h2 {
  margin: 0;
  color: var(--xt-text-inverse);
  font-size: var(--xt-text-lg);
  font-weight: 900;
}

.xt-fill-details__panel-head span {
  color: color-mix(in srgb, var(--xt-text-inverse) 50%, transparent);
  font-size: var(--xt-text-xs);
  font-weight: 800;
}

.xt-fill-details__source-card {
  display: grid;
  gap: var(--xt-space-2);
  padding: var(--xt-space-3);
}

.xt-fill-details__source-title {
  position: relative;
  z-index: 1;
  color: var(--xt-text-inverse);
  font-size: var(--xt-text-sm);
  font-weight: 900;
}

.xt-fill-details__source-row {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--xt-space-2);
}

.xt-fill-details__source-row b {
  color: var(--xt-text-inverse);
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-lg);
  font-weight: 900;
  font-variant-numeric: tabular-nums;
}

.xt-fill-details__source-row.is-muted b {
  color: color-mix(in srgb, var(--xt-text-inverse) 58%, transparent);
  font-size: var(--xt-text-base);
}

.xt-fill-details__tools {
  position: relative;
  z-index: 1;
  display: flex;
  gap: var(--xt-space-2);
  flex-wrap: wrap;
}

.xt-fill-details__search,
.xt-fill-details__select {
  min-height: 42px;
  border: 1px solid color-mix(in srgb, var(--xt-primary) 18%, var(--xt-border));
  border-radius: var(--xt-radius-lg);
  background: color-mix(in srgb, var(--xt-bg-ink) 48%, var(--xt-bg-panel));
  color: var(--xt-text-inverse);
  font-size: var(--xt-text-sm);
  box-shadow: inset 0 -1px 0 color-mix(in srgb, var(--xt-primary) 18%, transparent);
}

.xt-fill-details__search:focus,
.xt-fill-details__select:focus {
  outline: 2px solid color-mix(in srgb, var(--xt-primary) 40%, transparent);
  outline-offset: 2px;
}

.xt-fill-details__search::placeholder {
  color: color-mix(in srgb, var(--xt-text-inverse) 42%, transparent);
}

.xt-fill-details__search {
  flex: 1 1 260px;
  padding: 0 var(--xt-space-3);
}

.xt-fill-details__select {
  flex: 0 0 150px;
  padding: 0 var(--xt-space-2);
}

.xt-fill-details__cards {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: var(--xt-space-2);
}

.xt-fill-details__cards article {
  display: grid;
  gap: 3px;
  min-height: 92px;
  padding: var(--xt-space-3);
  border: 1px solid color-mix(in srgb, var(--xt-primary) 14%, var(--xt-border));
  border-radius: var(--xt-radius-lg);
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--xt-text-inverse) 6%, transparent), transparent),
    color-mix(in srgb, var(--xt-bg-ink) 34%, transparent);
}

.xt-fill-details__cards span,
.xt-fill-details__cards small {
  color: color-mix(in srgb, var(--xt-text-inverse) 48%, transparent);
  font-size: var(--xt-text-xs);
  font-weight: 800;
}

.xt-fill-details__cards strong {
  color: var(--xt-text-inverse);
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-xl);
  font-weight: 900;
  font-variant-numeric: tabular-nums;
}

.xt-fill-details__error {
  position: relative;
  z-index: 1;
  padding: var(--xt-space-2) var(--xt-space-3);
  border: 1px solid color-mix(in srgb, var(--xt-danger) 42%, var(--xt-border));
  border-radius: var(--xt-radius-md);
  background: color-mix(in srgb, var(--xt-danger-light) 10%, var(--xt-bg-panel));
  color: var(--xt-danger);
  font-size: var(--xt-text-sm);
}

.xt-fill-details__table-wrap {
  position: relative;
  z-index: 1;
  overflow: auto;
  border: 1px solid color-mix(in srgb, var(--xt-primary) 15%, var(--xt-border));
  border-radius: var(--xt-radius-lg);
  background: color-mix(in srgb, var(--xt-bg-ink) 50%, var(--xt-bg-panel));
}

.xt-fill-details__table {
  width: 100%;
  min-width: 980px;
  border-collapse: collapse;
  font-size: var(--xt-text-sm);
}

.xt-fill-details__table th,
.xt-fill-details__table td {
  padding: var(--xt-space-2) var(--xt-space-3);
  border-bottom: 1px solid color-mix(in srgb, var(--xt-primary) 8%, var(--xt-border));
  text-align: left;
  vertical-align: top;
  color: color-mix(in srgb, var(--xt-text-inverse) 78%, transparent);
}

.xt-fill-details__table th {
  color: color-mix(in srgb, var(--xt-text-inverse) 48%, transparent);
  font-size: var(--xt-text-xs);
  font-weight: 900;
  letter-spacing: 0.06em;
  white-space: nowrap;
}

.xt-fill-details__table tbody tr {
  transition:
    background-color var(--xt-motion-fast) var(--xt-ease),
    transform var(--xt-motion-fast) var(--xt-ease);
}

@media (hover: hover) {
  .xt-fill-details__table tbody tr:hover {
    background: color-mix(in srgb, var(--xt-primary) 6%, transparent);
    transform: translateX(2px);
  }
}

.xt-fill-details__table td strong {
  display: block;
  color: var(--xt-text-inverse);
  font-weight: 900;
}

.xt-fill-details__table td small {
  display: block;
  margin-top: 2px;
  color: color-mix(in srgb, var(--xt-text-inverse) 44%, transparent);
  font-size: var(--xt-text-xs);
}

.xt-fill-details__tag {
  display: inline-flex;
  padding: 2px 8px;
  border: 1px solid color-mix(in srgb, var(--xt-primary) 24%, var(--xt-border));
  border-radius: var(--xt-radius-pill);
  background: color-mix(in srgb, var(--xt-primary-light) 8%, transparent);
  color: color-mix(in srgb, var(--xt-primary) 82%, var(--xt-text-inverse));
  font-size: var(--xt-text-xs);
  font-weight: 900;
  white-space: nowrap;
}

.xt-fill-details__issues {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--xt-space-2);
}

.xt-fill-details__mes-gap {
  display: grid;
  gap: var(--xt-space-3);
  padding: var(--xt-space-4);
}

.xt-fill-details__mes-gap-grid {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--xt-space-2);
}

.xt-fill-details__mes-gap-row {
  display: grid;
  gap: 8px;
  min-width: 0;
  padding: var(--xt-space-3);
  border: 1px solid color-mix(in srgb, var(--xt-warning) 28%, var(--xt-border));
  border-radius: var(--xt-radius-lg);
  background: color-mix(in srgb, var(--xt-warning) 8%, transparent);
}

.xt-fill-details__mes-gap-row header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-2);
}

.xt-fill-details__mes-gap-row strong,
.xt-fill-details__mes-gap-row b {
  color: var(--xt-text-inverse);
  font-weight: 900;
  overflow-wrap: anywhere;
}

.xt-fill-details__mes-gap-row em {
  padding: 2px 7px;
  border: 1px solid color-mix(in srgb, var(--xt-primary) 28%, transparent);
  border-radius: var(--xt-radius-pill);
  color: color-mix(in srgb, var(--xt-primary) 78%, var(--xt-text-inverse));
  font-size: var(--xt-text-xs);
  font-style: normal;
  font-weight: 900;
  white-space: nowrap;
}

.xt-fill-details__mes-gap-row span,
.xt-fill-details__mes-gap-row small {
  color: color-mix(in srgb, var(--xt-text-inverse) 54%, transparent);
  font-size: var(--xt-text-xs);
  font-weight: 800;
  line-height: 1.55;
  overflow-wrap: anywhere;
}

.xt-fill-details__mes-gap-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.xt-fill-details__mes-gap-tags i {
  padding: 2px 7px;
  border-radius: var(--xt-radius-pill);
  background: color-mix(in srgb, var(--xt-primary-light) 8%, transparent);
  color: color-mix(in srgb, var(--xt-text-inverse) 68%, transparent);
  font-size: var(--xt-text-xs);
  font-style: normal;
  font-weight: 850;
}

.xt-fill-details__mes-gap-row p {
  margin: 0;
  padding: var(--xt-space-2);
  border-radius: var(--xt-radius-md);
  background: color-mix(in srgb, var(--xt-bg-ink) 32%, transparent);
  color: color-mix(in srgb, var(--xt-warning) 82%, var(--xt-text-inverse));
  font-size: var(--xt-text-xs);
  font-weight: 900;
  overflow-wrap: anywhere;
}

.xt-fill-details__bottom-status {
  position: relative;
  z-index: 1;
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--xt-space-2);
  padding: var(--xt-space-3);
  border: 1px solid color-mix(in srgb, var(--xt-primary) 18%, var(--xt-border));
  border-radius: var(--xt-radius-lg);
  background:
    linear-gradient(90deg, color-mix(in srgb, var(--xt-primary-light) 10%, transparent), transparent),
    color-mix(in srgb, var(--xt-bg-ink) 58%, var(--xt-bg-panel));
}

.xt-fill-details__status-pill {
  display: inline-flex;
  align-items: center;
  gap: var(--xt-space-2);
  min-height: 34px;
  padding: 0 var(--xt-space-3);
  border: 1px solid color-mix(in srgb, var(--xt-primary) 14%, transparent);
  border-radius: var(--xt-radius-pill);
  color: color-mix(in srgb, var(--xt-text-inverse) 74%, transparent);
  font-size: var(--xt-text-xs);
  font-weight: 850;
}

.xt-fill-details__status-pill i {
  width: 7px;
  height: 7px;
  border-radius: var(--xt-radius-pill);
  background: currentColor;
  box-shadow: 0 0 0 3px color-mix(in srgb, currentColor 18%, transparent);
}

.xt-fill-details__status-pill b {
  color: color-mix(in srgb, var(--xt-text-inverse) 46%, transparent);
}

.xt-fill-details__status-pill strong {
  color: var(--xt-text-inverse);
  font-family: var(--xt-font-number);
  font-variant-numeric: tabular-nums;
}

.xt-fill-details__status-pill.tone-success { color: var(--xt-success); }
.xt-fill-details__status-pill.tone-warning { color: var(--xt-warning); }
.xt-fill-details__status-pill.tone-danger { color: var(--xt-danger); }

.xt-fill-details__issue {
  display: grid;
  gap: var(--xt-space-2);
  min-height: 138px;
  padding: var(--xt-space-3);
}

.xt-fill-details__issue header {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-2);
}

.xt-fill-details__issue header span {
  color: color-mix(in srgb, var(--xt-text-inverse) 58%, transparent);
  font-size: var(--xt-text-xs);
  font-weight: 900;
}

.xt-fill-details__issue header strong {
  color: var(--xt-text-inverse);
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-2xl);
  font-weight: 900;
  font-variant-numeric: tabular-nums;
}

.xt-fill-details__issue p {
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.xt-fill-details__empty {
  text-align: center;
  color: color-mix(in srgb, var(--xt-text-inverse) 52%, transparent);
}

@media (max-width: 1120px) {
  .xt-fill-details__audit-ticker,
  .xt-fill-details__cards {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 920px) {
  .xt-fill-details__hero {
    grid-template-columns: 1fr;
    align-items: stretch;
  }

  .xt-fill-details__audit-ticker,
  .xt-fill-details__mes-gap-grid,
  .xt-fill-details__issues {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .xt-fill-details__main-grid {
    grid-template-columns: 1fr;
  }

  .xt-fill-details__cards {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .xt-fill-details__select {
    flex: 1 1 160px;
  }
}

@media (max-width: 620px) {
  .xt-fill-details__audit-ticker,
  .xt-fill-details__mes-gap-grid,
  .xt-fill-details__issues,
  .xt-fill-details__cards {
    grid-template-columns: 1fr;
  }

  .xt-fill-details__hero,
  .xt-fill-details__ledger-panel {
    padding: var(--xt-space-3);
  }

  .xt-fill-details__table {
    min-width: 0;
  }

  .xt-fill-details__table thead {
    display: none;
  }

  .xt-fill-details__table,
  .xt-fill-details__table tbody,
  .xt-fill-details__table tr,
  .xt-fill-details__table td {
    display: block;
  }

  .xt-fill-details__table tr {
    margin: var(--xt-space-2);
    border: 1px solid color-mix(in srgb, var(--xt-primary) 14%, var(--xt-border));
    border-radius: var(--xt-radius-lg);
    background: color-mix(in srgb, var(--xt-bg-ink) 24%, transparent);
  }

  .xt-fill-details__table td {
    display: grid;
    grid-template-columns: 86px minmax(0, 1fr);
    gap: var(--xt-space-2);
    border-bottom: 1px solid color-mix(in srgb, var(--xt-primary) 6%, var(--xt-border));
  }

  .xt-fill-details__table td::before {
    color: color-mix(in srgb, var(--xt-text-inverse) 44%, transparent);
    content: attr(data-label);
    font-size: var(--xt-text-xs);
    font-weight: 900;
  }
}

@media (prefers-reduced-motion: reduce) {
  .xt-fill-details__table tbody tr {
    transition: none;
  }
}
</style>
