<template>
  <section class="page-stack energy-center" data-testid="energy-center-page">
    <header class="energy-center__hero">
      <div class="energy-center__hero-copy">
        <span class="energy-center__eyebrow">ENERGY COMMAND</span>
        <h1>能耗中心</h1>
      </div>
      <div class="energy-center__actions">
        <el-date-picker
          v-model="filters.business_date"
          class="energy-center__date"
          type="date"
          value-format="YYYY-MM-DD"
        />
        <el-button class="energy-center__refresh" @click="load">刷新</el-button>
      </div>
    </header>

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

    <section class="energy-center__matrix">
      <div class="energy-center__matrix-head">
        <div>
          <span class="energy-center__eyebrow">ENERGY MATRIX</span>
          <h2>能耗明细表</h2>
        </div>
        <div class="energy-center__matrix-meta">
          <span>{{ filters.business_date }}</span>
          <span>{{ rows.length }} 条</span>
        </div>
      </div>

      <div class="energy-center__table" data-testid="energy-center-table">
        <ReferenceDataTable :data="rows" stripe>
          <el-table-column prop="business_date" label="业务日期" width="120" />
          <el-table-column prop="workshop_code" label="车间" width="120" />
          <el-table-column prop="shift_code" label="班次" width="120">
            <template #default="{ row }">
              <span class="energy-center__shift">{{ row.shift_code || '-' }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="electricity_value" label="电耗" width="120" align="right">
            <template #default="{ row }">{{ formatCell(row.electricity_value) }}</template>
          </el-table-column>
          <el-table-column prop="gas_value" label="气耗" width="120" align="right">
            <template #default="{ row }">{{ formatCell(row.gas_value) }}</template>
          </el-table-column>
          <el-table-column prop="water_value" label="水耗" width="120" align="right">
            <template #default="{ row }">{{ formatCell(row.water_value) }}</template>
          </el-table-column>
          <el-table-column prop="total_energy" label="总能耗" width="120" align="right">
            <template #default="{ row }">{{ formatCell(row.total_energy) }}</template>
          </el-table-column>
          <el-table-column prop="output_weight" label="产量" width="120" align="right">
            <template #default="{ row }">{{ formatCell(row.output_weight) }}</template>
          </el-table-column>
          <el-table-column prop="energy_per_ton" label="单吨能耗" width="120" align="right">
            <template #default="{ row }">
              <strong class="energy-center__per-ton">{{ formatCell(row.energy_per_ton) }}</strong>
            </template>
          </el-table-column>
        </ReferenceDataTable>
      </div>

      <div class="energy-center__mobile-list" data-testid="energy-center-mobile-list">
        <article v-for="row in rows" :key="`${row.business_date}-${row.workshop_code}-${row.shift_code}`">
          <div class="energy-center__mobile-title">
            <span>{{ row.workshop_code || '-' }}</span>
            <em>{{ row.shift_code || '-' }}</em>
          </div>
          <div class="energy-center__mobile-grid">
            <span>业务日期</span><strong>{{ row.business_date || '-' }}</strong>
            <span>电耗</span><strong>{{ formatCell(row.electricity_value) }}</strong>
            <span>气耗</span><strong>{{ formatCell(row.gas_value) }}</strong>
            <span>水耗</span><strong>{{ formatCell(row.water_value) }}</strong>
            <span>总能耗</span><strong>{{ formatCell(row.total_energy) }}</strong>
            <span>产量</span><strong>{{ formatCell(row.output_weight) }}</strong>
            <span>单吨能耗</span><strong>{{ formatCell(row.energy_per_ton) }}</strong>
          </div>
        </article>
      </div>
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import dayjs from 'dayjs'

import { fetchEnergySummary } from '../../api/energy'
import ReferenceDataTable from '../../components/reference/ReferenceDataTable.vue'

const filters = reactive({
  business_date: dayjs().format('YYYY-MM-DD')
})
const rows = ref([])

const energyStats = computed(() => [
  { key: 'electricity', label: '电耗', value: formatStat(sumBy('electricity_value')), unit: 'kWh', accent: 'cyan' },
  { key: 'gas', label: '气耗', value: formatStat(sumBy('gas_value')), unit: 'm³', accent: 'amber' },
  { key: 'water', label: '水耗', value: formatStat(sumBy('water_value')), unit: 'm³', accent: 'blue' },
  { key: 'total', label: '总能耗', value: formatStat(sumBy('total_energy')), unit: 'kgce', accent: 'cyan' }
])

function toNumber(value) {
  const number = Number(value)
  return Number.isFinite(number) ? number : 0
}

function sumBy(key) {
  return rows.value.reduce((total, row) => total + toNumber(row?.[key]), 0)
}

function formatStat(value) {
  return new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(value)
}

function formatCell(value) {
  if (value === null || value === undefined || value === '') return '-'
  return formatStat(toNumber(value))
}

async function load() {
  rows.value = await fetchEnergySummary({ business_date: filters.business_date })
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
.energy-center__stat,
.energy-center__mobile-list article {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--energy-line);
  background: linear-gradient(180deg, rgba(38, 42, 49, 0.54), var(--energy-panel));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06), 0 20px 54px rgba(0, 0, 0, 0.22);
  backdrop-filter: blur(14px);
}

