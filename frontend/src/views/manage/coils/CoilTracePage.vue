<template>
  <section class="xt-coils" data-testid="manage-coils">
    <header class="xt-coils__hero">
      <div class="xt-coils__hero-copy">
        <span class="xt-coils__eyebrow">MES 主数据</span>
        <h1>卷级线索</h1>
      </div>
      <div class="xt-coils__search">
        <input
          v-model.trim="filters.query"
          type="search"
          placeholder="搜索随行卡、批号、合金、机列"
          aria-label="搜索随行卡、批号、合金、机列"
          @keydown.enter="load"
        >
        <input
          v-model.trim="filters.workshop"
          type="search"
          placeholder="筛选车间"
          aria-label="筛选车间"
          @keydown.enter="load"
        >
        <select v-model="filters.destination" aria-label="筛选去向" @change="load">
          <option value="">全部去向</option>
          <option value="in_progress">在制</option>
          <option value="finished_stock">成品库存</option>
          <option value="allocation">已分配</option>
          <option value="delivery">交付</option>
          <option value="unknown">未知</option>
        </select>
        <input
          v-model.trim="filters.customer"
          type="search"
          placeholder="筛选客户"
          aria-label="筛选客户"
        >
        <input
          v-model.trim="filters.material"
          type="search"
          placeholder="合金/规格"
          aria-label="筛选合金或规格"
        >
        <input
          v-model.trim="filters.process"
          type="search"
          placeholder="当前工艺"
          aria-label="筛选当前工艺"
        >
        <select v-model="filters.machine_state" aria-label="筛选机列状态">
          <option value="">全部机列</option>
          <option value="bound">已匹配机列</option>
          <option value="pending">待绑定机列</option>
        </select>
        <button type="button" :disabled="loading" @click="load">{{ loading ? '同步中' : '查询' }}</button>
      </div>
    </header>

    <div class="xt-coils__ticker">
      <article v-for="item in kpis" :key="item.key" :class="`tone-${item.tone}`">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </article>
    </div>

    <div class="xt-coils__filter-summary" data-testid="manage-coils-filter-summary">
      <span>当前筛选</span>
      <strong>{{ coils.length }} / {{ rawCoils.length }} 卷</strong>
      <small>{{ activeFilterText }}</small>
    </div>

    <div v-if="errorText" class="xt-coils__error">{{ errorText }}</div>

    <div class="xt-coils__layout">
      <section class="xt-coils__table-panel">
        <div class="xt-coils__panel-head">
          <div>
            <span class="xt-coils__eyebrow">卷材列表</span>
            <h2>MES 过站线索</h2>
          </div>
          <small>{{ coils.length }} 卷</small>
        </div>

        <div class="xt-coils__table-wrap">
          <table class="xt-coils__table" data-testid="manage-coils-table">
            <thead>
              <tr>
                <th scope="col">随行卡</th>
                <th scope="col">批号/合金</th>
                <th scope="col">当前车间</th>
                <th scope="col">当前工艺</th>
                <th scope="col">机列归属</th>
                <th scope="col">自动废料</th>
                <th scope="col">去向</th>
              </tr>
            </thead>
            <tbody>
              <tr v-if="loading">
                <td colspan="7" class="xt-coils__empty">正在读取 MES 卷级线索...</td>
              </tr>
              <tr v-else-if="coils.length === 0">
                <td colspan="7" class="xt-coils__empty">暂无卷级线索</td>
              </tr>
              <template v-else>
                <tr
                  v-for="coil in coils"
                  :key="coil.coil_key"
                  :class="{ 'is-active': selectedCoil?.coil_key === coil.coil_key }"
                  @click="selectCoil(coil)"
                >
                  <td data-label="随行卡">
                    <button type="button" class="xt-coils__coil-key" @click.stop="selectCoil(coil)">
                      {{ coil.tracking_card_no || coil.coil_key }}
                    </button>
                  </td>
                  <td data-label="批号/合金">
                    <strong>{{ coil.batch_no || '-' }}</strong>
                    <small>{{ materialSummary(coil) }}</small>
                    <small v-if="customerText(coil)">客户 {{ customerText(coil) }}</small>
                  </td>
                  <td data-label="当前车间">{{ coil.current_workshop || '-' }}</td>
                  <td data-label="当前工艺">{{ coil.current_process || '-' }}</td>
                  <td data-label="机列归属">
                    <span class="xt-coils__binding" :class="bindingTone(coil)">
                      {{ machineLabel(coil) }}
                    </span>
                  </td>
                  <td data-label="自动废料">
                    <span class="xt-coils__binding" :class="scrapTone(coil)">
                      {{ scrapLabel(coil) }}
                    </span>
                  </td>
                  <td data-label="去向">{{ destinationLabel(coil.destination) }}</td>
                </tr>
              </template>
            </tbody>
          </table>
        </div>
      </section>

      <aside class="xt-coils__flow" data-testid="manage-coils-flow">
        <div class="xt-coils__panel-head">
          <div>
            <span class="xt-coils__eyebrow">人工补录对照</span>
            <h2>卷材流向</h2>
          </div>
          <small>{{ flowFreshnessText }}</small>
        </div>

        <template v-if="selectedCoil">
          <div class="xt-coils__identity">
            <strong>{{ selectedCoil.tracking_card_no || selectedCoil.coil_key }}</strong>
            <span>{{ selectedCoil.batch_no || '批号未同步' }} · {{ selectedCoil.material_code || '材质未同步' }}</span>
          </div>

          <div class="xt-coils__route">
            <article v-for="step in flowSteps" :key="step.key" :class="{ 'is-current': step.current }">
              <span>{{ step.label }}</span>
              <strong>{{ step.process }}</strong>
              <small>{{ step.workshop }}</small>
            </article>
          </div>

          <div class="xt-coils__compare">
            <article>
              <span>MES 主数据</span>
              <strong>{{ flowMachineText }}</strong>
              <small>{{ destinationLabel((flow || selectedCoil).destination) }}</small>
            </article>
            <article>
              <span>MES 上机</span>
              <strong>{{ formatTons(flowSource.mes_input_weight_tons) }}</strong>
              <small>来自 MES 工序记录</small>
            </article>
            <article>
              <span>MES 下机</span>
              <strong>{{ formatTons(flowSource.mes_output_weight_tons) }}</strong>
              <small>用于核对产量</small>
            </article>
            <article>
              <span>自动废料</span>
              <strong>{{ scrapLabel(flowSource) }}</strong>
              <small>{{ scrapStatusText(flowSource.scrap_status) }}</small>
            </article>
            <article>
              <span>废料率</span>
              <strong>{{ formatPercent(flowSource.auto_scrap_rate) }}</strong>
              <small>{{ scrapStatusText(flowSource.scrap_status) }}</small>
            </article>
            <article>
              <span>人工补录对照</span>
              <strong>从填报明细核对</strong>
              <small>补录不覆盖 MES 原始记录</small>
            </article>
            <article>
              <span>机列状态</span>
              <strong>{{ machineLabel(selectedCoil) }}</strong>
              <small>{{ machineHintText }}</small>
            </article>
          </div>
        </template>

        <p v-else class="xt-coils__empty">请选择一卷查看流向</p>
      </aside>
    </div>
  </section>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

