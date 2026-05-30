<template>
  <section class="xt-fill-details" data-testid="manage-fill-details">
    <header class="xt-fill-details__header">
      <h1>填报明细</h1>
      <DateSwitcher
        :model-value="targetDate"
        :loading="loading"
        :freshness="freshness"
        @step="stepDate"
        @refresh="load"
        @pick="pickDate"
      />
    </header>

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
            <tr v-for="row in filteredRows" :key="row.row_id">
              <td><span class="xt-fill-details__tag">{{ row.source_label || row.source_type || '-' }}</span></td>
              <td>{{ row.workshop_name || '-' }}</td>
              <td>
                <strong>{{ row.machine_name || '-' }}</strong>
                <small v-if="row.tracking_card_no">{{ row.tracking_card_no }}</small>
              </td>
              <td>{{ row.shift_name || '每日一录' }}</td>
              <td>
                <strong>{{ row.responsible_name || row.responsible_username || '-' }}</strong>
                <small v-if="row.responsible_username">{{ row.responsible_username }}</small>
              </td>
              <td>{{ formatDateTime(row.submitted_at || row.updated_at) }}</td>
              <td>{{ contentText(row) }}</td>
              <td>{{ statusText(row.status) }}</td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import dayjs from 'dayjs'

import DateSwitcher from '../../../components/manage/DateSwitcher.vue'
import { fetchLiveFillDetails } from '../../../api/realtime.js'
import { inferBusinessDate } from '../../../utils/shiftClock.js'

const targetDate = ref(inferBusinessDate())
const loading = ref(false)
const errorText = ref('')
const freshness = ref('yellow')
const keyword = ref('')
const sourceType = ref('')
const rows = ref([])
const summary = ref({})

const sourceOptions = [
  { value: 'machine_energy', label: '机台能耗' },
  { value: 'work_order_entry', label: '机台填报' },
  { value: 'owner_daily', label: '每日一录' },
  { value: 'mobile_shift_report', label: '班次汇总' },
  { value: 'mes_projection', label: '外部 MES' }
]

const kpis = computed(() => [
  { key: 'entry', label: '明细', value: summary.value.entry_count ?? rows.value.length, unit: '条' },
  { key: 'machine', label: '机列', value: summary.value.machine_count ?? 0, unit: '台' },
  { key: 'owner', label: '责任人', value: summary.value.owner_count ?? 0, unit: '人' },
  { key: 'output', label: '产量', value: formatNumber(summary.value.output, 2), unit: '吨' },
  { key: 'energy', label: '用电', value: formatNumber(summary.value.energy_kwh, 1), unit: 'kWh' },
  { key: 'gas', label: '天然气', value: formatNumber(summary.value.gas_m3, 1), unit: 'm³' }
])

const filteredRows = computed(() => {
  const text = keyword.value.trim().toLowerCase()
  return rows.value.filter((row) => {
    if (sourceType.value && row.source_type !== sourceType.value) return false
    if (!text) return true
    const haystack = [
      row.search_text,
      row.source_label,
      row.workshop_name,
      row.machine_name,
      row.shift_name,
      row.responsible_name,
      row.responsible_username,
      row.tracking_card_no,
      contentText(row)
    ].filter(Boolean).join(' ').toLowerCase()
    return haystack.includes(text)
  })
})

function formatNumber(value, digits = 2) {
  const num = Number(value)
  if (!Number.isFinite(num)) return '-'
  return num.toFixed(digits)
}

function formatDateTime(value) {
  if (!value) return '-'
  const parsed = dayjs(value)
  return parsed.isValid() ? parsed.format('MM-DD HH:mm') : '-'
}

function statusText(value) {
  const map = {
    submitted: '已提交',
    verified: '已核验',
    approved: '已确认',
    auto_confirmed: '自动确认',
    draft: '草稿',
    returned: '退回'
  }
  return map[value] || value || '-'
}

function contentText(row) {
  const parts = []
  if (row.output_weight != null) parts.push(`产量 ${formatNumber(row.output_weight, 3)} 吨`)
  if (row.input_weight != null) parts.push(`上料 ${formatNumber(row.input_weight, 3)} 吨`)
  if (row.scrap_weight != null) parts.push(`废料 ${formatNumber(row.scrap_weight, 3)} 吨`)
  if (row.energy_kwh != null) parts.push(`用电 ${formatNumber(row.energy_kwh, 1)} kWh`)
  if (row.gas_m3 != null) parts.push(`天然气 ${formatNumber(row.gas_m3, 1)} m³`)
  for (const item of row.metrics || []) {
    if (item?.value != null) parts.push(`${item.label || item.key} ${item.value}${item.unit || ''}`)
  }
  return parts.length ? parts.join('；') : '-'
}

async function load() {
  loading.value = true
  errorText.value = ''
  try {
    const payload = await fetchLiveFillDetails({ business_date: targetDate.value, limit: 2000 })
    rows.value = Array.isArray(payload.items) ? payload.items : []
    summary.value = payload.summary || {}
    freshness.value = 'green'
  } catch (error) {
    rows.value = []
    summary.value = {}
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
.xt-fill-details__empty { text-align: center; color: var(--xt-text-muted); }
@media (max-width: 920px) {
  .xt-fill-details__header { align-items: stretch; flex-direction: column; }
  .xt-fill-details__cards { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .xt-fill-details__select { flex: 1 1 160px; }
}
</style>
