<template>
  <section
    class="page-stack energy-center"
    data-testid="energy-center-page"
    data-visual-pass="stitch-image2-second-pass"
    :data-stitch-project-id="stitchSurface.stitch.projectId"
    :data-stitch-screen-id="stitchSurface.stitch.screenId"
  >
    <header class="energy-center__hero">
      <div class="energy-center__hero-copy">
        <span class="energy-center__eyebrow">能耗总览</span>
        <h1>{{ statusBar.title }}</h1>
        <span class="energy-center__subtitle">{{ statusBar.subtitle }}</span>
      </div>
      <div class="energy-center__actions">
        <div class="energy-center__top-status" data-testid="energy-center-status-bar">
          <span :class="`energy-center__status-dot energy-center__status-dot--${statusBar.tone}`"></span>
          <strong>{{ statusBar.syncStatus }}</strong>
          <small>{{ statusBar.businessDate || '-' }} / {{ statusBar.rowCount }} 条</small>
          <small>页面刷新 {{ statusBar.updatedAt || '-' }}</small>
        </div>
        <DateSwitcher
          :model-value="filters.business_date"
          :loading="loading"
          :freshness="energyFreshness"
          @step="handleBusinessDateStep"
          @refresh="load"
          @pick="handleBusinessDatePick"
        />
      </div>
    </header>

    <div class="xt-second-pass-source-strip" data-testid="second-pass-source-strip" aria-label="数据来源">
      <span class="xt-second-pass-source-strip__item">MES 外部数据</span>
      <span class="xt-second-pass-source-strip__item">人工填报</span>
      <span class="xt-second-pass-source-strip__item">算法数据</span>
    </div>

    <section class="energy-center__stats" data-testid="energy-center-stats">
      <article
        v-for="item in energyStats"
        :key="item.key"
        class="energy-center__stat"
        :class="`energy-center__stat--${item.accent}`"
      >
        <div class="energy-center__stat-top">
          <span class="energy-center__led"></span>
          <span>{{ item.label }}</span>
        </div>
        <strong>{{ item.value }}</strong>
        <small>{{ item.unit }}</small>
      </article>
    </section>

    <section class="energy-center__body">
      <div class="energy-center__main">
        <section class="energy-center__flow" data-testid="energy-center-flow">
          <article
            v-for="item in stitchSurface.energyFlow"
            :key="`flow-${item.key}`"
            :class="[
              `energy-center__flow-card--${item.tone}`,
              item.emphasis ? `energy-center__flow-card--${item.emphasis}` : '',
            ]"
          >
            <span class="energy-center__flow-stage">{{ item.stage }}</span>
            <span
              class="energy-center__flow-icon"
              :class="item.icon ? `energy-center__flow-icon--${item.icon}` : ''"
            ></span>
            <div class="energy-center__flow-copy">
              <small>{{ item.label }}</small>
              <strong>{{ item.value }} <b>{{ item.unit }}</b></strong>
              <em>{{ item.source }}</em>
            </div>
          </article>
        </section>

        <section class="energy-center__matrix">
          <div class="energy-center__matrix-head">
            <div>
              <span class="energy-center__eyebrow">能耗明细</span>
              <h2>能耗明细表</h2>
            </div>
            <div class="energy-center__matrix-meta">
              <span>{{ stitchSurface.businessDate }}</span>
              <span>{{ energyRows.length }} 条</span>
            </div>
          </div>

          <div class="energy-center__table" data-testid="energy-center-table">
            <ReferenceDataTable :data="energyRows" stripe>
              <el-table-column prop="business_date" label="业务日期" width="100" />
              <el-table-column prop="workshop_code" label="车间" width="92">
                <template #default="{ row }">{{ formatWorkshopLabel(row.workshop_code) }}</template>
              </el-table-column>
              <el-table-column prop="shift_code" label="班次" width="84">
                <template #default="{ row }">
                  <span class="energy-center__shift">{{ formatShiftLabel(row.shift_code, '-') }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="electricity_value" label="电耗" width="76" align="right">
                <template #default="{ row }">{{ formatCell(row.electricity_value) }}</template>
              </el-table-column>
              <el-table-column prop="gas_value" label="气耗" width="76" align="right">
                <template #default="{ row }">{{ formatCell(row.gas_value) }}</template>
              </el-table-column>
              <el-table-column prop="water_value" label="水耗" width="76" align="right">
                <template #default="{ row }">{{ formatCell(row.water_value) }}</template>
              </el-table-column>
              <el-table-column prop="total_energy" label="总能耗" width="76" align="right">
                <template #default="{ row }">{{ formatCell(row.total_energy) }}</template>
              </el-table-column>
              <el-table-column prop="output_weight" label="产量" width="76" align="right">
                <template #default="{ row }">{{ formatCell(row.output_weight) }}</template>
              </el-table-column>
              <el-table-column prop="energy_per_ton" label="单吨能耗" width="84" align="right">
                <template #default="{ row }">
                  <strong class="energy-center__per-ton">{{ formatCell(row.energy_per_ton) }}</strong>
                </template>
              </el-table-column>
              <el-table-column prop="source_label" label="数据来源" width="104">
                <template #default="{ row }">
                  <span class="energy-center__source">{{ formatEnergySourceLabel(row) }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="source_updated_at" label="采集时间" width="112">
                <template #default="{ row }">{{ formatSourceUpdatedAt(row.source_updated_at) }}</template>
              </el-table-column>
            </ReferenceDataTable>
          </div>

          <div class="energy-center__mobile-list" data-testid="energy-center-mobile-list">
            <article
              v-for="row in energyRows"
              :key="`${row.business_date}-${row.workshop_code}-${row.shift_code}-${row.source || 'energy'}`"
            >
              <div class="energy-center__mobile-title">
                <span>{{ formatWorkshopLabel(row.workshop_code) }}</span>
                <em>{{ formatShiftLabel(row.shift_code, '-') }}</em>
              </div>
              <div class="energy-center__mobile-grid">
                <span>业务日期</span><strong>{{ row.business_date || '-' }}</strong>
                <span>电耗</span><strong>{{ formatCell(row.electricity_value) }}</strong>
                <span>气耗</span><strong>{{ formatCell(row.gas_value) }}</strong>
                <span>水耗</span><strong>{{ formatCell(row.water_value) }}</strong>
                <span>总能耗</span><strong>{{ formatCell(row.total_energy) }}</strong>
                <span>产量</span><strong>{{ formatCell(row.output_weight) }}</strong>
                <span>单吨能耗</span><strong>{{ formatCell(row.energy_per_ton) }}</strong>
                <span>数据来源</span><strong>{{ formatEnergySourceLabel(row) }}</strong>
                <span>采集时间</span><strong>{{ formatSourceUpdatedAt(row.source_updated_at) }}</strong>
              </div>
            </article>
          </div>
        </section>
      </div>

      <aside class="energy-center__event-rail" data-testid="energy-event-rail">
        <div class="energy-center__matrix-head">
          <div>
            <span class="energy-center__eyebrow">能耗监测</span>
            <h2>能耗关注</h2>
          </div>
        </div>
        <article
          v-for="item in eventRailItems"
          :key="item.key"
          class="energy-center__event"
          :class="`energy-center__event--${item.tone}`"
        >
          <div>
            <strong>{{ item.title }}</strong>
            <span>{{ item.value }}</span>
          </div>
          <em>{{ item.time || '-' }}</em>
        </article>
      </aside>
    </section>

    <footer class="energy-center__bottom-status" data-testid="stitch-bottom-status">
      <span
        v-for="item in bottomStatusItems"
        :key="item.key"
        :class="`energy-center__status-pill energy-center__status-pill--${item.tone}`"
      >
        {{ item.label }}：<strong>{{ item.value }}</strong>
      </span>
    </footer>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import dayjs from 'dayjs'

import { fetchEnergySummary } from '../../api/energy'
import DateSwitcher from '../../components/manage/DateSwitcher.vue'
import ReferenceDataTable from '../../components/reference/ReferenceDataTable.vue'
import { formatShiftLabel } from '../../utils/display'
import { inferLastCompletedBusinessDate } from '../../utils/shiftClock'
import { buildEnergyStitchSurface } from '../../utils/stitchManageSurface.js'
import { normalizeWorkshopName } from '../../utils/activeWorkshops.js'

const WORKSHOP_CODE_LABELS = {
  ZD: '铸锭',
  ZR2: '铸二',
  ZR3: '铸三',
  RZ: '热轧',
  CH: '淬火车间',
  JZ: '精整',
  LJ: '拉矫',
  JQ: '园区剪切',
  'ZXTF-N': '新厂在线',
  'ZXTF-P': '园区在线',
  LZ1650: '冷轧1650',
  LZ1850: '冷轧1850',
  LZ2050: '冷轧2050',
}

const ENERGY_WORKSHOP_DISPLAY_LABELS = {
  铸锭: '铸锭车间',
  铸二: '铸二车间',
  铸三: '铸三车间',
  热轧: '热轧车间',
  精整: '精整车间',
  拉矫: '拉矫车间',
  园区剪切: '园区剪切车间',
  新厂在线: '新厂在线退火',
  园区在线: '园区在线退火',
}

const filters = reactive({
  business_date: inferLastCompletedBusinessDate()
})
const rows = ref([])
const loading = ref(false)
const errorText = ref('')
const updatedAt = ref('')

const rawEnergyStats = computed(() => [
  { key: 'electricity', label: '电耗', value: formatStat(sumBy('electricity_value')), unit: 'kWh', accent: 'cyan' },
  { key: 'gas', label: '气耗', value: formatStat(sumBy('gas_value')), unit: 'm³', accent: 'amber' },
  { key: 'water', label: '水耗', value: formatStat(sumBy('water_value')), unit: 'm³', accent: 'blue' },
  { key: 'total', label: '总能耗', value: formatStat(sumBy('total_energy')), unit: 'kgce', accent: 'cyan' },
  { key: 'output', label: '产量', value: formatStat(sumBy('output_weight')), unit: '吨', accent: 'blue' },
  { key: 'per-ton-peak', label: '单吨峰值', value: formatStat(maxBy('energy_per_ton')), unit: 'kgce/吨', accent: 'amber' },
])
const stitchSurface = computed(() => buildEnergyStitchSurface({
  targetDate: filters.business_date,
  kpiItems: rawEnergyStats.value,
  detailRows: rows.value,
  runtimeState: {
    loading: loading.value,
    errorText: errorText.value,
    updatedAt: updatedAt.value,
  },
}))
const statusBar = computed(() => stitchSurface.value.statusBar)
const energyStats = computed(() => stitchSurface.value.kpiStrip)
const energyRows = computed(() => stitchSurface.value.detailRows)
const eventRailItems = computed(() => stitchSurface.value.eventRail)
const bottomStatusItems = computed(() => stitchSurface.value.bottomStatus)
const energyFreshness = computed(() => {
  const tone = statusBar.value.tone
  if (tone === 'success') return 'green'
  if (tone === 'danger') return 'red'
  return 'yellow'
})

function toNumber(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number : 0
}

function sumBy(key) {
  return rows.value.reduce((total, row) => total + toNumber(row?.[key]), 0)
}

function maxBy(key) {
  return rows.value.reduce((max, row) => Math.max(max, toNumber(row?.[key])), 0)
}

function formatStat(value) {
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(value)
}

function formatCell(value) {
  if (value === null || value === undefined || value === '') return '-'
  return formatStat(toNumber(value))
}

function formatWorkshopLabel(value) {
  const text = String(value || '').trim()
  if (!text) return '-'
  const normalized = WORKSHOP_CODE_LABELS[text] || normalizeWorkshopName(text)
  return ENERGY_WORKSHOP_DISPLAY_LABELS[normalized] || normalized
}

function formatEnergySourceLabel(row = {}) {
  if (row.source_label) return row.source_label
  if (row.source === 'mes_packaging_output_basis') return 'MES包装产量'
  if (row.source === 'iot_shadow') return '物联网采集'
  if (row.source === 'mobile_shift_report') return '电工填报'
  if (row.source === 'owner_only') return '内勤填报'
  if (row.source === 'energy_import') return '旧导入'
  return row.source || '-'
}

function formatSourceUpdatedAt(value) {
  if (!value) return '-'
  const parsed = dayjs(value)
  return parsed.isValid() ? parsed.format('HH:mm:ss') : '-'
}

function formatRefreshTime(date = new Date()) {
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date)
}

function resolveEnergyErrorText(error) {
  const status = error?.response?.status
  if (status === 401) return '请先登录后查看能耗数据'
  if (status === 403) return '无权限查看能耗数据'
  return error?.response?.data?.detail || error?.message || '能耗数据加载失败'
}

async function load() {
  loading.value = true
  errorText.value = ''
  try {
    rows.value = await fetchEnergySummary({ business_date: filters.business_date })
  } catch (error) {
    errorText.value = resolveEnergyErrorText(error)
    rows.value = []
  } finally {
    updatedAt.value = formatRefreshTime()
    loading.value = false
  }
}

function setBusinessDate(value) {
  if (!value || value === filters.business_date) return
  filters.business_date = value
  void load()
}

function handleBusinessDateStep(deltaDays) {
  setBusinessDate(dayjs(filters.business_date).add(deltaDays, 'day').format('YYYY-MM-DD'))
}

function handleBusinessDatePick(value) {
  setBusinessDate(value)
}

onMounted(load)
</script>

<style scoped>
.energy-center {
  --energy-cyan: #00f2ff;
  --energy-cyan-soft: rgba(0, 242, 255, 0.16);
  --energy-amber: #ffab00;
  --energy-blue: #74f5ff;
  --energy-bg: #06101f;
  --energy-panel: rgba(12, 25, 42, 0.72);
  --energy-line: rgba(0, 242, 255, 0.18);
  --energy-muted: rgba(223, 226, 235, 0.66);
  color: #dfe2eb;
}

.energy-center::before {
  position: fixed;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  content: '';
  background:
    radial-gradient(circle at 12% 10%, rgba(0, 242, 255, 0.12), transparent 28%),
    linear-gradient(rgba(0, 242, 255, 0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 242, 255, 0.035) 1px, transparent 1px),
    linear-gradient(135deg, #0a0e14, var(--energy-bg));
  background-size: auto, 32px 32px, 32px 32px, auto;
}

.energy-center__hero,
.energy-center__matrix,
.energy-center__flow article,
.energy-center__event-rail,
.energy-center__event,
.energy-center__bottom-status,
.energy-center__stat,
.energy-center__mobile-list article {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--energy-line);
  background: linear-gradient(180deg, rgba(38, 42, 49, 0.54), var(--energy-panel));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06), 0 12px 28px rgba(0, 0, 0, 0.18);
}