import { fetchFactoryCommandCoilFlow, fetchFactoryCommandCoils } from '../../../api/factory-command.js'

const rawCoils = ref([])
const selectedCoil = ref(null)
const flow = ref(null)
const loading = ref(false)
const flowLoading = ref(false)
const errorText = ref('')
const filters = ref({
  query: '',
  workshop: '',
  destination: '',
  customer: '',
  material: '',
  process: '',
  machine_state: '',
})

const visibleCoils = computed(() => rawCoils.value.filter((coil) => (
  matchText(coil, ['customer_alias', 'customer_name', 'contract_customer_name'], filters.value.customer)
  && matchText(coil, ['material_code', 'alloy_grade', 'spec_display', 'spec_thickness', 'spec_width', 'spec_length', 'batch_no'], filters.value.material)
  && matchText(coil, ['current_process', 'process_code', 'previous_process', 'next_process'], filters.value.process)
  && machineStateMatches(coil, filters.value.machine_state)
)))
const coils = visibleCoils
const pendingBindingCount = computed(() => coils.value.filter((coil) => !hasBoundMachine(coil)).length)
const inFactoryCount = computed(() => coils.value.filter((coil) => coil.current_workshop || coil.current_process).length)
const activeFilterText = computed(() => {
  const labels = []
  if (filters.value.customer) labels.push(`客户 ${filters.value.customer}`)
  if (filters.value.material) labels.push(`合金/规格 ${filters.value.material}`)
  if (filters.value.process) labels.push(`工艺 ${filters.value.process}`)
  if (filters.value.machine_state === 'bound') labels.push('已匹配机列')
  if (filters.value.machine_state === 'pending') labels.push('待绑定机列')
  return labels.length ? labels.join(' · ') : '全部卷级线索'
})
const kpis = computed(() => [
  { key: 'total', label: '卷级线索', value: coils.value.length, tone: 'normal' },
  { key: 'running', label: '在制卷', value: inFactoryCount.value, tone: 'success' },
  { key: 'pending', label: '待绑定机列', value: pendingBindingCount.value, tone: pendingBindingCount.value ? 'warning' : 'success' },
  { key: 'source', label: '数据来源', value: 'MES', tone: 'normal' },
])
const flowSource = computed(() => flow.value || selectedCoil.value || {})
const flowFreshnessText = computed(() => {
  if (flowLoading.value) return '读取中'
  const freshness = flow.value?.freshness
  if (!freshness) return '待选择'
  if (freshness.status === 'fresh') return '同步正常'
  return freshness.status || '已同步'
})
const flowMachineText = computed(() => machineLabel(flowSource.value))
const machineHintText = computed(() => {
  if (selectedCoil.value?.machine_code || selectedCoil.value?.line_code) return '已匹配机列'
  return '待绑定'
})
const flowSteps = computed(() => {
  const item = flowSource.value
  return [
    {
      key: 'previous',
      label: '上一工序',
      workshop: item.previous_workshop || '-',
      process: item.previous_process || '-',
      current: false,
    },
    {
      key: 'current',
      label: '当前工序',
      workshop: item.current_workshop || '-',
      process: item.current_process || '-',
      current: true,
    },
    {
      key: 'next',
      label: '下一工序',
      workshop: item.next_workshop || destinationLabel(item.destination),
      process: item.next_process || destinationLabel(item.destination),
      current: false,
    },
  ]
})

