<template>
  <section
    class="xt-fill-details"
    data-testid="manage-fill-details"
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
      <div class="xt-fill-details__hero-status" aria-hidden="true">
        <span></span>
        <strong>{{ stitchSurface.statusBar.filteredCount }}</strong>
        <small>当前筛选</small>
      </div>
    </header>

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

import DateSwitcher from '../../../components/manage/DateSwitcher.vue'
import { fetchDailyProduction } from '../../../api/dashboard.js'
import { fetchLiveAggregation, fetchLiveFillDetails } from '../../../api/realtime.js'
import { fetchWorkshops } from '../../../api/master.js'
import { useAuthStore } from '../../../stores/auth.js'
import { inferBusinessDate } from '../../../utils/shiftClock.js'
import { buildFillDetailsStitchSurface } from '../../../utils/stitchManageSurface.js'
import {
  buildAuditTickerItems,
  buildFillLedgerRows,
  buildIssueQueues,
  buildSourceChainCards,
  filterFillLedgerRows,
  MISSING_AUDIT_VALUE,
} from '../../../utils/manageFillDetailsAudit.js'

const targetDate = ref(inferBusinessDate())
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
const workshops = ref([])
const workshopsLoaded = ref(false)

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

async function loadWorkshops() {
  if (workshopsLoaded.value || !canChooseWorkshop.value) return
  try {
    workshops.value = await fetchWorkshops({ limit: 300 })
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
    const [detailResult, dailyResult, liveResult] = await Promise.allSettled([
      fetchLiveFillDetails(scopedParams({ business_date: targetDate.value, limit: 2000 })),
      fetchDailyProduction({ target_date: targetDate.value }),
      fetchLiveAggregation(scopedParams({ business_date: targetDate.value })),
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
    freshness.value = detailResult.status === 'rejected'
      ? 'red'
      : (dailyResult.status === 'rejected' || liveResult.status === 'rejected' ? 'yellow' : 'green')
  } catch (error) {
    rows.value = []
    summary.value = {}
    dailyOverview.value = {}
    liveAggregation.value = {}
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
.xt-fill-details__issue {
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
.xt-fill-details__issue::before {
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
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  gap: var(--xt-space-4);
  min-height: 132px;
  padding: var(--xt-space-5);
}

.xt-fill-details__hero-copy,
.xt-fill-details__hero :deep(.xt-date-switcher),
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