.energy-center__hero::after,
.energy-center__matrix::after,
.energy-center__flow article::after,
.energy-center__stat::after {
  position: absolute;
  top: 0;
  right: 18px;
  left: 18px;
  height: 1px;
  pointer-events: none;
  content: '';
  background: linear-gradient(90deg, transparent, rgba(0, 242, 255, 0.16), transparent);
}

.energy-center__hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  min-height: 152px;
  padding: 28px;
  border-radius: 18px;
}

.energy-center__hero-copy {
  position: relative;
  z-index: 1;
}

.energy-center__eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--energy-cyan);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.16em;
}

.energy-center__eyebrow::before {
  width: 8px;
  height: 8px;
  content: '';
  border-radius: 999px;
  background: var(--energy-cyan);
  box-shadow: 0 0 0 3px rgba(0, 242, 255, 0.18);
}

.energy-center h1,
.energy-center h2 {
  margin: 0;
  color: #f6fbff;
  font-family: 'Hanken Grotesk', 'Inter', sans-serif;
  letter-spacing: -0.03em;
}

.energy-center h1 {
  margin-top: 12px;
  font-size: clamp(34px, 5vw, 58px);
  line-height: 1;
}

.energy-center__subtitle {
  display: block;
  margin-top: 10px;
  color: var(--energy-muted);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.16em;
}

