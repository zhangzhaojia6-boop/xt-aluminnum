<template>
  <section class="exec-root">
    <header class="exec-head">
      <div class="exec-brand">
        <h1>鑫泰铝业 数据中枢</h1>
        <span class="exec-sub">经营驾驶舱 · {{ businessDateDisplay }}</span>
      </div>
      <div class="exec-actions">
        <input type="date" v-model="businessDate" class="exec-date" @change="reload" />
        <button class="exec-btn" @click="onRecompute" :disabled="loading">重算今日</button>
      </div>
    </header>

    <div v-if="data?.is_estimated" class="exec-banner">
      ⚠ 阶段 1 估算模式（±20% 精度）· 待核算员接入后升级至 ±3%
    </div>

    <div class="exec-kpi">
      <article class="kpi-card kpi-primary">
        <span class="kpi-label">昨日加工利润</span>
        <strong class="kpi-value">¥{{ fmtMoney(data?.total_profit) }}</strong>
        <span class="kpi-delta" :class="{ up: deltaPositive, down: deltaNegative }">
          {{ formatDelta(data?.vs_yesterday_profit_delta, data?.vs_yesterday_profit_delta_pct) }}
        </span>
      </article>
      <article class="kpi-card">
        <span class="kpi-label">昨日加工收入</span>
        <strong class="kpi-value">¥{{ fmtMoney(data?.total_revenue) }}</strong>
        <span class="kpi-sub">毛利率 {{ fmtPct(data?.profit_margin_pct) }}</span>
      </article>
      <article class="kpi-card">
        <span class="kpi-label">昨日加工成本</span>
        <strong class="kpi-value">¥{{ fmtMoney(data?.total_cost) }}</strong>
        <span class="kpi-sub">产量 {{ fmtNum(data?.total_output_tons, 1) }} 吨</span>
      </article>
      <article class="kpi-card kpi-month">
        <span class="kpi-label">本月累计毛利</span>
        <strong class="kpi-value">¥{{ fmtMoney(data?.mtd_profit) }}</strong>
        <span class="kpi-sub">收入 ¥{{ fmtMoney(data?.mtd_revenue) }} · 成本 ¥{{ fmtMoney(data?.mtd_cost) }}</span>
      </article>
    </div>

    <div class="exec-grid">
      <article class="panel">
        <header class="panel-head">
          <h2>车间盈亏榜</h2>
          <span class="panel-hint">按加工毛利降序 · 负数标红</span>
        </header>
        <div v-if="!ranking.length" class="panel-empty">当日无数据</div>
        <ul v-else class="rank-list">
          <li
            v-for="r in ranking"
            :key="r.workshop_id + '-' + (r.alloy_grade || '')"
            class="rank-row"
            :class="{ loss: (r.gross_profit ?? 0) < 0, missing: r.has_missing_fee_rule }"
          >
            <div class="rank-name">
              <strong>{{ r.workshop_name }}</strong>
              <span class="rank-sub">
                {{ r.alloy_grade || '?' }} · {{ r.process_type || '?' }} · {{ fmtNum(r.output_tons, 1) }}t
              </span>
            </div>
            <div class="rank-bar">
              <div
                class="rank-bar-fill"
                :class="{ negative: (r.gross_profit ?? 0) < 0 }"
                :style="{ width: barWidth(r.gross_profit) }"
              ></div>
            </div>
            <div class="rank-profit">
              <strong v-if="r.gross_profit !== null && r.gross_profit !== undefined">
                {{ (r.gross_profit ?? 0) >= 0 ? '+' : '' }}¥{{ fmtMoney(r.gross_profit) }}
              </strong>
              <strong v-else class="missing-tag">加工费缺</strong>
              <span class="rank-rev">收入 ¥{{ fmtMoney(r.revenue) }} · 成本 ¥{{ fmtMoney(r.cost) }}</span>
            </div>
          </li>
        </ul>
      </article>

      <article class="panel">
        <header class="panel-head">
          <h2>铝价与现金流</h2>
          <span class="panel-hint">长江 A00 · 代采代付不进利润</span>
        </header>
        <div class="price-hero">
          <strong v-if="data?.aluminum_price?.price_per_ton">
            ¥{{ fmtMoney(data.aluminum_price.price_per_ton) }}/吨
          </strong>
          <strong v-else class="missing-tag">暂无报价</strong>
          <span
            v-if="data?.aluminum_price?.delta_vs_prev !== null"
            class="price-delta"
            :class="{ up: (data?.aluminum_price?.delta_vs_prev ?? 0) > 0, down: (data?.aluminum_price?.delta_vs_prev ?? 0) < 0 }"
          >
            {{ (data?.aluminum_price?.delta_vs_prev ?? 0) >= 0 ? '+' : '' }}{{ fmtNum(data?.aluminum_price?.delta_vs_prev, 0) }}
          </span>
        </div>
        <p class="price-note">
          昨日产量 {{ fmtNum(data?.total_output_tons, 1) }}t × 铝价 ≈
          ¥{{ fmtMoney((data?.total_output_tons || 0) * (data?.aluminum_price?.price_per_ton || 0)) }}
          <br />该笔代收代付不影响经营利润
        </p>
        <div v-if="priceTrend.length" class="price-trend">
          <div
            v-for="p in priceTrend"
            :key="p.price_date"
            class="price-bar"
            :title="`${p.price_date}: ¥${p.price_per_ton}`"
            :style="{ height: trendHeight(p.price_per_ton) }"
          ></div>
        </div>
      </article>
    </div>

    <div v-if="data?.has_missing_fee_rule" class="exec-warning">
      ⚠ 本日有车间缺少加工费规则，未计入合计。请到 <router-link to="/manage/executive/processing-fees">加工费管理</router-link> 补齐。
    </div>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import {
  fetchExecutiveDashboard,
  fetchMachineRanking,
  fetchAluminumPriceTrend,
  recomputeExecutive,
} from '../../api/executive'

