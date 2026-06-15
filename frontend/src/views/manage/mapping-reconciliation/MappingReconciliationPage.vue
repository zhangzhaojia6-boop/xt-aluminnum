<template>
  <section class="xt-mapping-reconciliation" data-testid="mapping-reconciliation-page">
    <header class="xt-mapping-reconciliation__hero">
      <div>
        <span>只读 dry-run</span>
        <h1>输出skill 对齐</h1>
      </div>
      <button type="button" :disabled="running" @click="runDryRun">
        {{ running ? '试算中' : '运行真实试算' }}
      </button>
    </header>

    <div v-if="loading" class="xt-mapping-reconciliation__state">读取数据源</div>
    <div v-else-if="errorText" class="xt-mapping-reconciliation__state is-error">
      <span>{{ errorText }}</span>
      <button type="button" @click="loadSources">重试</button>
    </div>

    <section class="xt-mapping-reconciliation__metrics">
      <article v-for="card in metricCards" :key="card.key">
        <span>{{ card.label }}</span>
        <strong>{{ card.value }}</strong>
        <small>{{ card.meta }}</small>
      </article>
    </section>

    <section class="xt-mapping-reconciliation__grid">
      <article class="xt-mapping-reconciliation__panel is-controls">
        <header>
          <h2>试算条件</h2>
          <span>只读执行</span>
        </header>
        <div class="xt-mapping-reconciliation__controls">
          <label>
            <span>参考文件</span>
            <select v-model="selectedReferenceFile">
              <option value="">请选择文件</option>
              <option v-for="item in runnableFiles" :key="item.relative_path" :value="item.relative_path">
                {{ item.relative_path }}
              </option>
            </select>
          </label>
          <label>
            <span>业务日</span>
            <input v-model="businessDate" type="date" />
          </label>
          <fieldset>
            <legend>可比维度</legend>
            <label v-for="item in dimensionOptions" :key="item.key">
              <input v-model="selectedDimensions" type="checkbox" :value="item.key" />
              <span>{{ item.label }}</span>
            </label>
          </fieldset>
        </div>
      </article>

      <article class="xt-mapping-reconciliation__panel">
        <header>
          <h2>参考源</h2>
          <span>{{ sourceFiles.length }} 个文件</span>
        </header>
        <p class="xt-mapping-reconciliation__path">{{ sourceRoot }}</p>
        <div v-if="sourceFiles.length === 0" class="xt-mapping-reconciliation__empty">暂无可读文件</div>
        <ul v-else class="xt-mapping-reconciliation__file-list">
          <li v-for="item in sourceFiles.slice(0, 12)" :key="item.relative_path">
            <b>{{ item.name }}</b>
            <span>{{ item.extension || '无扩展名' }} / {{ formatBytes(item.size_bytes) }}</span>
          </li>
        </ul>
      </article>

      <article class="xt-mapping-reconciliation__panel">
        <header>
          <h2>系统源</h2>
          <span>{{ systemSources.length }} 张表</span>
        </header>
        <div class="xt-mapping-reconciliation__chips">
          <span v-for="item in systemSources" :key="item">{{ item }}</span>
        </div>
      </article>

      <article class="xt-mapping-reconciliation__panel">
        <header>
          <h2>差异原因汇总</h2>
          <span>{{ displayNumber(differenceSummary.total) }} 条</span>
        </header>
        <div v-if="!result" class="xt-mapping-reconciliation__empty">未运行试算</div>
        <div v-else-if="reasonBreakdown.length === 0" class="xt-mapping-reconciliation__empty">暂无差异原因</div>
        <ul v-else class="xt-mapping-reconciliation__summary">
          <li v-for="reason in reasonBreakdown" :key="reason.reason_code">
            <b>{{ reason.label }}</b>
            <strong>{{ displayNumber(reason.count) }}</strong>
          </li>
        </ul>
      </article>

      <article class="xt-mapping-reconciliation__panel is-wide">
        <header>
          <h2>差异明细</h2>
          <span>{{ differences.length }} 条</span>
        </header>
        <div v-if="differences.length === 0" class="xt-mapping-reconciliation__empty">当前没有差异</div>
        <div v-else class="xt-mapping-reconciliation__table-wrap">
          <table>
            <thead>
              <tr>
                <th>指标</th>
                <th>维度</th>
                <th>参考值</th>
                <th>系统值</th>
                <th>差异</th>
                <th>原因</th>
                <th>建议规则</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(item, index) in differences" :key="`${item.reason_code}-${index}`">
                <td>{{ metricLabel(item.metric) }}</td>
                <td>{{ formatDimension(item.dimension) }}</td>
                <td>{{ formatValue(item.reference_value) }}</td>
                <td>{{ formatValue(item.system_value) }}</td>
                <td>{{ formatValue(item.diff_value) }}</td>
                <td>{{ reasonLabel(item.reason_code) }}</td>
                <td>{{ item.suggested_rule || '人工确认' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </article>

      <article class="xt-mapping-reconciliation__panel">
        <header>
          <h2>规则建议</h2>
          <span>{{ ruleProposals.length }} 条</span>
        </header>
        <div v-if="ruleProposals.length === 0" class="xt-mapping-reconciliation__empty">暂无建议</div>
        <ol v-else class="xt-mapping-reconciliation__rules">
          <li v-for="item in ruleProposals" :key="`${item.field}-${item.reference_value}-${item.system_value}`">
            <b>{{ fieldLabel(item.field) }}</b>
            <span>{{ item.system_value }} → {{ item.reference_value }}</span>
            <small>{{ item.dry_run ? '仅试算' : '待确认' }}</small>
          </li>
        </ol>
      </article>
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

import { fetchMappingReconciliationSources, runMappingReconciliation } from '../../../api/mapping-reconciliation.js'
import { inferLastCompletedBusinessDate } from '../../../utils/shiftClock.js'

const loading = ref(false)
const running = ref(false)
const errorText = ref('')
const sources = ref({ available: false, files: [], system_sources: [] })
const result = ref(null)
const selectedReferenceFile = ref('')
const businessDate = ref(inferLastCompletedBusinessDate())
const selectedDimensions = ref(['business_date', 'workshop'])

const sourceFiles = computed(() => sources.value?.files || [])
const runnableFiles = computed(() => sourceFiles.value.filter((item) => ['.txt', '.md', '.log', '.xlsx', '.xls'].includes(item.extension)))
const systemSources = computed(() => sources.value?.system_sources || [])
const sourceRoot = computed(() => sources.value?.reference_source || '未配置')
const differences = computed(() => result.value?.differences || [])
const ruleProposals = computed(() => result.value?.rule_proposals || [])
const differenceSummary = computed(() => result.value?.difference_summary || { total: differences.value.length, by_reason_code: {}, by_metric: {}, reason_breakdown: [] })
const reasonBreakdown = computed(() => differenceSummary.value.reason_breakdown || [])
const matchRate = computed(() => Number(result.value?.overall_match_rate || 0))
const referenceRowsCount = computed(() => Number(result.value?.reference_rows_count || 0))
const systemRowsCount = computed(() => Number(result.value?.system_rows_count || 0))
const runId = computed(() => result.value?.run_id || null)

const dimensionOptions = [
  { key: 'business_date', label: '日期' },
  { key: 'workshop', label: '车间' },
  { key: 'shift', label: '班次' },
  { key: 'machine', label: '机台' },
  { key: 'process', label: '工序' }
]

const defaultMappingFields = [
  {
    metric: 'output',
    reference_field: 'output_tons',
    system_field: 'output_tons',
    reference_unit: 'ton',
    system_unit: 'ton',
    tolerance: 0.01,
    weight: 30
  },
  {
    metric: 'scrap',
    reference_field: 'scrap_tons',
    system_field: 'scrap_tons',
    reference_unit: 'ton',
    system_unit: 'ton',
    tolerance: 0.01,
    weight: 10
  },
  {
    metric: 'downtime',
    reference_field: 'downtime_minutes',
    system_field: 'downtime_minutes',
    reference_unit: 'minute',
    system_unit: 'minute',
    tolerance: 1,
    weight: 10
  },
  {
    metric: 'quality',
    reference_field: 'quality_issue_count',
    system_field: 'quality_issue_count',
    reference_unit: 'count',
    system_unit: 'count',
    tolerance: 0,
    weight: 10
  },
  {
    metric: 'yield',
    reference_field: 'yield_rate',
    system_field: 'yield_rate',
    reference_unit: 'percent',
    system_unit: 'percent',
    tolerance: 0.01,
    weight: 15
  },
  {
    metric: 'energy',
    reference_field: 'energy_kwh',
    system_field: 'energy_kwh',
    reference_unit: 'kwh',
    system_unit: 'kwh',
    tolerance: 0.1,
    weight: 15
  },
  {
    metric: 'gas',
    reference_field: 'gas_m3',
    system_field: 'gas_m3',
    reference_unit: 'm3',
    system_unit: 'm3',
    tolerance: 0.1,
    weight: 10
  },
  {
    metric: 'rolling_oil',
    reference_field: 'rolling_oil_per_ton',
    system_field: 'rolling_oil_per_ton',
    reference_unit: 'per_ton',
    system_unit: 'per_ton',
    tolerance: 0.01,
    weight: 10
  },
  {
    metric: 'cost',
    reference_field: 'cost_per_ton',
    system_field: 'cost_per_ton',
    reference_unit: 'yuan_per_ton',
    system_unit: 'yuan_per_ton',
    tolerance: 0.01,
    weight: 10
  }
]

const defaultDimensionAliases = {
  workshop: {
    精整车间: '精整',
    拉矫车间: '拉矫',
    剪切车间: '园区剪切',
    成品库: '成品库'
  },
  shift: {
    白班: '长白班',
    小夜: '小夜班',
    大夜: '大夜班'
  }
}

const metricCards = computed(() => [
  { key: 'files', label: '参考文件', value: displayNumber(sourceFiles.value.length), meta: sources.value?.available ? '已挂载' : '未挂载' },
  { key: 'rows', label: '对齐行数', value: `${displayNumber(referenceRowsCount.value)} / ${displayNumber(systemRowsCount.value)}`, meta: '输出skill / 系统' },
  { key: 'match', label: '当前匹配率', value: `${displayNumber(matchRate.value)}%`, meta: result.value ? '来自试算' : '未运行' },
  { key: 'diff', label: '差异数量', value: displayNumber(differenceSummary.value.total), meta: '可追原因' },
  { key: 'run', label: '运行编号', value: runId.value ? `#${displayNumber(runId.value)}` : '-', meta: runId.value ? '可追溯' : '未保存' }
])

function displayNumber(value) {
  const number = Number(value || 0)
  return Number.isFinite(number) ? number.toLocaleString('zh-CN') : '0'
}

function formatBytes(value) {
  const number = Number(value || 0)
  if (number >= 1024 * 1024) return `${(number / 1024 / 1024).toFixed(1)} MB`
  if (number >= 1024) return `${(number / 1024).toFixed(1)} KB`
  return `${number} B`
}

function formatValue(value) {
  if (value === null || value === undefined || value === '') return '-'
  if (typeof value === 'number') return displayNumber(value)
  return String(value)
}

function formatDimension(value) {
  if (!value) return '-'
  return Object.entries(value)
    .filter(([, item]) => item)
    .map(([key, item]) => `${fieldLabel(key)}:${item}`)
    .join(' / ')
}

function fieldLabel(value) {
  const labels = { business_date: '日期', workshop: '车间', shift: '班次', machine: '机台', process: '工序' }
  return labels[value] || value || '字段'
}

function metricLabel(value) {
  const labels = {
    output: '产量',
    scrap: '废料',
    downtime: '停机',
    quality: '质量',
    yield: '成材率',
    energy: '能耗',
    gas: '燃气',
    rolling_oil: '轧制油吨耗',
    cost: '吨成本'
  }
  return labels[value] || value || '指标'
}

function reasonLabel(value) {
  const labels = {
    value_diff: '数值不一致',
    missing_system_row: '系统缺行',
    extra_system_row: '系统多行',
    missing_field_value: '字段缺值'
  }
  return labels[value] || value || '待确认'
}

async function loadSources() {
  loading.value = true
  errorText.value = ''
  try {
    sources.value = await fetchMappingReconciliationSources()
    if (!selectedReferenceFile.value && runnableFiles.value.length > 0) {
      selectedReferenceFile.value = runnableFiles.value[0].relative_path
    }
  } catch (error) {
    errorText.value = error?.response?.data?.detail || error?.message || '读取失败'
    sources.value = { available: false, files: [], system_sources: [] }
  } finally {
    loading.value = false
  }
}

async function runDryRun() {
  if (!selectedReferenceFile.value) {
    errorText.value = '请选择参考文件'
    return
  }
  if (!businessDate.value) {
    errorText.value = '请选择业务日'
    return
  }
  running.value = true
  errorText.value = ''
  try {
    result.value = await runMappingReconciliation({
      reference_file: selectedReferenceFile.value,
      business_date: businessDate.value,
      fields: defaultMappingFields,
      dimensions: selectedDimensions.value.length > 0 ? selectedDimensions.value : ['business_date', 'workshop'],
      dimension_aliases: defaultDimensionAliases
    })
  } catch (error) {
    errorText.value = error?.response?.data?.detail || error?.message || '试算失败'
  } finally {
    running.value = false
  }
}

onMounted(loadSources)
</script>

<style scoped>
.xt-mapping-reconciliation {
  --mapping-bg: #081116;
  --mapping-panel: #111b22;
  --mapping-border: rgba(179, 139, 69, 0.28);
  --mapping-gold: #c79b4b;
  --mapping-red: #7f1d1d;
  --mapping-text: #f5f0e6;
  display: grid;
  gap: var(--xt-space-4);
  min-height: calc(100vh - var(--xt-topbar-height) - var(--xt-space-10));
  color: var(--mapping-text);
}

.xt-mapping-reconciliation__hero,
.xt-mapping-reconciliation__metrics article,
.xt-mapping-reconciliation__panel,
.xt-mapping-reconciliation__state {
  border: 1px solid var(--mapping-border);
  border-radius: 14px;
  background:
    linear-gradient(180deg, rgba(199, 155, 75, 0.08), transparent 42%),
    linear-gradient(135deg, rgba(17, 27, 34, 0.96), rgba(8, 17, 22, 0.96));
  box-shadow: inset 0 1px 0 rgba(245, 240, 230, 0.06);
}

.xt-mapping-reconciliation__hero {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: var(--xt-space-4);
  min-height: 132px;
  padding: var(--xt-space-5);
}

.xt-mapping-reconciliation__hero span {
  color: var(--mapping-gold);
  font-size: var(--xt-text-xs);
  font-weight: 900;
  letter-spacing: 0.16em;
}

.xt-mapping-reconciliation__hero h1 {
  margin: var(--xt-space-2) 0 0;
  color: var(--mapping-text);
  font-family: var(--xt-font-display);
  font-size: clamp(34px, 4vw, 56px);
  font-weight: 950;
  letter-spacing: -0.04em;
}

.xt-mapping-reconciliation button {
  min-height: 38px;
  padding: 0 var(--xt-space-4);
  border: 1px solid rgba(199, 155, 75, 0.42);
  border-radius: 999px;
  background: rgba(199, 155, 75, 0.12);
  color: var(--mapping-text);
  cursor: pointer;
  font-weight: 900;
}

.xt-mapping-reconciliation button:disabled {
  cursor: not-allowed;
  opacity: 0.58;
}

.xt-mapping-reconciliation__state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--xt-space-3);
  min-height: 68px;
  color: rgba(245, 240, 230, 0.74);
  font-weight: 900;
}