function normalizeParams() {
  const params = { limit: 100 }
  for (const key of ['query', 'workshop', 'destination']) {
    const value = filters.value[key]
    if (value) params[key] = value
  }
  return params
}

function textValue(value) {
  return String(value ?? '').trim().toLowerCase()
}

function matchText(coil, fields, value) {
  const needle = textValue(value)
  if (!needle) return true
  return fields.some((field) => textValue(coil?.[field]).includes(needle))
}

function machineStateMatches(coil, state) {
  if (!state) return true
  const bound = hasBoundMachine(coil)
  if (state === 'bound') return bound
  if (state === 'pending') return !bound
  return true
}

function isUnknownMachineLabel(value) {
  const text = String(value ?? '').trim().toLowerCase()
  return !text || text === 'unknown'
}

function hasBoundMachine(coil) {
  if (!coil) return false
  return !isUnknownMachineLabel(coil.machine_code) || !isUnknownMachineLabel(coil.line_code)
}

function destinationLabel(destination) {
  if (!destination) return '-'
  return destination.label || destination.kind || '-'
}

function customerText(coil) {
  return coil?.customer_alias || coil?.customer_name || coil?.contract_customer_name || ''
}

function materialSummary(coil) {
  const parts = [
    coil?.material_code || coil?.alloy_grade,
    coil?.spec_display,
  ].filter(Boolean)
  return parts.length ? parts.join(' · ') : '材质未同步'
}

function machineLabel(coil) {
  if (!coil) return '-'
  if (!isUnknownMachineLabel(coil.machine_code)) return coil.machine_code
  if (!isUnknownMachineLabel(coil.line_code)) return coil.line_code
  return '待绑定'
}

function bindingTone(coil) {
  return machineLabel(coil) === '待绑定' ? 'tone-warning' : 'tone-success'
}

function formatTons(value) {
  if (value === null || value === undefined || value === '') return '待同步'
  const numericValue = Number(value)
  if (!Number.isFinite(numericValue)) return '待同步'
  return `${numericValue.toFixed(2).replace(/\.00$/, '')} 吨`
}

function formatPercent(value) {
  if (value === null || value === undefined || value === '') return '待同步'
  const numericValue = Number(value)
  if (!Number.isFinite(numericValue)) return '待同步'
  return `${(numericValue * 100).toFixed(2).replace(/\.00$/, '')}%`
}

function scrapStatusText(status) {
  if (status === 'normal') return '自动计算'
  if (status === 'abnormal_output_gt_input') return '异常审核'
  if (status === 'missing_weight') return '缺少上下机重量'
  return '等待 MES 工序记录'
}