const today = new Date()
const y = (d) => new Date(d.getTime() - 24 * 3600 * 1000)
const iso = (d) => d.toISOString().slice(0, 10)
const businessDate = ref(iso(y(today)))
const data = ref(null)
const ranking = ref([])
const priceTrend = ref([])
const loading = ref(false)

const businessDateDisplay = computed(() => businessDate.value)

const deltaPositive = computed(() => (data.value?.vs_yesterday_profit_delta ?? 0) > 0)
const deltaNegative = computed(() => (data.value?.vs_yesterday_profit_delta ?? 0) < 0)

const maxProfitAbs = computed(() => {
  const arr = ranking.value.map((r) => Math.abs(r.gross_profit ?? 0))
  return arr.length ? Math.max(...arr) : 1
})

function barWidth(profit) {
  if (profit === null || profit === undefined) return '4%'
  const pct = (Math.abs(profit) / (maxProfitAbs.value || 1)) * 100
  return `${Math.max(4, Math.min(100, pct))}%`
}

const trendMax = computed(() => priceTrend.value.length ? Math.max(...priceTrend.value.map((p) => p.price_per_ton)) : 1)
const trendMin = computed(() => priceTrend.value.length ? Math.min(...priceTrend.value.map((p) => p.price_per_ton)) : 0)

function trendHeight(price) {
  const span = Math.max(1, trendMax.value - trendMin.value)
  const h = 12 + ((price - trendMin.value) / span) * 44
  return `${h}px`
}

function fmtMoney(v) {
  if (v === null || v === undefined) return '—'
  const n = Number(v)
  if (Math.abs(n) >= 10000) return (n / 10000).toFixed(1) + ' 万'
  return n.toLocaleString('zh-CN', { maximumFractionDigits: 0 })
}

function fmtNum(v, digits = 0) {
  if (v === null || v === undefined) return '—'
  return Number(v).toLocaleString('zh-CN', { maximumFractionDigits: digits, minimumFractionDigits: digits })
}

function fmtPct(v) {
  if (v === null || v === undefined) return '—'
  return Number(v).toFixed(1) + '%'
}

function formatDelta(val, pct) {
  if (val === null || val === undefined) return '无对比数据'
  const sign = val >= 0 ? '+' : ''
  const pctStr = pct !== null && pct !== undefined ? ` (${sign}${Number(pct).toFixed(1)}%)` : ''
  return `${sign}¥${fmtMoney(val)} vs 前日${pctStr}`
}