.energy-center h2 {
  margin-top: 8px;
  font-size: 24px;
}

.energy-center__actions {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px;
  border: 1px solid rgba(0, 242, 255, 0.14);
  border-radius: 14px;
  background: rgba(6, 16, 31, 0.58);
}

.energy-center__top-status {
  display: inline-grid;
  grid-template-columns: auto 1fr;
  gap: 3px 8px;
  align-items: center;
  min-width: 190px;
  padding: 8px 12px;
  border: 1px solid rgba(0, 242, 255, 0.18);
  border-radius: 12px;
  background: rgba(0, 242, 255, 0.07);
}

.energy-center__top-status strong {
  color: #f6fbff;
  font-size: 14px;
}

.energy-center__top-status small {
  grid-column: 2;
  color: var(--energy-muted);
  font-size: 11px;
  font-weight: 700;
  white-space: nowrap;
}

.energy-center__status-dot {
  width: 9px;
  height: 9px;
  border-radius: 999px;
  background: currentColor;
  box-shadow: 0 0 0 3px color-mix(in srgb, currentColor 18%, transparent);
}

.energy-center__status-dot--success {
  color: #72f5ad;
}

.energy-center__status-dot--warning {
  color: var(--energy-amber);
}

.energy-center__status-dot--danger {
  color: #ff7777;
}