.energy-center__hero::after,
.energy-center__matrix::after,
.energy-center__stat::after {
  position: absolute;
  inset: 0;
  pointer-events: none;
  content: '';
  background: linear-gradient(115deg, transparent 0%, rgba(0, 242, 255, 0.14) 42%, transparent 62%);
  transform: translateX(-120%);
  animation: energyCenterSweep 7s ease-in-out infinite;
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
  box-shadow: 0 0 18px var(--energy-cyan);
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
  text-shadow: 0 0 28px rgba(0, 242, 255, 0.22);
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

.energy-center__date {
  width: 178px;
}

.energy-center :deep(.energy-center__date .el-input__wrapper) {
  background: rgba(10, 14, 20, 0.74);
  box-shadow: 0 0 0 1px rgba(0, 242, 255, 0.22) inset;
}

.energy-center :deep(.energy-center__date .el-input__inner),
.energy-center :deep(.energy-center__date .el-input__prefix) {
  color: #dfe2eb;
}

.energy-center__refresh {
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(0, 242, 255, 0.46);
  background: rgba(0, 242, 255, 0.12);
  color: var(--energy-cyan);
  font-weight: 700;
}

.energy-center__refresh:hover {
  border-color: var(--energy-cyan);
  background: rgba(0, 242, 255, 0.2);
  box-shadow: 0 0 24px rgba(0, 242, 255, 0.22);
}

.energy-center__stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.energy-center__stat {
  min-height: 144px;
  padding: 20px;
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
  box-shadow: 0 0 16px currentColor;
  animation: energyCenterPulse 1.8s ease-in-out infinite;
}

.energy-center__stat strong {
  position: relative;
  z-index: 1;
  display: block;
  margin-top: 24px;
  color: var(--energy-cyan);
  font-family: 'Hanken Grotesk', 'Inter', sans-serif;
  font-size: clamp(30px, 4vw, 46px);
  line-height: 1;
  text-shadow: 0 0 22px rgba(0, 242, 255, 0.34);
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
.energy-center__shift {
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
  text-shadow: 0 0 16px rgba(0, 242, 255, 0.26);
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

@keyframes energyCenterSweep {
  0%,
  70% {
    transform: translateX(-120%);
  }

  100% {
    transform: translateX(120%);
  }
}

@keyframes energyCenterPulse {
  0%,
  100% {
    opacity: 0.56;
    transform: scale(0.88);
  }

  50% {
    opacity: 1;
    transform: scale(1.18);
  }
}

@media (max-width: 1080px) {
  .energy-center__stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
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

  .energy-center__date {
    width: 100%;
  }

  .energy-center__stats {
    grid-template-columns: 1fr;
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
