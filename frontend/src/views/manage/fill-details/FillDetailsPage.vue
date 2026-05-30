<template>
  <section class="xt-fill-details" data-testid="manage-fill-details">
    <header class="xt-fill-details__header">
      <div>
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
                  <td><span class="xt-fill-details__tag">{{ row.sourceLabel }}</span></td>
                  <td>{{ row.workshopName }}</td>
                  <td>
                    <strong>{{ row.machineName }}</strong>
                    <small v-if="row.tracking_card_no">{{ row.tracking_card_no }}</small>
                  </td>
                  <td>{{ row.shiftName }}</td>
                  <td>
                    <strong>{{ row.responsibleText }}</strong>
                    <small v-if="row.responsibleUsername">{{ row.responsibleUsername }}</small>
                  </td>
                  <td>{{ row.submittedText }}</td>
                  <td>{{ row.contentText }}</td>
                  <td>{{ row.statusLabel }}</td>
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
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import dayjs from 'dayjs'

import DateSwitcher from '../../../components/manage/DateSwitcher.vue'
import { fetchDailyProduction } from '../../../api/dashboard.js'
import { fetchLiveAggregation, fetchLiveFillDetails } from '../../../api/realtime.js'
import { inferBusinessDate } from '../../../utils/shiftClock.js'
import {
  buildAuditTickerItems,
  buildFillLedgerRows,
  buildIssueQueues,
  buildSourceChainCards,
  filterFillLedgerRows,
  MISSING_AUDIT_VALUE,
} from '../../../utils/manageFillDetailsAudit.js'

const targetDate = ref(inferBusinessDate())
const loading = ref(false)
const errorText = ref('')
const freshness = ref('yellow')
const keyword = ref('')
const sourceType = ref('')
const rows = ref([])
const summary = ref({})
const dailyOverview = ref({})
const liveAggregation = ref({})

const sourceOptions = [
  { value: 'machine_energy', label: '机台能耗' },
  { value: 'work_order_entry', label: '机台填报' },
  { value: 'owner_daily', label: '每日一录' },
  { value: 'mobile_shift_report', label: '班次汇总' },
  { value: 'mes_projection', label: '外部 MES' }
]

const ledgerRows = computed(() => buildFillLedgerRows(rows.value))
const auditTickerItems = computed(() => buildAuditTickerItems({
  dailyOverview: dailyOverview.value,
  liveAggregation: liveAggregation.value,
}))
const sourceChainCards = computed(() => buildSourceChainCards(dailyOverview.value))
const issueQueues = computed(() => buildIssueQueues({
  dailyOverview: dailyOverview.value,
  liveAggregation: liveAggregation.value,
}))
const filteredRows = computed(() => filterFillLedgerRows(ledgerRows.value, {
  keyword: keyword.value,
  sourceType: sourceType.value,
}))
const hasLedgerEnergy = computed(() => ledgerRows.value.some((row) => {
  if (row.energy_kwh !== null && row.energy_kwh !== undefined) return true
  return (row.metrics || []).some((item) => /electric|energy|用电|能耗/i.test(`${item?.key || ''} ${item?.label || ''}`) && item?.value != null)
}))
const hasLedgerGas = computed(() => ledgerRows.value.some((row) => row.gas_m3 !== null && row.gas_m3 !== undefined))

const kpis = computed(() => [
  { key: 'entry', label: '明细', value: summary.value.entry_count ?? ledgerRows.value.length, unit: '条' },
  { key: 'machine', label: '机列', value: summary.value.machine_count ?? 0, unit: '台' },
  { key: 'owner', label: '责任人', value: summary.value.owner_count ?? 0, unit: '人' },
  { key: 'output', label: '产量', value: formatNumber(summary.value.output, 2), unit: '吨' },
  { key: 'energy', label: '用电', value: hasLedgerEnergy.value ? formatNumber(summary.value.energy_kwh, 1) : MISSING_AUDIT_VALUE, unit: hasLedgerEnergy.value ? 'kWh' : '' },
  { key: 'gas', label: '天然气', value: hasLedgerGas.value ? formatNumber(summary.value.gas_m3, 1) : MISSING_AUDIT_VALUE, unit: hasLedgerGas.value ? 'm³' : '' }
])