.energy-center__stats {
  display: grid;
  grid-template-columns: repeat(6, minmax(0, 1fr));
  gap: 16px;
}

.energy-center__stat {
  min-height: 132px;
  padding: 18px;
  border-radius: 16px;
}

.energy-center__stat-top {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--energy-muted);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
}

.energy-center__led {
  width: 9px;
  height: 9px;
  border-radius: 999px;
  background: currentColor;
  box-shadow: 0 0 0 3px color-mix(in srgb, currentColor 18%, transparent);
}

.energy-center__stat strong {
  position: relative;
  z-index: 1;
  display: block;
  margin-top: 24px;
  color: var(--energy-cyan);
  font-family: 'Hanken Grotesk', 'Inter', sans-serif;
  font-size: clamp(24px, 3vw, 38px);
  line-height: 1;
}

.energy-center__stat small {
  position: relative;
  z-index: 1;
  display: block;
  margin-top: 8px;
  color: var(--energy-muted);
  font-size: 12px;
}

.energy-center__stat--amber strong,
.energy-center__stat--amber .energy-center__led {
  color: var(--energy-amber);
}

.energy-center__stat--blue strong,
.energy-center__stat--blue .energy-center__led {
  color: var(--energy-blue);
}

.energy-center__body {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(280px, 340px);
  gap: 16px;
  align-items: start;
}