function scrapLabel(coil) {
  if (!coil) return '待同步'
  if (coil.scrap_status === 'abnormal_output_gt_input') return '异常审核'
  return formatTons(coil.auto_scrap_weight_tons)
}

function scrapTone(coil) {
  if (coil?.scrap_status === 'normal') return 'tone-success'
  if (coil?.scrap_status === 'abnormal_output_gt_input') return 'tone-warning'
  return 'tone-muted'
}

async function selectCoil(coil) {
  selectedCoil.value = coil
  flow.value = null
  flowLoading.value = true
  try {
    flow.value = await fetchFactoryCommandCoilFlow(coil.coil_key)
  } catch {
    flow.value = null
  } finally {
    flowLoading.value = false
  }
}

async function load() {
  loading.value = true
  errorText.value = ''
  try {
    rawCoils.value = await fetchFactoryCommandCoils(normalizeParams())
    if (coils.value.length) {
      await selectCoil(coils.value[0])
    } else {
      selectedCoil.value = null
      flow.value = null
    }
  } catch (error) {
    rawCoils.value = []
    selectedCoil.value = null
    flow.value = null
    errorText.value = error?.response?.data?.detail || error?.message || '卷级线索读取失败'
  } finally {
    loading.value = false
  }
}

watch(visibleCoils, (items) => {
  if (loading.value) return
  if (!items.length) {
    selectedCoil.value = null
    flow.value = null
    return
  }
  const selectedKey = selectedCoil.value?.coil_key
  if (!selectedKey || !items.some((coil) => coil.coil_key === selectedKey)) {
    void selectCoil(items[0])
  }
})

load()
</script>

<style scoped>
.xt-coils {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: var(--xt-space-4);
}

.xt-coils::before {
  position: fixed;
  inset: 0;
  z-index: -1;
  background:
    radial-gradient(circle at 18% 0%, color-mix(in srgb, var(--xt-primary) 15%, transparent), transparent 30%),
    linear-gradient(color-mix(in srgb, var(--xt-primary) 5%, transparent) 1px, transparent 1px),
    linear-gradient(90deg, color-mix(in srgb, var(--xt-primary) 5%, transparent) 1px, transparent 1px);
  background-size: auto, 34px 34px, 34px 34px;
  content: "";
  pointer-events: none;
}

.xt-coils__hero,
.xt-coils__ticker article,
.xt-coils__filter-summary,
.xt-coils__table-panel,
.xt-coils__flow {
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

.xt-coils__hero::before,
.xt-coils__ticker article::before,
.xt-coils__filter-summary::before,
.xt-coils__table-panel::before,
.xt-coils__flow::before {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 92% 10%, color-mix(in srgb, var(--xt-primary) 14%, transparent), transparent 34%),
    linear-gradient(135deg, color-mix(in srgb, var(--xt-primary) 7%, transparent), transparent 48%);
  content: "";
  pointer-events: none;
}

.xt-coils__hero {
  display: grid;
  grid-template-columns: minmax(0, 0.8fr) minmax(360px, 1.2fr);
  align-items: center;
  gap: var(--xt-space-4);
  min-height: 126px;
  padding: var(--xt-space-5);
}

.xt-coils__hero-copy,
.xt-coils__search,
.xt-coils__ticker article > *,
.xt-coils__filter-summary > *,
.xt-coils__table-panel > *,
.xt-coils__flow > * {
  position: relative;
  z-index: 1;
}

.xt-coils__eyebrow {
  color: color-mix(in srgb, var(--xt-primary) 72%, var(--xt-text-inverse));
  font-size: var(--xt-text-xs);
  font-weight: 900;
  letter-spacing: 0.08em;
}

.xt-coils h1,
.xt-coils h2 {
  margin: 0;
  color: var(--xt-text-inverse);
  font-family: var(--xt-font-display);
  font-weight: 900;
}

.xt-coils h1 {
  margin-top: var(--xt-space-1);
  font-size: clamp(var(--xt-text-2xl), 3vw, 42px);
  letter-spacing: -0.04em;
}

.xt-coils h2 {
  margin-top: 4px;
  font-size: var(--xt-text-xl);
}

.xt-coils__search {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--xt-space-2);
}

.xt-coils__search input,
.xt-coils__search select,
.xt-coils__search button {
  min-height: 42px;
  border: 1px solid color-mix(in srgb, var(--xt-primary) 18%, var(--xt-border));
  border-radius: var(--xt-radius-lg);
  background: color-mix(in srgb, var(--xt-bg-ink) 48%, var(--xt-bg-panel));
  color: var(--xt-text-inverse);
  font-size: var(--xt-text-sm);
  font-weight: 850;
  box-shadow: inset 0 -1px 0 color-mix(in srgb, var(--xt-primary) 18%, transparent);
}

