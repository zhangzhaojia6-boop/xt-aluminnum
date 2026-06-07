<template>
  <section
    class="xt-production"
    data-testid="manage-production"
    :data-stitch-project-id="stitchSurface.stitch.projectId"
    :data-stitch-screen-id="stitchSurface.stitch.screenId"
  >
    <header class="xt-production__hero">
      <div class="xt-production__hero-copy">
        <span class="xt-production__eyebrow">生产驾驶舱</span>
        <h1>生产</h1>
      </div>
      <DateSwitcher
        :model-value="snapshot.targetDate.value"
        :loading="snapshot.loading.value"
        :freshness="snapshot.freshnessStatus.value"
        @step="snapshot.stepDate"
        @refresh="snapshot.load"
        @pick="(d) => snapshot.targetDate.value = d"
      />
    </header>

    <KpiBar :items="kpiItems" />

    <FactorySourceStrip :overview="stitchSurface.sourceOverview" />

    <div v-if="snapshot.lastError.value" class="xt-production__error">{{ snapshot.lastError.value }}</div>

    <div class="xt-production__grid">
      <section class="xt-production__ranking">
        <div class="xt-production__panel-head">
          <div>
            <span class="xt-production__eyebrow">车间排行</span>
            <h2>车间产量排名</h2>
          </div>
          <span class="xt-production__count">{{ rankedRows.length }} 个车间</span>
        </div>
        <p v-if="rankedRows.length === 0" class="xt-production__empty">无车间数据</p>
        <table v-else class="xt-production__table" data-testid="manage-production-table">
          <thead>
            <tr>
              <th scope="col">排名</th>
              <th scope="col">车间</th>
              <th scope="col" class="is-num">今日产量</th>
              <th scope="col" class="is-num">比昨日</th>
              <th scope="col" class="is-num">月均参照</th>
              <th scope="col">状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in rankedRows" :key="row.key">
              <td>
                <span class="xt-production__rank" :class="row.rankTone ? `tone-${row.rankTone}` : ''">{{ row.rank }}</span>
              </td>
              <td>
                <span class="xt-production__workshop">{{ row.name }}</span>
              </td>
              <td class="is-num">
                <span>{{ fmt(row.totalOutput, 2) }}</span>
                <small>吨</small>
              </td>
              <td class="is-num" :class="row.compareTone ? `tone-${row.compareTone}` : ''">
                <template v-if="row.compareValue == null">—</template>
                <template v-else>{{ row.compareArrow }}{{ fmt(Math.abs(row.compareValue), 2) }}</template>
              </td>
              <td class="is-num is-muted">
                <template v-if="row.targetValue == null">—</template>
                <template v-else>{{ fmt(row.targetValue, 2) }} <small>月均</small></template>
              </td>
              <td>
                <div class="xt-production__bar" aria-hidden="true">
                  <span :style="{ width: `${row.progress}%` }"></span>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </section>

      <aside class="xt-production__aside">
        <section class="xt-production__insight">
          <div class="xt-production__panel-head">
            <div>
              <span class="xt-production__eyebrow">主数据摘要</span>
              <h2>生产摘要</h2>
            </div>
          </div>
          <ul class="xt-production__brief-list">
            <li v-for="item in productionBrief" :key="item.key">
              <span></span>
              <div>
                <small>{{ item.label }}</small>
                <strong>{{ item.value }}</strong>
              </div>
            </li>
          </ul>
        </section>

        <section class="xt-production__signal">
          <span class="xt-production__signal-icon">⌁</span>
          <strong>生产信号</strong>
          <small>{{ leadingWorkshopText }}</small>
        </section>
      </aside>
    </div>

    <footer class="xt-production__status-bar" data-testid="stitch-bottom-status">
      <div
        v-for="item in bottomStatusItems"
        :key="item.key"
        class="xt-production__status-item"
        :class="item.tone ? `tone-${item.tone}` : ''"
      >
        <span aria-hidden="true"></span>
        <small>{{ item.label }}</small>
        <strong>{{ item.value }}</strong>
      </div>
    </footer>
  </section>
</template>

<script setup>
import { computed } from 'vue'

import DateSwitcher from '../../../components/manage/DateSwitcher.vue'
import KpiBar from '../../../components/manage/KpiBar.vue'
import FactorySourceStrip from '../../../components/manage/FactorySourceStrip.vue'
import { useDashboardSnapshot } from '../../../composables/useDashboardSnapshot.js'
import { buildProductionStitchSurface } from '../../../utils/stitchManageSurface.js'