.energy-center__main {
  display: grid;
  min-width: 0;
  gap: 16px;
}

.energy-center__flow {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}

.energy-center__flow article {
  position: relative;
  display: flex;
  align-items: flex-start;
  flex-direction: column;
  gap: 10px;
  min-height: 140px;
  padding: 34px 16px 16px;
  border-radius: 16px;
}

.energy-center__flow article:not(:last-child)::before {
  position: absolute;
  top: 50%;
  right: -11px;
  z-index: 2;
  color: var(--energy-cyan);
  content: '>';
  font-size: 22px;
  font-weight: 900;
  line-height: 1;
  transform: translateY(-50%);
}

.energy-center__flow-stage {
  position: absolute;
  top: 10px;
  left: 14px;
  z-index: 1;
  padding: 2px 8px;
  border: 1px solid rgba(0, 242, 255, 0.24);
  border-radius: 999px;
  background: rgba(0, 242, 255, 0.08);
  color: var(--energy-cyan);
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.08em;
}

.energy-center__flow-icon {
  position: relative;
  width: 34px;
  height: 34px;
  flex: 0 0 auto;
  border: 1px solid rgba(0, 242, 255, 0.38);
  border-radius: 12px;
  background:
    linear-gradient(135deg, rgba(0, 242, 255, 0.12), rgba(0, 96, 255, 0.18)),
    radial-gradient(circle at 50% 50%, rgba(0, 242, 255, 0.5), transparent 52%);
  box-shadow: inset 0 0 0 1px rgba(0, 242, 255, 0.16);
}