.xt-coils__search input,
.xt-coils__search select {
  padding: 0 var(--xt-space-3);
}

.xt-coils__search input::placeholder {
  color: color-mix(in srgb, var(--xt-text-inverse) 42%, transparent);
}

.xt-coils__search button {
  cursor: pointer;
  background: color-mix(in srgb, var(--xt-primary) 16%, var(--xt-bg-ink));
}

.xt-coils__ticker {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--xt-space-2);
}

.xt-coils__filter-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-3);
  padding: var(--xt-space-3);
}

.xt-coils__filter-summary span,
.xt-coils__filter-summary small {
  position: relative;
  z-index: 1;
  color: color-mix(in srgb, var(--xt-text-inverse) 52%, transparent);
  font-size: var(--xt-text-xs);
  font-weight: 900;
}

.xt-coils__filter-summary strong {
  position: relative;
  z-index: 1;
  color: var(--xt-text-inverse);
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-lg);
  font-weight: 900;
}

.xt-coils__ticker article {
  display: grid;
  gap: 4px;
  min-height: 98px;
  padding: var(--xt-space-3);
}

.xt-coils__ticker span,
.xt-coils__panel-head small,
.xt-coils__identity span,
.xt-coils__route small,
.xt-coils__compare small,
.xt-coils__table small {
  color: color-mix(in srgb, var(--xt-text-inverse) 50%, transparent);
  font-size: var(--xt-text-xs);
  font-weight: 800;
}

.xt-coils__ticker strong {
  color: var(--xt-text-inverse);
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-2xl);
  font-weight: 900;
  font-variant-numeric: tabular-nums;
}

.xt-coils__ticker article.tone-warning {
  border-color: color-mix(in srgb, var(--xt-warning) 46%, var(--xt-border));
}

.xt-coils__ticker article.tone-success {
  border-color: color-mix(in srgb, var(--xt-success) 42%, var(--xt-border));
}

.xt-coils__layout {
  display: grid;
  grid-template-columns: minmax(0, 1.6fr) minmax(320px, 0.76fr);
  gap: var(--xt-space-4);
  align-items: start;
}

.xt-coils__table-panel,
.xt-coils__flow {
  display: grid;
  gap: var(--xt-space-3);
  padding: var(--xt-space-4);
}

.xt-coils__panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--xt-space-3);
}

.xt-coils__table-wrap {
  overflow: auto;
  border: 1px solid color-mix(in srgb, var(--xt-primary) 15%, var(--xt-border));
  border-radius: var(--xt-radius-lg);
  background: color-mix(in srgb, var(--xt-bg-ink) 50%, var(--xt-bg-panel));
}

.xt-coils__table {
  width: 100%;
  min-width: 920px;
  border-collapse: collapse;
  font-size: var(--xt-text-sm);
}

.xt-coils__table th,
.xt-coils__table td {
  padding: var(--xt-space-3);
  border-bottom: 1px solid color-mix(in srgb, var(--xt-primary) 8%, var(--xt-border));
  text-align: left;
  vertical-align: top;
  color: color-mix(in srgb, var(--xt-text-inverse) 80%, transparent);
}

.xt-coils__table th {
  color: color-mix(in srgb, var(--xt-text-inverse) 48%, transparent);
  font-size: var(--xt-text-xs);
  font-weight: 900;
  letter-spacing: 0.06em;
  white-space: nowrap;
}

.xt-coils__table tbody tr {
  cursor: pointer;
  transition:
    background-color var(--xt-motion-fast) var(--xt-ease),
    transform var(--xt-motion-fast) var(--xt-ease);
}

@media (hover: hover) {
  .xt-coils__table tbody tr:hover {
    background: color-mix(in srgb, var(--xt-primary) 6%, transparent);
    transform: translateX(2px);
  }
}

.xt-coils__table tbody tr.is-active {
  background: color-mix(in srgb, var(--xt-primary) 10%, transparent);
}

.xt-coils__table strong {
  display: block;
  color: var(--xt-text-inverse);
  font-weight: 900;
}

.xt-coils__coil-key {
  padding: 0;
  border: 0;
  background: transparent;
  color: color-mix(in srgb, var(--xt-primary) 82%, var(--xt-text-inverse));
  cursor: pointer;
  font: inherit;
  font-weight: 900;
  text-align: left;
}