const snapshot = useDashboardSnapshot()
snapshot.load()

const fmt = (v, digits = 2) =>
  (v == null || Number.isNaN(Number(v)))
    ? '—'
    : Number(v).toLocaleString('zh-CN', {
      minimumFractionDigits: 0,
      maximumFractionDigits: digits,
    })

const rawKpiItems = computed(() => {
  const lm = snapshot.leaderMetrics.value
  const trend = snapshot.trend.value
  const me = snapshot.managementEstimate.value

  const delta = trend.output_delta_vs_yesterday
  const deltaTone = delta == null ? null : (Number(delta) > 0 ? 'positive' : Number(delta) < 0 ? 'negative' : null)
  const deltaArrow = delta == null ? '' : (Number(delta) > 0 ? '↑' : Number(delta) < 0 ? '↓' : '')
  const deltaText = delta == null ? '—' : `${deltaArrow}${fmt(Math.abs(Number(delta)), 2)}`

  const marginReady = me.estimate_ready !== false && me.estimated_margin != null
  const marginValue = marginReady ? fmt(Number(me.estimated_margin) / 10000, 1) : '—'

  return [
    { key: 'output', label: '入库产量', value: fmt(lm.total_output_weight, 2), unit: '吨' },
    { key: 'delta', label: '比昨日', value: deltaText, unit: '吨', tone: deltaTone },
    {
      key: 'margin',
      label: '估算毛利',
      value: marginValue,
      unit: '万元',
      status: marginReady ? null : 'muted',
      hint: marginReady ? null : '估算未就绪'
    },
    { key: 'gap', label: '合同缺口', value: me.remaining_weight == null ? '—' : Number(me.remaining_weight).toFixed(0), unit: '吨' },
    { key: 'energy', label: '日吨能耗', value: fmt(lm.energy_per_ton, 1), unit: 'kWh/吨' }
  ]
})

const rawRankedRows = computed(() => {
  const rows = snapshot.productionLane.value || []
  return [...rows]
    .sort((a, b) => Number(b.total_output || 0) - Number(a.total_output || 0))
    .map((r, i) => {
      const compare = r.delta_vs_yesterday == null ? null : Number(r.delta_vs_yesterday)
      const compareTone = compare == null ? null : (compare > 0 ? 'positive' : compare < 0 ? 'negative' : null)
      const compareArrow = compare == null ? '' : (compare > 0 ? '↑' : compare < 0 ? '↓' : '')
      const totalOutput = Number(r.total_output || 0)
      const targetValue = r.target_value == null ? null : Number(r.target_value)
      const progress = targetValue && targetValue > 0
        ? Math.min(Math.max((totalOutput / targetValue) * 100, 8), 100)
        : Math.min(Math.max(totalOutput, 8), 100)
      return {
        key: r.workshop_id ?? r.workshop_name ?? i,
        rank: i + 1,
        rankTone: i === 0 ? 'hot' : i === 1 ? 'warm' : i === 2 ? 'live' : '',
        name: r.workshop_name || '—',
        totalOutput,
        compareValue: compare,
        compareTone,
        compareArrow,
        targetValue,
        progress
      }
    })
})

const rawLeadingRow = computed(() => rawRankedRows.value[0] || null)

const rawLeadingWorkshopText = computed(() => {
  const row = rawLeadingRow.value
  return row ? `${row.name} ${fmt(row.totalOutput, 2)} 吨` : '暂无车间数据'
})

const rawProductionBrief = computed(() => {
  const lm = snapshot.leaderMetrics.value
  const me = snapshot.managementEstimate.value
  return [
    { key: 'workshops', label: '参与车间', value: `${rawRankedRows.value.length} 个` },
    { key: 'leader', label: '当前最高', value: rawLeadingWorkshopText.value },
    { key: 'gap', label: '合同缺口', value: me.remaining_weight == null ? '—' : `${Number(me.remaining_weight).toFixed(0)} 吨` },
    { key: 'energy', label: '日吨能耗', value: lm.energy_per_ton == null ? '—' : `${fmt(lm.energy_per_ton, 1)} kWh/吨` }
  ]
})