async function reload() {
  loading.value = true
  try {
    const [dash, rank, trend] = await Promise.all([
      fetchExecutiveDashboard(businessDate.value),
      fetchMachineRanking(businessDate.value),
      fetchAluminumPriceTrend(30),
    ])
    data.value = dash
    ranking.value = rank
    priceTrend.value = trend
  } finally {
    loading.value = false
  }
}

async function onRecompute() {
  loading.value = true
  try {
    await recomputeExecutive(businessDate.value)
    await reload()
  } finally {
    loading.value = false
  }
}

onMounted(reload)
</script>

<style scoped>
.exec-root {
  min-height: 100vh;
  padding: 20px clamp(16px, 3vw, 40px);
  background:
    radial-gradient(ellipse at 10% 0%, oklch(22% 0.03 255 / 0.5) 0%, transparent 50%),
    radial-gradient(ellipse at 90% 100%, oklch(20% 0.05 158 / 0.3) 0%, transparent 50%),
    oklch(12% 0.015 252);
  color: oklch(92% 0.01 252);
  font-variant-numeric: tabular-nums;
}
.exec-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  margin-bottom: 18px;
  padding-bottom: 16px;
  border-bottom: 1px solid oklch(28% 0.03 252);
}
.exec-brand h1 {
  margin: 0;
  color: oklch(92% 0.01 252);
  font-size: 22px;
  font-weight: 900;
  letter-spacing: 1px;
}
.exec-sub {
  color: oklch(58% 0.02 252);
  font-size: 13px;
  font-weight: 800;
}
.exec-actions { display: flex; gap: 10px; align-items: center; }
.exec-date {
  height: 36px;
  padding: 0 10px;
  border: 1px solid oklch(30% 0.03 252);
  border-radius: 6px;
  background: oklch(16% 0.018 252);
  color: oklch(92% 0.01 252);
  font-variant-numeric: tabular-nums;
}
.exec-btn {
  min-height: 36px;
  padding: 0 14px;
  border: 0;
  border-radius: 6px;
  background: oklch(52% 0.18 255);
  color: #fff;
  font-weight: 850;
  cursor: pointer;
  box-shadow: 0 0 12px oklch(52% 0.18 255 / 0.25);
}
.exec-btn:disabled { opacity: 0.5; cursor: not-allowed; }

.exec-banner {
  margin-bottom: 16px;
  padding: 10px 14px;
  border: 1px solid oklch(50% 0.14 75);
  background: oklch(22% 0.06 75);
  color: oklch(80% 0.11 75);
  border-radius: 8px;
  font-size: 13px;
  font-weight: 800;
}

.exec-kpi {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 14px;
  margin-bottom: 18px;
}
.kpi-card {
  display: grid;
  gap: 8px;
  padding: 18px;
  border: 1px solid oklch(28% 0.03 252);
  border-radius: 10px;
  background:
    linear-gradient(180deg, rgba(80, 160, 255, 0.03) 0%, transparent 60%),
    oklch(18% 0.022 252);
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.35), inset 0 1px 0 rgba(255, 255, 255, 0.05);
}
.kpi-primary {
  border-color: oklch(50% 0.14 158);
  background:
    linear-gradient(180deg, oklch(62% 0.14 158 / 0.08) 0%, transparent 50%),
    oklch(18% 0.025 158);
}
.kpi-month {
  border-color: oklch(45% 0.14 255);
}
.kpi-label {
  color: oklch(58% 0.02 252);
  font-size: 12px;
  font-weight: 850;
  letter-spacing: 1px;
}
.kpi-value {
  font-size: 30px;
  font-weight: 900;
  letter-spacing: 0.5px;
}
.kpi-primary .kpi-value { color: oklch(78% 0.14 158); }
.kpi-delta {
  font-size: 13px;
  font-weight: 800;
}
.kpi-delta.up { color: oklch(72% 0.14 158); }
.kpi-delta.down { color: oklch(72% 0.16 28); }
.kpi-sub {
  color: oklch(58% 0.02 252);
  font-size: 12px;
  font-weight: 800;
}