.xt-coils__binding {
  display: inline-flex;
  padding: 2px 8px;
  border: 1px solid color-mix(in srgb, var(--xt-primary) 24%, var(--xt-border));
  border-radius: var(--xt-radius-pill);
  font-size: var(--xt-text-xs);
  font-weight: 900;
  white-space: nowrap;
}

.xt-coils__binding.tone-warning {
  border-color: color-mix(in srgb, var(--xt-warning) 44%, var(--xt-border));
  color: var(--xt-warning);
}

.xt-coils__binding.tone-success {
  border-color: color-mix(in srgb, var(--xt-success) 38%, var(--xt-border));
  color: var(--xt-success);
}

.xt-coils__binding.tone-muted {
  color: color-mix(in srgb, var(--xt-text-inverse) 46%, transparent);
}

.xt-coils__identity {
  display: grid;
  gap: 4px;
  padding: var(--xt-space-3);
  border: 1px solid color-mix(in srgb, var(--xt-primary) 15%, var(--xt-border));
  border-radius: var(--xt-radius-lg);
  background: color-mix(in srgb, var(--xt-bg-ink) 34%, transparent);
}

.xt-coils__identity strong {
  color: var(--xt-text-inverse);
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-xl);
  font-weight: 900;
}

.xt-coils__route,
.xt-coils__compare {
  display: grid;
  gap: var(--xt-space-2);
}

.xt-coils__route article,
.xt-coils__compare article {
  display: grid;
  gap: 5px;
  padding: var(--xt-space-3);
  border: 1px solid color-mix(in srgb, var(--xt-primary) 14%, var(--xt-border));
  border-radius: var(--xt-radius-lg);
  background: color-mix(in srgb, var(--xt-bg-ink) 30%, transparent);
}

.xt-coils__route article.is-current {
  border-color: color-mix(in srgb, var(--xt-primary) 34%, var(--xt-border));
  background: color-mix(in srgb, var(--xt-primary-light) 8%, transparent);
}

.xt-coils__route span,
.xt-coils__compare span {
  color: color-mix(in srgb, var(--xt-text-inverse) 48%, transparent);
  font-size: var(--xt-text-xs);
  font-weight: 900;
}

.xt-coils__route strong,
.xt-coils__compare strong {
  color: var(--xt-text-inverse);
  font-weight: 900;
}

.xt-coils__error {
  padding: var(--xt-space-2) var(--xt-space-3);
  border: 1px solid color-mix(in srgb, var(--xt-warning) 35%, var(--xt-border));
  border-radius: var(--xt-radius-md);
  background: color-mix(in srgb, var(--xt-warning-light) 10%, var(--xt-bg-panel));
  color: var(--xt-warning);
  font-size: var(--xt-text-sm);
  font-weight: 850;
}

.xt-coils__empty {
  text-align: center;
  color: color-mix(in srgb, var(--xt-text-inverse) 52%, transparent);
}

@media (max-width: 1120px) {
  .xt-coils__hero,
  .xt-coils__layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 760px) {
  .xt-coils__hero,
  .xt-coils__table-panel,
  .xt-coils__flow {
    padding: var(--xt-space-3);
  }

  .xt-coils__search,
  .xt-coils__ticker,
  .xt-coils__filter-summary {
    grid-template-columns: 1fr;
  }

  .xt-coils__filter-summary {
    display: grid;
    align-items: start;
  }

  .xt-coils__table {
    min-width: 0;
  }

  .xt-coils__table thead {
    display: none;
  }

  .xt-coils__table,
  .xt-coils__table tbody,
  .xt-coils__table tr,
  .xt-coils__table td {
    display: block;
  }

  .xt-coils__table tr {
    margin: var(--xt-space-2);
    border: 1px solid color-mix(in srgb, var(--xt-primary) 14%, var(--xt-border));
    border-radius: var(--xt-radius-lg);
  }

  .xt-coils__table td {
    display: grid;
    grid-template-columns: 84px minmax(0, 1fr);
    gap: var(--xt-space-2);
    padding: var(--xt-space-2);
  }

  .xt-coils__table td::before {
    color: color-mix(in srgb, var(--xt-text-inverse) 44%, transparent);
    content: attr(data-label);
    font-size: var(--xt-text-xs);
    font-weight: 900;
  }
}

@media (prefers-reduced-motion: reduce) {
  .xt-coils__table tbody tr {
    transition: none;
  }
}
</style>