const stitchSurface = computed(() => buildProductionStitchSurface({
  snapshotData: snapshot.data.value,
  targetDate: snapshot.targetDate.value,
  kpiItems: rawKpiItems.value,
  rankedRows: rawRankedRows.value,
  productionBrief: rawProductionBrief.value,
  leadingWorkshopText: rawLeadingWorkshopText.value,
  sourceOverview: snapshot.factoryCommandOverview.value,
  runtimeState: {
    snapshotLoading: snapshot.loading.value,
    snapshotError: snapshot.lastError.value,
  },
}))

const kpiItems = computed(() => stitchSurface.value.kpiStrip)
const rankedRows = computed(() => stitchSurface.value.workshopRanking)
const productionBrief = computed(() => stitchSurface.value.productionBrief)
const leadingWorkshopText = computed(() => stitchSurface.value.signal.text)
const bottomStatusItems = computed(() => stitchSurface.value.bottomStatus)
</script>

<style scoped>
.xt-production {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: var(--xt-space-4);
}

.xt-production::before {
  position: fixed;
  inset: 0;
  z-index: -1;
  background:
    linear-gradient(color-mix(in srgb, var(--xt-primary) 5%, transparent) 1px, transparent 1px),
    linear-gradient(90deg, color-mix(in srgb, var(--xt-primary) 5%, transparent) 1px, transparent 1px);
  background-size: 32px 32px;
  content: "";
  pointer-events: none;
}

.xt-production__hero,
.xt-production__ranking,
.xt-production__insight,
.xt-production__signal,
.xt-production__status-bar {
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

.xt-production__hero::before,
.xt-production__ranking::before,
.xt-production__insight::before,
.xt-production__signal::before {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(circle at 88% 10%, color-mix(in srgb, var(--xt-primary) 16%, transparent), transparent 34%),
    linear-gradient(135deg, color-mix(in srgb, var(--xt-primary) 8%, transparent), transparent 44%);
  content: "";
  pointer-events: none;
}

.xt-production__hero::after,
.xt-production__ranking::after,
.xt-production__insight::after {
  position: absolute;
  top: 0;
  right: var(--xt-space-4);
  left: var(--xt-space-4);
  height: 1px;
  background: linear-gradient(90deg, transparent, color-mix(in srgb, var(--xt-primary) 18%, transparent), transparent);
  content: "";
  pointer-events: none;
}

.xt-production__hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-3);
  min-height: 132px;
  padding: var(--xt-space-5);
}

.xt-production__hero-copy {
  position: relative;
  z-index: 1;
  display: grid;
  gap: var(--xt-space-1);
}

.xt-production__hero :deep(.xt-date-switcher) {
  position: relative;
  z-index: 1;
}

.xt-production__hero h1 {
  margin: 0;
  color: var(--xt-text-inverse);
  font-family: var(--xt-font-display);
  font-size: clamp(var(--xt-text-2xl), 3vw, 42px);
  font-weight: 900;
  letter-spacing: -0.04em;
}

.xt-production__eyebrow {
  color: color-mix(in srgb, var(--xt-primary) 72%, var(--xt-text-inverse));
  font-size: var(--xt-text-xs);
  font-weight: 900;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.xt-production__error {
  padding: var(--xt-space-2) var(--xt-space-3);
  border: 1px solid color-mix(in srgb, var(--xt-warning) 35%, var(--xt-border));
  border-radius: var(--xt-radius-md);
  background: color-mix(in srgb, var(--xt-warning-light) 10%, var(--xt-bg-panel));
  color: var(--xt-text-inverse);
  font-size: var(--xt-text-sm);
}

.xt-production__grid {
  display: grid;
  grid-template-columns: minmax(0, 2fr) minmax(300px, 0.86fr);
  gap: var(--xt-space-4);
}

.xt-production__ranking {
  display: flex;
  flex-direction: column;
  min-height: 520px;
  padding: var(--xt-space-4);
}

.xt-production__panel-head {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--xt-space-3);
  margin-bottom: var(--xt-space-3);
  padding-bottom: var(--xt-space-3);
  border-bottom: 1px solid color-mix(in srgb, var(--xt-primary) 13%, var(--xt-border));
}

.xt-production__panel-head h2 {
  margin: var(--xt-space-1) 0 0;
  color: var(--xt-text-inverse);
  font-size: var(--xt-text-xl);
  font-weight: 900;
}