.exec-grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(0, 1fr);
  gap: 14px;
}
.panel {
  padding: 16px 18px;
  border: 1px solid oklch(28% 0.03 252);
  border-radius: 10px;
  background:
    linear-gradient(180deg, rgba(80, 160, 255, 0.02) 0%, transparent 50%),
    oklch(18% 0.022 252);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
}
.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid oklch(25% 0.03 252);
}
.panel-head h2 { margin: 0; font-size: 15px; font-weight: 900; letter-spacing: 0.5px; }
.panel-hint { color: oklch(58% 0.02 252); font-size: 12px; font-weight: 800; }
.panel-empty { padding: 24px; text-align: center; color: oklch(58% 0.02 252); }

.rank-list { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
.rank-row {
  display: grid;
  grid-template-columns: minmax(0, 1.3fr) minmax(0, 2fr) minmax(0, 1.2fr);
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid oklch(25% 0.03 252);
  border-radius: 8px;
  background: oklch(16% 0.018 252);
  align-items: center;
}
.rank-row.loss { border-color: oklch(50% 0.14 28 / 0.5); background: oklch(20% 0.05 28 / 0.25); }
.rank-row.missing { opacity: 0.6; }
.rank-name strong { display: block; font-size: 14px; font-weight: 900; }
.rank-sub { color: oklch(58% 0.02 252); font-size: 11px; font-weight: 800; }
.rank-bar {
  height: 12px;
  border-radius: 999px;
  background: oklch(22% 0.025 252);
  overflow: hidden;
  box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.3);
}
.rank-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, oklch(62% 0.18 255), oklch(72% 0.14 158));
  box-shadow: 0 0 8px oklch(62% 0.18 255 / 0.3);
  transition: width 420ms cubic-bezier(0.16, 1, 0.3, 1);
}
.rank-bar-fill.negative {
  background: linear-gradient(90deg, oklch(60% 0.18 28), oklch(72% 0.16 28));
  box-shadow: 0 0 8px oklch(60% 0.18 28 / 0.3);
}
.rank-profit { text-align: right; }
.rank-profit strong { display: block; font-size: 15px; font-weight: 900; }
.rank-row.loss .rank-profit strong { color: oklch(78% 0.16 28); }
.rank-rev { color: oklch(70% 0.02 252); font-size: 11px; font-weight: 800; }
.missing-tag { color: oklch(72% 0.14 75); font-weight: 800; }

.price-hero {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 12px 0;
}
.price-hero strong { font-size: 28px; font-weight: 900; }
.price-delta { font-size: 13px; font-weight: 850; }
.price-delta.up { color: oklch(72% 0.14 158); }
.price-delta.down { color: oklch(72% 0.16 28); }
.price-note {
  margin: 10px 0;
  padding: 10px;
  border: 1px solid oklch(25% 0.03 252);
  border-radius: 6px;
  background: oklch(16% 0.018 252);
  color: oklch(58% 0.02 252);
  font-size: 12px;
  font-weight: 700;
  line-height: 1.6;
}
.price-trend {
  display: flex;
  align-items: flex-end;
  gap: 3px;
  height: 70px;
  padding: 4px;
  border: 1px solid oklch(25% 0.03 252);
  border-radius: 6px;
  background: oklch(14% 0.015 252);
}
.price-bar {
  flex: 1;
  min-width: 4px;
  background: linear-gradient(180deg, oklch(62% 0.18 255), oklch(45% 0.14 255));
  border-radius: 2px 2px 0 0;
}

.exec-warning {
  margin-top: 14px;
  padding: 10px 14px;
  border: 1px solid oklch(50% 0.14 28);
  background: oklch(22% 0.06 28);
  color: oklch(80% 0.12 28);
  border-radius: 8px;
  font-size: 13px;
  font-weight: 800;
}
.exec-warning a { color: oklch(80% 0.14 255); }

@media (max-width: 1100px) {
  .exec-kpi { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .exec-grid { grid-template-columns: 1fr; }
}
@media (max-width: 640px) {
  .exec-kpi { grid-template-columns: 1fr; }
  .rank-row { grid-template-columns: 1fr; }
  .rank-bar { order: 3; }
}
</style>
