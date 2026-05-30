<template>
  <section class="dr-page">
    <header class="dr-header">
      <div class="dr-header__title">
        <h1>鑫泰铝业 | 生产经营日报总览</h1>
        <span class="dr-header__date">数据日期：{{ data?.target_date || '—' }}</span>
      </div>
      <DateSwitcher
        :model-value="targetDate"
        :loading="loading"
        @step="stepDate"
        @refresh="load"
        @pick="onPick"
      />
    </header>

    <KpiBar :items="kpiItems" />

    <div class="dr-grid-3">
      <!-- 出勤情况 -->
      <div class="panel dr-panel">
        <h3 class="dr-panel__title">出勤情况</h3>
        <div v-if="!data?.attendance" class="dr-empty">暂无数据</div>
      </div>

      <!-- 在制料分布 -->
      <div class="panel dr-panel">
        <h3 class="dr-panel__title">在制料分布
          <span class="dr-panel__badge">总计 {{ fmtNum(wipTotal) }} 吨</span>
        </h3>
        <div v-if="wip.length" class="dr-wip-grid">
          <div v-for="w in wip" :key="w.workshop" class="dr-wip-card">
            <div class="dr-wip-card__name">{{ w.workshop }}</div>
            <div class="dr-wip-card__value">{{ fmtNum(w.total_weight) }}<small>吨</small></div>
            <div class="dr-wip-card__count">{{ w.coil_count }} 卷</div>
          </div>
        </div>
        <div v-else class="dr-empty">暂无数据</div>
      </div>

      <!-- 合同与投料 -->
      <div class="panel dr-panel">
        <h3 class="dr-panel__title">合同与投料</h3>
        <template v-if="data?.contracts">
          <div class="dr-stat-rows">
            <div class="dr-stat-row">
              <span class="dr-stat-row__label">当天接合同</span>
              <span class="dr-stat-row__value">{{ data.contracts.daily_new }} <small>个</small></span>
            </div>
            <div class="dr-stat-row">
              <span class="dr-stat-row__label">月累计合同</span>
              <span class="dr-stat-row__value">{{ fmtNum(data.contracts.monthly_total) }} <small>个</small></span>
            </div>
            <div class="dr-stat-row">
              <span class="dr-stat-row__label">总余合同量</span>
              <span class="dr-stat-row__value tone-accent">{{ fmtNum(data.contracts.remaining) }} <small>个</small></span>
            </div>
            <div v-if="data.contracts.remaining_delta" class="dr-stat-row__delta">
              比昨日 {{ data.contracts.remaining_delta >= 0 ? '↑' : '↓' }}{{ Math.abs(data.contracts.remaining_delta) }}
            </div>
          </div>
        </template>
        <div v-else class="dr-empty">暂无数据</div>
      </div>
    </div>

    <!-- 车间产量概览 -->
    <div class="panel dr-panel dr-panel--wide">
      <h3 class="dr-panel__title">车间产量概览</h3>
      <table v-if="workshops.length" class="dr-table">
        <thead>
          <tr>
            <th>车间</th>
            <th class="num">下机量（吨）</th>
            <th class="num">比昨日</th>
            <th class="num">月累计（吨）</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="w in workshops" :key="w.workshop_id">
            <td>{{ w.workshop }}</td>
            <td class="num">{{ fmtNum(w.daily_output) }}</td>
            <td class="num" :class="deltaClass(w.delta)">{{ fmtDelta(w.delta) }}</td>
            <td class="num">{{ fmtNum(w.monthly_output) }}</td>
          </tr>
          <tr class="dr-table__total">
            <td>过站合计</td>
            <td class="num">{{ fmtNum(totalToday) }}</td>
            <td class="num" :class="deltaClass(totalToday - totalYesterday)">{{ fmtDelta(totalToday - totalYesterday) }}</td>
            <td class="num">{{ fmtNum(totalMonthly) }}</td>
          </tr>
        </tbody>
      </table>
      <div v-else class="dr-empty">暂无数据</div>
    </div>

    <div class="dr-grid-2">
      <!-- 能耗总览 -->
      <div class="panel dr-panel">
        <h3 class="dr-panel__title">能耗总览</h3>
        <template v-if="data?.energy">
          <div class="dr-stat-rows">
            <div class="dr-stat-row">
              <span class="dr-stat-row__label">总用电</span>
              <span class="dr-stat-row__value">{{ fmtNum(data.energy.total_electricity) }} <small>度</small></span>
            </div>
            <div class="dr-stat-row">
              <span class="dr-stat-row__label">总用气</span>
              <span class="dr-stat-row__value">{{ fmtNum(data.energy.total_gas) }} <small>m³</small></span>
            </div>
            <div class="dr-stat-row">
              <span class="dr-stat-row__label">电费</span>
              <span class="dr-stat-row__value">{{ data.energy.electricity_cost }} <small>万元</small></span>
            </div>
            <div class="dr-stat-row">
              <span class="dr-stat-row__label">气费</span>
              <span class="dr-stat-row__value">{{ data.energy.gas_cost }} <small>万元</small></span>
            </div>
            <div class="dr-stat-row dr-stat-row--highlight">
              <span class="dr-stat-row__label">能耗合计</span>
              <span class="dr-stat-row__value tone-accent">{{ data.energy.total_cost }} <small>万元</small></span>
            </div>
          </div>
          <table v-if="data.energy.by_workshop?.length" class="dr-table dr-table--compact">
            <thead><tr><th>车间</th><th class="num">日电耗(度)</th><th class="num">日气耗(m³)</th></tr></thead>
            <tbody>
              <tr v-for="e in data.energy.by_workshop" :key="e.workshop">
                <td>{{ e.workshop }}</td>
                <td class="num">{{ fmtNum(e.daily_electricity) }}</td>
                <td class="num">{{ fmtNum(e.daily_gas) }}</td>
              </tr>
            </tbody>
          </table>
        </template>
        <div v-else class="dr-empty">暂无数据</div>
      </div>

      <!-- 成品率 + 油品 + 成本 -->
      <div class="dr-stack">
        <!-- 成品率 -->
        <div class="panel dr-panel">
          <h3 class="dr-panel__title">成品率与运营指标</h3>
          <template v-if="data?.yield_rates?.daily != null">
            <div class="dr-yield-grid">
              <div class="dr-yield-card">
                <div class="dr-yield-card__label">日成品率</div>
                <div class="dr-yield-card__value">{{ data.yield_rates.daily }}%</div>
                <div class="dr-yield-card__delta" :class="deltaClass(data.yield_rates.daily_delta)">
                  {{ fmtDelta(data.yield_rates.daily_delta) }}%
                </div>
              </div>
              <div v-if="data.yield_rates.monthly != null" class="dr-yield-card">
                <div class="dr-yield-card__label">月成品率</div>
                <div class="dr-yield-card__value">{{ data.yield_rates.monthly }}%</div>
              </div>
            </div>
          </template>
          <div v-else class="dr-empty">暂无数据</div>
        </div>

        <!-- 油品 -->
        <div class="panel dr-panel">
          <h3 class="dr-panel__title">油品领取情况</h3>
          <div class="dr-empty">暂无数据</div>
        </div>

        <!-- 成本核算 -->
        <div class="panel dr-panel">
          <h3 class="dr-panel__title">成本核算（约）</h3>
          <template v-if="data?.cost?.cost_per_ton != null">
            <div class="dr-stat-rows">
              <div class="dr-stat-row">
                <span class="dr-stat-row__label">电费</span>
                <span class="dr-stat-row__value">{{ data.cost.electricity_cost }} <small>万元</small></span>
              </div>
              <div class="dr-stat-row">
                <span class="dr-stat-row__label">气费</span>
                <span class="dr-stat-row__value">{{ data.cost.gas_cost }} <small>万元</small></span>
              </div>
              <div class="dr-stat-row dr-stat-row--highlight">
                <span class="dr-stat-row__label">折算单耗</span>
                <span class="dr-stat-row__value tone-accent">{{ fmtNum(data.cost.cost_per_ton) }} <small>元/吨</small></span>
              </div>
              <div class="dr-stat-row__hint">按 {{ data.cost.basis_weight }} 吨折算</div>
            </div>
          </template>
          <div v-else class="dr-empty">暂无数据</div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import dayjs from 'dayjs'