.xt-production__count {
  border: 1px solid color-mix(in srgb, var(--xt-primary) 22%, var(--xt-border));
  border-radius: var(--xt-radius-pill);
  padding: var(--xt-space-1) var(--xt-space-2);
  background: color-mix(in srgb, var(--xt-primary-light) 8%, transparent);
  color: color-mix(in srgb, var(--xt-text-inverse) 74%, transparent);
  font-size: var(--xt-text-xs);
  font-weight: 850;
}

.xt-production__empty {
  position: relative;
  z-index: 1;
  display: grid;
  min-height: 260px;
  margin: 0;
  place-items: center;
  border: 1px dashed color-mix(in srgb, var(--xt-primary) 18%, var(--xt-border));
  border-radius: var(--xt-radius-lg);
  color: color-mix(in srgb, var(--xt-text-inverse) 46%, transparent);
  font-size: var(--xt-text-sm);
}

.xt-production__table {
  position: relative;
  z-index: 1;
  width: 100%;
  border-collapse: collapse;
  font-size: var(--xt-text-sm);
}

.xt-production__table th,
.xt-production__table td {
  padding: var(--xt-space-3);
  border-bottom: 1px solid color-mix(in srgb, var(--xt-primary) 8%, var(--xt-border));
  text-align: left;
  color: color-mix(in srgb, var(--xt-text-inverse) 80%, transparent);
}

.xt-production__table tbody tr {
  transition:
    background-color var(--xt-motion-fast) var(--xt-ease),
    transform var(--xt-motion-fast) var(--xt-ease);
}

@media (hover: hover) {
  .xt-production__table tbody tr:hover {
    background: color-mix(in srgb, var(--xt-primary) 6%, transparent);
    transform: translateX(2px);
  }
}

.xt-production__table th {
  color: color-mix(in srgb, var(--xt-text-inverse) 48%, transparent);
  font-size: var(--xt-text-xs);
  font-weight: 900;
  letter-spacing: 0.06em;
}

.xt-production__table .is-num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.xt-production__table small {
  margin-left: 2px;
  color: color-mix(in srgb, var(--xt-text-inverse) 46%, transparent);
  font-size: var(--xt-text-xs);
}

.xt-production__table .is-muted {
  color: color-mix(in srgb, var(--xt-text-inverse) 52%, transparent);
}

.xt-production__table .tone-positive {
  color: var(--xt-success);
}

.xt-production__table .tone-negative {
  color: var(--xt-warning);
}

.xt-production__rank {
  display: inline-grid;
  width: 28px;
  height: 28px;
  place-items: center;
  border: 1px solid color-mix(in srgb, var(--xt-primary) 20%, var(--xt-border));
  border-radius: var(--xt-radius-pill);
  background: color-mix(in srgb, var(--xt-primary-light) 8%, transparent);
  color: var(--xt-text-inverse);
  font-family: var(--xt-font-number);
  font-weight: 900;
}

.xt-production__rank.tone-hot {
  border-color: color-mix(in srgb, var(--xt-warning) 44%, var(--xt-border));
  color: var(--xt-warning);
}

.xt-production__rank.tone-warm {
  color: color-mix(in srgb, var(--xt-warning) 72%, var(--xt-text-inverse));
}

.xt-production__rank.tone-live {
  color: var(--xt-primary);
}

.xt-production__workshop {
  color: var(--xt-text-inverse);
  font-weight: 850;
}

.xt-production__bar {
  width: min(120px, 14vw);
  height: 7px;
  overflow: hidden;
  border-radius: var(--xt-radius-pill);
  background: color-mix(in srgb, var(--xt-bg-ink) 62%, var(--xt-bg-panel));
}

.xt-production__bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, var(--xt-primary), color-mix(in srgb, var(--xt-primary) 46%, var(--xt-text-inverse)));
  box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--xt-text-inverse) 18%, transparent);
}

.xt-production__aside {
  display: grid;
  gap: var(--xt-space-4);
}

.xt-production__insight,
.xt-production__signal {
  padding: var(--xt-space-4);
}

.xt-production__insight {
  min-height: 358px;
}

.xt-production__brief-list {
  position: relative;
  z-index: 1;
  display: grid;
  gap: var(--xt-space-3);
  margin: 0;
  padding: 0;
  list-style: none;
}