.xt-mapping-reconciliation__state.is-error {
  border-color: rgba(127, 29, 29, 0.52);
  color: #ffb4a8;
}

.xt-mapping-reconciliation__metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--xt-space-3);
}

.xt-mapping-reconciliation__metrics article {
  display: grid;
  gap: var(--xt-space-2);
  min-height: 120px;
  padding: var(--xt-space-4);
}

.xt-mapping-reconciliation__metrics span,
.xt-mapping-reconciliation__panel header span {
  color: rgba(245, 240, 230, 0.62);
  font-size: var(--xt-text-xs);
  font-weight: 850;
  letter-spacing: 0.08em;
}

.xt-mapping-reconciliation__metrics strong {
  color: var(--mapping-gold);
  font-family: var(--xt-font-number);
  font-size: clamp(30px, 3vw, 44px);
  line-height: 1;
}

.xt-mapping-reconciliation__metrics small {
  color: rgba(245, 240, 230, 0.68);
  font-weight: 800;
}

.xt-mapping-reconciliation__grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(340px, 0.7fr);
  gap: var(--xt-space-4);
}

.xt-mapping-reconciliation__panel {
  min-width: 0;
  display: grid;
  align-content: start;
  gap: var(--xt-space-3);
  padding: var(--xt-space-4);
}