import DateSwitcher from '../../../components/manage/DateSwitcher.vue'
import KpiBar from '../../../components/manage/KpiBar.vue'
import { fetchDailyProduction } from '../../../api/dashboard.js'

const targetDate = ref(dayjs().format('YYYY-MM-DD'))
const loading = ref(false)
const data = ref(null)

function stepDate(dir) {
  targetDate.value = dayjs(targetDate.value).add(dir, 'day').format('YYYY-MM-DD')
  load()
}
function onPick(val) {
  targetDate.value = val
  load()
}

async function load() {
  loading.value = true
  try {
    data.value = await fetchDailyProduction({ target_date: targetDate.value })
  } catch { data.value = null }
  finally { loading.value = false }
}

onMounted(load)

const workshops = computed(() => data.value?.workshop_output || [])
const wip = computed(() => data.value?.wip_distribution || [])
const wipTotal = computed(() => wip.value.reduce((s, w) => s + (w.total_weight || 0), 0))
const totalToday = computed(() => workshops.value.reduce((s, w) => s + (w.daily_output || 0), 0))
const totalYesterday = computed(() => workshops.value.reduce((s, w) => s + (w.yesterday_output || 0), 0))
const totalMonthly = computed(() => workshops.value.reduce((s, w) => s + (w.monthly_output || 0), 0))