function formatNumber(value, digits = 2) {
  const num = Number(value)
  if (!Number.isFinite(num)) return '-'
  return num.toFixed(digits)
}

async function load() {
  loading.value = true
  errorText.value = ''
  try {
    const [detailResult, dailyResult, liveResult] = await Promise.allSettled([
      fetchLiveFillDetails({ business_date: targetDate.value, limit: 2000 }),
      fetchDailyProduction({ target_date: targetDate.value }),
      fetchLiveAggregation({ business_date: targetDate.value }),
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
load()
</script>

<style scoped>
.xt-fill-details { display: flex; flex-direction: column; gap: var(--xt-space-4); }
.xt-fill-details__header { display: flex; align-items: center; justify-content: space-between; gap: var(--xt-space-3); flex-wrap: wrap; }
.xt-fill-details__header h1 { margin: 0; color: var(--xt-text); font-size: var(--xt-text-2xl); font-weight: 850; }
.xt-fill-details__eyebrow {
  display: block;
  margin-bottom: 2px;
  color: var(--xt-text-muted);
  font-size: var(--xt-text-xs);
  font-weight: 850;
  letter-spacing: 0.16em;
}
.xt-fill-details__audit-ticker {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: var(--xt-space-2);
}
.xt-fill-details__audit-card,
.xt-fill-details__source-card,
.xt-fill-details__issue {
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-md);
  background: var(--xt-bg-panel);
}
.xt-fill-details__audit-card {
  display: grid;
  gap: 4px;
  padding: var(--xt-space-3);
}
.xt-fill-details__audit-card span,
.xt-fill-details__source-row span,
.xt-fill-details__issue p { color: var(--xt-text-muted); font-size: var(--xt-text-xs); font-weight: 750; }
.xt-fill-details__audit-card strong {
  color: var(--xt-text);
  font-size: var(--xt-text-lg);
  font-weight: 850;
  font-variant-numeric: tabular-nums;
}
.xt-fill-details__audit-card.tone-warning,
.xt-fill-details__source-card.tone-warning,
.xt-fill-details__issue.tone-warning { border-color: var(--xt-warning, var(--xt-color-warning)); }
.xt-fill-details__audit-card.tone-danger,
.xt-fill-details__source-card.tone-danger,
.xt-fill-details__issue.tone-danger { border-color: var(--xt-danger, var(--xt-color-danger)); }
.xt-fill-details__audit-card.tone-success,
.xt-fill-details__source-card.tone-success { border-color: var(--xt-success, var(--xt-color-success)); }
.xt-fill-details__main-grid {
  display: grid;
  grid-template-columns: minmax(260px, 0.34fr) minmax(0, 0.66fr);
  gap: var(--xt-space-3);
  align-items: start;
}
.xt-fill-details__source-chain,
.xt-fill-details__ledger-panel {
  display: grid;
  gap: var(--xt-space-3);
  min-width: 0;
}
.xt-fill-details__panel-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--xt-space-3);
}
.xt-fill-details__panel-head h2 {
  margin: 0;
  color: var(--xt-text);
  font-size: var(--xt-text-lg);
  font-weight: 850;
}
.xt-fill-details__panel-head span {
  color: var(--xt-text-muted);
  font-size: var(--xt-text-xs);
  font-weight: 750;
}
.xt-fill-details__source-card {
  display: grid;
  gap: var(--xt-space-2);
  padding: var(--xt-space-3);
}
.xt-fill-details__source-title { color: var(--xt-text); font-size: var(--xt-text-sm); font-weight: 850; }
.xt-fill-details__source-row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--xt-space-2);
}
.xt-fill-details__source-row b {
  color: var(--xt-text);
  font-size: var(--xt-text-lg);
  font-weight: 850;
  font-variant-numeric: tabular-nums;
}
.xt-fill-details__source-row.is-muted b {
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-base);
}
.xt-fill-details__tools { display: flex; gap: var(--xt-space-2); flex-wrap: wrap; }
.xt-fill-details__search,
.xt-fill-details__select {
  min-height: 38px;
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-md);
  background: var(--xt-bg-panel);
  color: var(--xt-text);
  font-size: var(--xt-text-sm);
}
.xt-fill-details__search { flex: 1 1 260px; padding: 0 var(--xt-space-3); }
.xt-fill-details__select { flex: 0 0 150px; padding: 0 var(--xt-space-2); }
.xt-fill-details__cards { display: grid; grid-template-columns: repeat(6, minmax(0, 1fr)); gap: var(--xt-space-2); }
.xt-fill-details__cards article {
  display: grid;
  gap: 3px;
  padding: var(--xt-space-3);
  background: var(--xt-bg-panel);
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-md);
}
.xt-fill-details__cards span,
.xt-fill-details__cards small { color: var(--xt-text-muted); font-size: var(--xt-text-xs); }
.xt-fill-details__cards strong { color: var(--xt-text); font-size: var(--xt-text-xl); font-weight: 850; font-variant-numeric: tabular-nums; }
.xt-fill-details__error {
  padding: var(--xt-space-2) var(--xt-space-3);
  background: var(--xt-bg-panel);
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-md);
  color: var(--xt-color-danger);
  font-size: var(--xt-text-sm);
}
.xt-fill-details__table-wrap {
  overflow: auto;
  background: var(--xt-bg-panel);
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-md);
}
.xt-fill-details__table { width: 100%; min-width: 980px; border-collapse: collapse; font-size: var(--xt-text-sm); }
.xt-fill-details__table th,
.xt-fill-details__table td { padding: var(--xt-space-2) var(--xt-space-3); border-bottom: 1px solid var(--xt-border); text-align: left; vertical-align: top; color: var(--xt-text); }
.xt-fill-details__table th { color: var(--xt-text-muted); font-size: var(--xt-text-xs); font-weight: 800; white-space: nowrap; }
.xt-fill-details__table td strong { display: block; font-weight: 800; }
.xt-fill-details__table td small { display: block; margin-top: 2px; color: var(--xt-text-muted); font-size: var(--xt-text-xs); }
.xt-fill-details__tag {
  display: inline-flex;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--xt-bg-muted, rgba(15, 23, 42, 0.06));
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-xs);
  font-weight: 800;
  white-space: nowrap;
}
.xt-fill-details__issues {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--xt-space-2);
}
.xt-fill-details__issue {
  display: grid;
  gap: var(--xt-space-2);
  padding: var(--xt-space-3);
}
.xt-fill-details__issue header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-2);
}
.xt-fill-details__issue header span {
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-xs);
  font-weight: 850;
}
.xt-fill-details__issue header strong {
  color: var(--xt-text);
  font-size: var(--xt-text-2xl);
  font-weight: 850;
  font-variant-numeric: tabular-nums;
}
.xt-fill-details__issue p {
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.xt-fill-details__empty { text-align: center; color: var(--xt-text-muted); }
@media (max-width: 920px) {
  .xt-fill-details__header { align-items: stretch; flex-direction: column; }
  .xt-fill-details__audit-ticker,
  .xt-fill-details__issues { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .xt-fill-details__main-grid { grid-template-columns: 1fr; }
  .xt-fill-details__cards { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .xt-fill-details__select { flex: 1 1 160px; }
}
@media (max-width: 560px) {
  .xt-fill-details__audit-ticker,
  .xt-fill-details__issues,
  .xt-fill-details__cards { grid-template-columns: 1fr; }
}
</style>