.xt-mapping-reconciliation__panel.is-wide {
  grid-column: 1 / -1;
}

.xt-mapping-reconciliation__panel header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-3);
  padding-bottom: var(--xt-space-3);
  border-bottom: 1px solid rgba(199, 155, 75, 0.18);
}

.xt-mapping-reconciliation__panel h2 {
  margin: 0;
  color: var(--mapping-text);
  font-size: var(--xt-text-lg);
  font-weight: 950;
}

.xt-mapping-reconciliation__path {
  overflow: hidden;
  margin: 0;
  color: rgba(245, 240, 230, 0.62);
  font-family: var(--xt-font-mono);
  font-size: var(--xt-text-xs);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.xt-mapping-reconciliation__empty {
  min-height: 98px;
  display: grid;
  place-items: center;
  border: 1px dashed rgba(199, 155, 75, 0.28);
  border-radius: 12px;
  color: rgba(245, 240, 230, 0.54);
  font-weight: 900;
}

.xt-mapping-reconciliation__file-list,
.xt-mapping-reconciliation__rules,
.xt-mapping-reconciliation__summary {
  display: grid;
  gap: var(--xt-space-2);
  margin: 0;
  padding: 0;
  list-style: none;
}

.xt-mapping-reconciliation__file-list li,
.xt-mapping-reconciliation__rules li,
.xt-mapping-reconciliation__summary li {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-3);
  padding: var(--xt-space-3);
  border: 1px solid rgba(199, 155, 75, 0.14);
  border-radius: 10px;
  background: rgba(245, 240, 230, 0.035);
}