.energy-center__flow-icon::before,
.energy-center__flow-icon::after {
  position: absolute;
  content: '';
}

.energy-center__flow-icon--meter::before {
  inset: 8px 9px 10px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  opacity: 0.82;
}

.energy-center__flow-icon--meter::after {
  right: 9px;
  bottom: 11px;
  width: 12px;
  height: 2px;
  border-radius: 999px;
  background: currentColor;
  transform: rotate(-32deg);
  transform-origin: right center;
}

.energy-center__flow-icon--flame::before {
  inset: 7px 10px 6px;
  border-radius: 48% 52% 56% 44%;
  background: linear-gradient(180deg, rgba(255, 221, 126, 0.92), rgba(255, 124, 57, 0.28));
  clip-path: polygon(50% 0, 74% 30%, 66% 56%, 86% 100%, 18% 100%, 36% 56%, 28% 30%);
}

.energy-center__flow-icon--water::before {
  left: 8px;
  right: 8px;
  top: 9px;
  height: 18px;
  border-radius: 50% 50% 56% 56%;
  background: linear-gradient(180deg, rgba(116, 245, 255, 0.88), rgba(0, 242, 255, 0.18));
  clip-path: polygon(50% 0, 86% 56%, 72% 100%, 28% 100%, 14% 56%);
}

.energy-center__flow-icon--converter::before {
  inset: 9px 7px;
  border: 2px solid currentColor;
  border-radius: 6px;
  opacity: 0.82;
}

.energy-center__flow-icon--converter::after {
  left: 10px;
  right: 10px;
  top: 16px;
  height: 2px;
  border-radius: 999px;
  background: currentColor;
  box-shadow: 0 -5px 0 rgba(114, 245, 173, 0.42), 0 5px 0 rgba(114, 245, 173, 0.42);
}

.energy-center__flow-icon--gauge::before {
  inset: 7px 8px 10px;
  border: 2px solid currentColor;
  border-bottom-color: transparent;
  border-radius: 50% 50% 0 0;
  opacity: 0.88;
}

.energy-center__flow-icon--gauge::after {
  left: 16px;
  bottom: 10px;
  width: 11px;
  height: 2px;
  border-radius: 999px;
  background: currentColor;
  transform: rotate(-48deg);
  transform-origin: left center;
}

.energy-center__flow-card--amber .energy-center__flow-icon,
.energy-center__flow-card--warning .energy-center__flow-icon,
.energy-center__flow-card--critical .energy-center__flow-icon {
  border-color: rgba(255, 176, 32, 0.42);
  background:
    linear-gradient(135deg, rgba(255, 176, 32, 0.12), rgba(0, 96, 255, 0.12)),
    radial-gradient(circle at 50% 50%, rgba(255, 176, 32, 0.48), transparent 52%);
  box-shadow: inset 0 0 0 1px rgba(255, 176, 32, 0.16);
}

.energy-center__flow-card--result,
.energy-center__flow-card--critical {
  border-width: 1px;
  transform: translateY(-4px);
}