.xt-production__brief-list li {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: var(--xt-space-2);
  align-items: center;
  padding: var(--xt-space-3);
  border: 1px solid color-mix(in srgb, var(--xt-primary) 10%, var(--xt-border));
  border-radius: var(--xt-radius-lg);
  background: color-mix(in srgb, var(--xt-bg-ink) 28%, transparent);
}

.xt-production__brief-list li > span {
  width: 8px;
  height: 8px;
  border-radius: var(--xt-radius-pill);
  background: var(--xt-primary);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--xt-primary) 18%, transparent);
}

.xt-production__brief-list small {
  display: block;
  color: color-mix(in srgb, var(--xt-text-inverse) 46%, transparent);
  font-size: var(--xt-text-xs);
  font-weight: 850;
}

.xt-production__brief-list strong {
  display: block;
  margin-top: 2px;
  color: var(--xt-text-inverse);
  font-size: var(--xt-text-md);
  font-weight: 900;
}

.xt-production__signal {
  display: grid;
  min-height: 148px;
  place-items: center;
  text-align: center;
}

.xt-production__status-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-3);
  padding: var(--xt-space-3) var(--xt-space-4);
}

.xt-production__status-item {
  position: relative;
  z-index: 1;
  display: inline-flex;
  align-items: center;
  gap: var(--xt-space-2);
  min-width: 0;
  color: color-mix(in srgb, var(--xt-text-inverse) 72%, transparent);
  font-size: var(--xt-text-sm);
}

.xt-production__status-item > span {
  width: 8px;
  height: 8px;
  flex: 0 0 auto;
  border-radius: var(--xt-radius-pill);
  background: var(--xt-primary);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--xt-primary) 18%, transparent);
}

.xt-production__status-item small {
  color: color-mix(in srgb, var(--xt-text-inverse) 46%, transparent);
  font-size: var(--xt-text-xs);
  font-weight: 850;
  white-space: nowrap;
}

.xt-production__status-item strong {
  color: var(--xt-text-inverse);
  font-weight: 900;
  white-space: nowrap;
}

.xt-production__status-item.tone-success > span {
  background: var(--xt-success);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--xt-success) 18%, transparent);
}

.xt-production__status-item.tone-warning > span,
.xt-production__status-item.tone-danger > span {
  background: var(--xt-warning);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--xt-warning) 18%, transparent);
}

.xt-production__signal-icon {
  color: var(--xt-primary);
  font-size: 48px;
  line-height: 1;
}

.xt-production__signal strong {
  color: var(--xt-text-inverse);
  font-size: var(--xt-text-md);
  font-weight: 900;
}

.xt-production__signal small {
  color: color-mix(in srgb, var(--xt-text-inverse) 52%, transparent);
  font-size: var(--xt-text-xs);
  font-weight: 850;
}

@media (max-width: 1080px) {
  .xt-production__grid {
    grid-template-columns: 1fr;
  }

  .xt-production__ranking {
    min-height: auto;
  }
}

@media (max-width: 720px) {
  .xt-production__hero {
    flex-direction: column;
    align-items: stretch;
    padding: var(--xt-space-4);
  }

  .xt-production__ranking,
  .xt-production__insight,
  .xt-production__signal,
  .xt-production__status-bar {
    padding: var(--xt-space-3);
  }

  .xt-production__status-bar {
    align-items: flex-start;
    flex-direction: column;
  }

  .xt-production__table {
    min-width: 0;
    table-layout: fixed;
  }

  .xt-production__table th,
  .xt-production__table td {
    padding: var(--xt-space-2);
    font-size: var(--xt-text-xs);
  }

  .xt-production__table th:nth-child(1),
  .xt-production__table td:nth-child(1) {
    width: 44px;
  }

  .xt-production__table th:nth-child(3),
  .xt-production__table td:nth-child(3) {
    width: 82px;
  }

  .xt-production__table th:nth-child(4),
  .xt-production__table td:nth-child(4) {
    width: 62px;
  }

  .xt-production__table th:nth-child(5),
  .xt-production__table td:nth-child(5),
  .xt-production__table th:nth-child(6),
  .xt-production__table td:nth-child(6) {
    display: none;
  }

  .xt-production__ranking {
    overflow-x: auto;
  }
}

@media (prefers-reduced-motion: reduce) {
  .xt-production__table tbody tr {
    transition: none;
  }
}
</style>