const kpiItems = computed(() => {
  if (!data.value?.header_kpis) return []
  return data.value.header_kpis.map(k => ({
    key: k.key,
    label: k.label,
    value: k.value != null ? fmtNum(k.value) : '—',
    unit: k.unit,
    deltaText: k.delta_label || undefined,
    deltaTone: k.delta != null ? (k.delta >= 0 ? 'positive' : 'negative') : undefined,
  }))
})

function fmtNum(v) {
  if (v == null) return '—'
  const n = Number(v)
  if (Number.isNaN(n)) return v
  return n.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}
function fmtDelta(v) {
  if (v == null) return '—'
  const n = Number(v)
  if (Number.isNaN(n)) return '—'
  return (n >= 0 ? '+' : '') + n.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
}
function deltaClass(v) {
  if (v == null) return ''
  return Number(v) >= 0 ? 'tone-positive' : 'tone-negative'
}
</script>

<style scoped>
.dr-page {
  display: grid;
  gap: var(--xt-space-4);
  padding: var(--xt-space-4);
  max-width: 1400px;
  margin: 0 auto;
}

.dr-page :deep(.xt-kpi-bar) { grid-template-columns: repeat(7, 1fr); }
@media (max-width: 900px) { .dr-page :deep(.xt-kpi-bar) { grid-template-columns: repeat(3, 1fr); } }

.dr-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-4);
  flex-wrap: wrap;
}
.dr-header__title h1 {
  margin: 0;
  font-size: var(--xt-text-xl);
  font-weight: 850;
  color: var(--xt-text);
}
.dr-header__date {
  font-size: var(--xt-text-sm);
  color: var(--xt-text-muted);
}

/* grid layouts */
.dr-grid-3 { display: grid; grid-template-columns: 1fr 1.5fr 1fr; gap: var(--xt-space-4); }
.dr-grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: var(--xt-space-4); }
.dr-stack { display: grid; gap: var(--xt-space-4); }
@media (max-width: 900px) {
  .dr-grid-3, .dr-grid-2 { grid-template-columns: 1fr; }
}