.energy-center__flow-card--result {
  border-color: rgba(62, 255, 197, 0.46);
  background:
    radial-gradient(circle at 74% 12%, rgba(62, 255, 197, 0.18), transparent 36%),
    linear-gradient(180deg, rgba(12, 56, 72, 0.72), rgba(9, 23, 38, 0.9));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08), 0 8px 18px rgba(0, 0, 0, 0.16);
}

.energy-center__flow-card--critical {
  border-color: rgba(255, 176, 32, 0.54);
  background:
    radial-gradient(circle at 74% 12%, rgba(255, 176, 32, 0.18), transparent 36%),
    linear-gradient(180deg, rgba(72, 46, 12, 0.66), rgba(18, 20, 30, 0.92));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08), 0 8px 18px rgba(0, 0, 0, 0.16);
}

.energy-center__flow-card--endpoint .energy-center__flow-stage {
  border-color: currentColor;
  background: rgba(255, 255, 255, 0.08);
}

.energy-center__flow-card--result .energy-center__flow-stage,
.energy-center__flow-card--result strong,
.energy-center__flow-card--result .energy-center__flow-icon {
  color: #72f5ad;
}

.energy-center__flow-card--critical .energy-center__flow-stage,
.energy-center__flow-card--critical strong {
  color: var(--energy-amber);
}

.energy-center__flow-card--result .energy-center__flow-icon {
  border-color: rgba(114, 245, 173, 0.46);
  background:
    linear-gradient(135deg, rgba(114, 245, 173, 0.14), rgba(0, 242, 255, 0.18)),
    radial-gradient(circle at 50% 50%, rgba(114, 245, 173, 0.48), transparent 52%);
  box-shadow: inset 0 0 0 1px rgba(114, 245, 173, 0.2);
}

.energy-center__flow-card--endpoint strong {
  font-size: 20px;
}

.energy-center__flow-copy {
  width: 100%;
  min-width: 0;
}

.energy-center__flow small,
.energy-center__event span {
  display: block;
  color: var(--energy-muted);
  font-size: 12px;
  font-weight: 700;
}

.energy-center__flow strong,
.energy-center__event strong {
  position: relative;
  z-index: 1;
  display: block;
  margin-top: 6px;
  color: #f6fbff;
  font-family: 'Hanken Grotesk', 'Inter', sans-serif;
  font-size: 20px;
}

.energy-center__flow strong {
  font-size: 18px;
  line-height: 1.22;
}

.energy-center__flow strong b {
  color: var(--energy-muted);
  font-size: 12px;
  font-weight: 800;
}

.energy-center__flow em {
  display: block;
  margin-top: 8px;
  color: rgba(143, 174, 203, 0.8);
  font-size: 11px;
  font-style: normal;
  font-weight: 800;
}

.energy-center__matrix {
  border-radius: 18px;
}

.energy-center__matrix-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 22px 24px;
  border-bottom: 1px solid var(--energy-line);
  background: rgba(0, 242, 255, 0.045);
}

.energy-center__matrix-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: flex-end;
}

.energy-center__matrix-meta span,
.energy-center__shift,
.energy-center__source {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 5px 10px;
  border: 1px solid rgba(0, 242, 255, 0.18);
  border-radius: 999px;
  background: rgba(0, 242, 255, 0.08);
  color: #dfe2eb;
  font-size: 12px;
  font-style: normal;
  font-weight: 700;
}

.energy-center__table {
  padding: 16px;
}

.energy-center__table :deep(.el-table) {
  --el-table-header-bg-color: rgba(0, 242, 255, 0.08);
  --el-table-tr-bg-color: transparent;
  --el-table-row-hover-bg-color: rgba(0, 242, 255, 0.08);
  --el-table-border-color: rgba(0, 242, 255, 0.14);
  --el-table-header-text-color: #74f5ff;
  --el-table-text-color: #dfe2eb;
  overflow: hidden;
  border: 1px solid rgba(0, 242, 255, 0.14);
  border-radius: 14px;
  background: transparent;
}