.xt-mapping-reconciliation__file-list b,
.xt-mapping-reconciliation__rules b,
.xt-mapping-reconciliation__summary b {
  overflow: hidden;
  color: var(--mapping-text);
  font-weight: 900;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.xt-mapping-reconciliation__file-list span,
.xt-mapping-reconciliation__rules span,
.xt-mapping-reconciliation__rules small {
  flex: 0 0 auto;
  color: rgba(245, 240, 230, 0.58);
  font-size: var(--xt-text-xs);
  font-weight: 800;
}

.xt-mapping-reconciliation__summary strong {
  color: var(--mapping-gold);
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-xl);
}

.xt-mapping-reconciliation__chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--xt-space-2);
}

.xt-mapping-reconciliation__chips span {
  padding: var(--xt-space-2) var(--xt-space-3);
  border: 1px solid rgba(199, 155, 75, 0.2);
  border-radius: 999px;
  background: rgba(199, 155, 75, 0.08);
  color: rgba(245, 240, 230, 0.78);
  font-size: var(--xt-text-xs);
  font-weight: 850;
}

.xt-mapping-reconciliation__panel.is-controls {
  grid-column: 1 / -1;
}

.xt-mapping-reconciliation__controls {
  display: grid;
  grid-template-columns: minmax(280px, 1.2fr) minmax(180px, 0.6fr) minmax(320px, 1fr);
  gap: var(--xt-space-3);
}