/* panels */
.dr-panel {
  padding: var(--xt-space-4);
}
.dr-panel--wide { grid-column: 1 / -1; }
.dr-panel__title {
  margin: 0 0 var(--xt-space-3);
  font-size: var(--xt-text-sm);
  font-weight: 800;
  color: var(--xt-text);
  display: flex;
  align-items: center;
  gap: var(--xt-space-2);
}
.dr-panel__badge {
  font-size: 11px;
  font-weight: 700;
  padding: 1px 8px;
  border-radius: var(--xt-radius-pill);
  background: var(--xt-bg-panel-soft);
  color: var(--xt-text-secondary);
}

.dr-empty {
  color: var(--xt-text-muted);
  font-size: var(--xt-text-sm);
  padding: var(--xt-space-4) 0;
  text-align: center;
}

/* WIP cards */
.dr-wip-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: var(--xt-space-2);
}
.dr-wip-card {
  padding: var(--xt-space-2);
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-md);
  background: var(--xt-bg-panel-soft);
  text-align: center;
}
.dr-wip-card__name {
  font-size: 11px;
  font-weight: 700;
  color: var(--xt-text-secondary);
  margin-bottom: 2px;
}
.dr-wip-card__value {
  font-size: var(--xt-text-lg);
  font-weight: 850;
  color: var(--xt-text);
  font-variant-numeric: tabular-nums;
}
.dr-wip-card__value small { font-size: 11px; color: var(--xt-text-muted); font-weight: 700; }
.dr-wip-card__count { font-size: 11px; color: var(--xt-text-muted); }

/* stat rows */
.dr-stat-rows { display: grid; gap: var(--xt-space-2); }
.dr-stat-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  padding: 2px 0;
}
.dr-stat-row--highlight { border-top: 1px solid var(--xt-border-light); padding-top: var(--xt-space-2); margin-top: var(--xt-space-1); }
.dr-stat-row__label { font-size: var(--xt-text-sm); color: var(--xt-text-secondary); }
.dr-stat-row__value {
  font-size: var(--xt-text-base);
  font-weight: 800;
  color: var(--xt-text);
  font-variant-numeric: tabular-nums;
}
.dr-stat-row__value small { font-size: 11px; font-weight: 700; color: var(--xt-text-muted); margin-left: 2px; }
.dr-stat-row__delta { font-size: 11px; color: var(--xt-text-muted); text-align: right; }
.dr-stat-row__hint { font-size: 11px; color: var(--xt-text-muted); }
.tone-accent { color: var(--xt-accent, var(--xt-primary)); }

/* tables */
.dr-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--xt-text-sm);
  font-variant-numeric: tabular-nums;
}
.dr-table th {
  text-align: left;
  font-weight: 700;
  color: var(--xt-text-secondary);
  padding: var(--xt-space-2) var(--xt-space-2);
  border-bottom: 1px solid var(--xt-border);
  font-size: 11px;
  text-transform: uppercase;
}
.dr-table td {
  padding: var(--xt-space-2) var(--xt-space-2);
  border-bottom: 1px solid var(--xt-border-light);
  color: var(--xt-text);
}
.dr-table .num { text-align: right; }
.dr-table__total td { font-weight: 800; border-top: 2px solid var(--xt-border); }
.dr-table--compact { font-size: 12px; margin-top: var(--xt-space-3); }
.dr-table--compact th, .dr-table--compact td { padding: var(--xt-space-1) var(--xt-space-2); }

/* delta tones */
.tone-positive { color: var(--xt-success, #3ba55c); }
.tone-negative { color: var(--xt-danger, #d65241); }

/* yield */
.dr-yield-grid { display: grid; grid-template-columns: 1fr 1fr; gap: var(--xt-space-3); }
.dr-yield-card { text-align: center; }
.dr-yield-card__label { font-size: 11px; font-weight: 700; color: var(--xt-text-muted); }
.dr-yield-card__value { font-size: var(--xt-text-2xl); font-weight: 850; color: var(--xt-text); }
.dr-yield-card__delta { font-size: 12px; font-weight: 700; }
</style>