.energy-center__table :deep(.el-table th.el-table__cell) {
  font-size: 12px;
  letter-spacing: 0.08em;
  background: rgba(0, 242, 255, 0.08);
}

.energy-center__table :deep(.el-table th.el-table__cell > .cell) {
  color: #74f5ff;
}

.energy-center__table :deep(.el-table td.el-table__cell) {
  background: rgba(10, 14, 20, 0.32);
}

.energy-center__table :deep(.el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell) {
  background: rgba(0, 242, 255, 0.045);
}

.energy-center__table :deep(.el-table__inner-wrapper::before),
.energy-center__table :deep(.el-table__inner-wrapper::after) {
  background: rgba(0, 242, 255, 0.14);
}

.energy-center__per-ton {
  color: var(--energy-cyan);
}

.energy-center__event-rail {
  overflow: hidden;
  border-radius: 18px;
}

.energy-center__event {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  margin: 14px;
  padding: 16px;
  border-radius: 14px;
}

.energy-center__event em {
  color: var(--energy-muted);
  font-size: 12px;
  font-style: normal;
  white-space: nowrap;
}

.energy-center__event--success {
  border-color: rgba(65, 232, 137, 0.28);
}

.energy-center__event--success strong {
  color: #72f5ad;
}

.energy-center__event--warning {
  border-color: rgba(255, 171, 0, 0.28);
}

.energy-center__event--warning strong {
  color: var(--energy-amber);
}

.energy-center__event--danger {
  border-color: rgba(255, 87, 87, 0.34);
}

.energy-center__event--danger strong {
  color: #ff7777;
}

.energy-center__bottom-status {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: space-between;
  padding: 14px 18px;
  border-radius: 16px;
}

.energy-center__status-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  color: var(--energy-muted);
  font-size: 13px;
}

.energy-center__status-pill strong {
  color: #f6fbff;
}

.energy-center__status-pill--success strong {
  color: #72f5ad;
}

.energy-center__status-pill--warning strong {
  color: var(--energy-amber);
}

.energy-center__status-pill--danger strong {
  color: #ff7777;
}

.energy-center__mobile-list {
  display: none;
  padding: 16px;
}

.energy-center__mobile-list article {
  border-radius: 16px;
  padding: 16px;
}

.energy-center__mobile-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
  color: #f6fbff;
  font-weight: 800;
}

.energy-center__mobile-title em {
  padding: 4px 9px;
  border-radius: 999px;
  background: var(--energy-cyan-soft);
  color: var(--energy-cyan);
  font-size: 12px;
  font-style: normal;
}

.energy-center__mobile-grid {
  display: grid;
  grid-template-columns: minmax(76px, auto) 1fr;
  gap: 10px 14px;
  color: var(--energy-muted);
  font-size: 13px;
}

.energy-center__mobile-grid strong {
  color: #eafcff;
  text-align: right;
}

@media (max-width: 1080px) {
  .energy-center__body {
    grid-template-columns: 1fr;
  }

  .energy-center__flow {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .energy-center__flow article:nth-child(2n)::before {
    display: none;
  }

  .energy-center__stats {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .energy-center__hero,
  .energy-center__matrix-head {
    align-items: stretch;
    flex-direction: column;
  }

  .energy-center__hero {
    padding: 22px;
  }

  .energy-center__actions {
    flex-direction: column;
    align-items: stretch;
  }

  .energy-center__actions :deep(.xt-date-switcher) {
    width: 100%;
    flex-wrap: wrap;
  }

  .energy-center__actions :deep(.xt-date-switcher__label) {
    flex: 1 1 auto;
    justify-content: center;
  }

  .energy-center__stats {
    grid-template-columns: 1fr;
  }

  .energy-center__flow {
    grid-template-columns: 1fr;
  }

  .energy-center__flow article::before {
    display: none;
  }

  .energy-center__table {
    display: none;
  }

  .energy-center__mobile-list {
    display: grid;
    gap: 12px;
  }
}
</style>