.xt-mapping-reconciliation__controls label,
.xt-mapping-reconciliation__controls fieldset {
  display: grid;
  gap: var(--xt-space-2);
  margin: 0;
  min-width: 0;
  border: 0;
  padding: 0;
}

.xt-mapping-reconciliation__controls label span,
.xt-mapping-reconciliation__controls legend {
  color: rgba(245, 240, 230, 0.64);
  font-size: var(--xt-text-xs);
  font-weight: 900;
}

.xt-mapping-reconciliation__controls select,
.xt-mapping-reconciliation__controls input[type='date'] {
  width: 100%;
  min-height: 42px;
  border: 1px solid rgba(199, 155, 75, 0.28);
  border-radius: 10px;
  background: rgba(8, 17, 22, 0.72);
  color: var(--mapping-text);
  font-weight: 850;
  padding: 0 var(--xt-space-3);
}

.xt-mapping-reconciliation__controls fieldset {
  align-content: start;
  grid-template-columns: repeat(5, minmax(0, 1fr));
}

.xt-mapping-reconciliation__controls fieldset legend {
  grid-column: 1 / -1;
}

.xt-mapping-reconciliation__controls fieldset label {
  display: flex;
  align-items: center;
  gap: var(--xt-space-1);
  color: rgba(245, 240, 230, 0.76);
  font-weight: 850;
}

.xt-mapping-reconciliation__table-wrap {
  overflow-x: auto;
}

.xt-mapping-reconciliation table {
  width: 100%;
  min-width: 920px;
  border-collapse: collapse;
}

.xt-mapping-reconciliation th,
.xt-mapping-reconciliation td {
  padding: 11px var(--xt-space-2);
  border-bottom: 1px solid rgba(199, 155, 75, 0.12);
  text-align: left;
}

.xt-mapping-reconciliation th {
  color: var(--mapping-gold);
  font-size: var(--xt-text-xs);
  font-weight: 950;
}

.xt-mapping-reconciliation td {
  color: rgba(245, 240, 230, 0.78);
  font-size: var(--xt-text-sm);
}

@media (max-width: 1120px) {
  .xt-mapping-reconciliation__metrics,
  .xt-mapping-reconciliation__grid,
  .xt-mapping-reconciliation__controls {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 760px) {
  .xt-mapping-reconciliation__hero {
    align-items: flex-start;
    flex-direction: column;
  }

  .xt-mapping-reconciliation__metrics,
  .xt-mapping-reconciliation__grid,
  .xt-mapping-reconciliation__controls {
    grid-template-columns: 1fr;
  }

  .xt-mapping-reconciliation__controls fieldset {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
