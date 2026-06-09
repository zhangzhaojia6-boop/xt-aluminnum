<template>
  <section class="xt-shifts" data-testid="manage-yesterday-shifts">
    <header class="xt-shifts__head">
      <div class="xt-shifts__title-wrap">
        <span class="xt-shifts__eyebrow">昨日三班</span>
        <h2 class="xt-shifts__title">{{ dateLabel }} · 三班产量</h2>
      </div>
      <div class="xt-shifts__totals">
        <div class="xt-shifts__total">
          <span class="xt-shifts__total-label">{{ payload.output_basis_label || '包装产量' }}</span>
          <span class="xt-shifts__total-value">{{ fmt(payload.total_output, 2) }}</span>
          <span class="xt-shifts__total-unit">吨</span>
        </div>
        <div class="xt-shifts__total xt-shifts__total--secondary" v-if="showThroughputTotal">
          <span class="xt-shifts__total-label">{{ payload.shift_output_basis_label || '过站下机参考' }}</span>
          <span class="xt-shifts__total-value">{{ fmt(payload.total_throughput, 2) }}</span>
          <span class="xt-shifts__total-unit">吨</span>
        </div>
        <div class="xt-shifts__total xt-shifts__total--secondary" v-if="payload.energy_per_ton != null">
          <span class="xt-shifts__total-label">吨能耗</span>
          <span class="xt-shifts__total-value">{{ fmt(payload.energy_per_ton, 1) }}</span>
          <span class="xt-shifts__total-unit">kWh/吨</span>
        </div>
      </div>
    </header>

    <ul class="xt-shifts__grid">
      <li
        v-for="(s, idx) in shifts"
        :key="s.shift_code"
        class="xt-shifts__cell"
        :class="[`is-${s.shift_code.toLowerCase()}`, s.shift_count === 0 ? 'is-empty' : '', leaderIdx === idx ? 'is-leader' : '']"
      >
        <div class="xt-shifts__cell-head">
          <div class="xt-shifts__shift-tag">
            <span class="xt-shifts__shift-dot" />
            <span class="xt-shifts__shift-name">{{ s.shift_name }}</span>
            <span class="xt-shifts__shift-window">{{ s.shift_window || '' }}</span>
          </div>
          <span class="xt-shifts__crown" v-if="leaderIdx === idx" aria-hidden="true">▲</span>
        </div>

        <div class="xt-shifts__metric">
          <span class="xt-shifts__metric-value">{{ s.shift_count === 0 ? '—' : fmt(s.total_output, 2) }}</span>
          <span class="xt-shifts__metric-unit">吨</span>
        </div>
        <div class="xt-shifts__share" v-if="shiftShareTotal > 0 && s.total_output > 0">
          <span class="xt-shifts__share-bar">
            <span class="xt-shifts__share-fill" :style="{ width: sharePct(s) + '%' }" />
          </span>
          <span class="xt-shifts__share-text">{{ sharePct(s) }}%</span>
        </div>

        <ul class="xt-shifts__sub">
          <li class="xt-shifts__sub-item">
            <span class="xt-shifts__sub-label">已填/应填</span>
            <span class="xt-shifts__sub-value">
              <b>{{ s.reported_workshops }}</b>/{{ s.expected_workshops }}
              <small v-if="pendingWorkshops(s) > 0">待填 {{ pendingWorkshops(s) }}</small>
            </span>
          </li>
          <li class="xt-shifts__sub-item">
            <span class="xt-shifts__sub-label">吨能耗</span>
            <span class="xt-shifts__sub-value">
              <template v-if="s.energy_per_ton != null">
                <b>{{ fmt(s.energy_per_ton, 1) }}</b>
                <small>kWh/吨</small>
              </template>
              <template v-else>—</template>
            </span>
          </li>
          <li class="xt-shifts__sub-item">
            <span class="xt-shifts__sub-label">异常</span>
            <span class="xt-shifts__sub-value" :class="s.exception_count > 0 ? 'is-warn' : ''">
              <b>{{ s.exception_count }}</b>
              <small>条</small>
            </span>
          </li>
        </ul>
      </li>
    </ul>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import dayjs from 'dayjs'
import { formatShiftLabel } from '../../utils/display'

const props = defineProps({
  payload: { type: Object, default: () => ({ shifts: [], total_output: 0 }) }
})

const SHIFT_ORDER = ['A', 'B', 'C']
const SHIFT_FALLBACK = {
  A: { shift_code: 'A', shift_name: '长白班', shift_window: '07:30-15:30', shift_count: 0, total_output: 0, reported_workshops: 0, expected_workshops: 0, energy_per_ton: null, exception_count: 0 },
  B: { shift_code: 'B', shift_name: '小夜班', shift_window: '15:30-23:30', shift_count: 0, total_output: 0, reported_workshops: 0, expected_workshops: 0, energy_per_ton: null, exception_count: 0 },
  C: { shift_code: 'C', shift_name: '大夜班', shift_window: '23:30-07:30', shift_count: 0, total_output: 0, reported_workshops: 0, expected_workshops: 0, energy_per_ton: null, exception_count: 0 }
}

const shifts = computed(() => {
  const incoming = Array.isArray(props.payload?.shifts) ? props.payload.shifts : []
  const byCode = {}
  for (const it of incoming) byCode[it.shift_code] = it
  return SHIFT_ORDER.map((code) => {
    const row = { ...SHIFT_FALLBACK[code], ...(byCode[code] || {}) }
    return {
      ...row,
      shift_name: formatShiftLabel(row.shift_name || row.shift_code, SHIFT_FALLBACK[code].shift_name)
    }
  })
})

const leaderIdx = computed(() => {
  let best = -1
  let bestVal = 0
  shifts.value.forEach((s, i) => {
    const v = Number(s.total_output || 0)
    if (v > bestVal) { bestVal = v; best = i }
  })
  return best
})

const shiftShareTotal = computed(() => Number(props.payload?.total_throughput || props.payload?.total_output || 0))
const showThroughputTotal = computed(() => Number(props.payload?.total_throughput || 0) > 0)

const dateLabel = computed(() => {
  const d = props.payload?.business_date
  if (!d) return ''
  return dayjs(d).format('M月D日 (ddd)').replace('Mon','周一').replace('Tue','周二').replace('Wed','周三').replace('Thu','周四').replace('Fri','周五').replace('Sat','周六').replace('Sun','周日')
})

const fmt = (v, digits = 2) =>
  (v == null || Number.isNaN(Number(v)))
    ? '—'
    : Number(v).toLocaleString('zh-CN', {
      minimumFractionDigits: 0,
      maximumFractionDigits: digits,
    })

function sharePct(s) {
  const total = shiftShareTotal.value
  if (total <= 0) return 0
  return Math.round((Number(s.total_output || 0) / total) * 100)
}

function pendingWorkshops(s) {
  return Math.max(Number(s.expected_workshops || 0) - Number(s.reported_workshops || 0), 0)
}
</script>

<style scoped>
.xt-shifts {
  background: linear-gradient(160deg, #0d1320 0%, #131b2e 50%, #0e1422 100%);
  border: 1px solid rgba(140, 168, 220, 0.18);
  border-radius: var(--xt-radius-md);
  padding: var(--xt-space-4);
  display: flex; flex-direction: column; gap: var(--xt-space-3);
  color: #e6edf7;
  position: relative;
  overflow: hidden;
}
.xt-shifts::before {
  content: ''; position: absolute; inset: 0;
  background:
    radial-gradient(900px 220px at 0% -20%, rgba(102, 178, 255, 0.10), transparent 60%),
    radial-gradient(700px 200px at 110% 120%, rgba(255, 195, 100, 0.07), transparent 60%);
  pointer-events: none;
}

.xt-shifts__head {
  display: flex; align-items: flex-end; justify-content: space-between;
  gap: var(--xt-space-3); flex-wrap: wrap; position: relative;
}
.xt-shifts__title-wrap { display: flex; flex-direction: column; gap: 4px; }
.xt-shifts__eyebrow {
  font-size: 11px; font-weight: 800; letter-spacing: 0.16em;
  color: rgba(180, 200, 235, 0.55);
  text-transform: uppercase;
}
.xt-shifts__title {
  margin: 0; font-size: var(--xt-text-lg, 17px); font-weight: 800; letter-spacing: -0.01em;
  color: #f3f6fb;
}
.xt-shifts__totals { display: flex; gap: var(--xt-space-4); align-items: baseline; }
.xt-shifts__total { display: flex; align-items: baseline; gap: 6px; }
.xt-shifts__total--secondary { opacity: 0.78; }
.xt-shifts__total-label { font-size: 11px; color: rgba(180, 200, 235, 0.6); font-weight: 700; }
.xt-shifts__total-value {
  font-size: 24px; font-weight: 850; color: #f3f6fb;
  font-variant-numeric: tabular-nums; letter-spacing: -0.01em;
}
.xt-shifts__total-unit { font-size: 11px; color: rgba(180, 200, 235, 0.7); font-weight: 700; }

.xt-shifts__grid {
  list-style: none; margin: 0; padding: 0;
  display: grid; grid-template-columns: repeat(3, 1fr); gap: var(--xt-space-3);
  position: relative;
}
@media (max-width: 720px) { .xt-shifts__grid { grid-template-columns: 1fr; } }

.xt-shifts__cell {
  position: relative;
  background: rgba(255, 255, 255, 0.025);
  border: 1px solid rgba(140, 168, 220, 0.14);
  border-radius: 10px;
  padding: 14px 14px 12px;
  display: flex; flex-direction: column; gap: 8px;
  transition: border-color 200ms ease, background 200ms ease;
}
.xt-shifts__cell.is-leader {
  background: rgba(102, 178, 255, 0.08);
  border-color: rgba(102, 178, 255, 0.45);
  box-shadow: 0 0 0 1px rgba(102, 178, 255, 0.18) inset, 0 6px 22px -10px rgba(0, 80, 200, 0.45);
}
.xt-shifts__cell.is-empty { opacity: 0.55; }
.xt-shifts__cell.is-empty .xt-shifts__metric-value { color: rgba(230, 237, 247, 0.4); }

.xt-shifts__cell-head { display: flex; justify-content: space-between; align-items: center; }
.xt-shifts__shift-tag {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 12px; font-weight: 700; letter-spacing: 0.04em;
}
.xt-shifts__shift-dot {
  width: 8px; height: 8px; border-radius: 50%;
  display: inline-block;
}
.xt-shifts__cell.is-a .xt-shifts__shift-dot { background: #ffd166; box-shadow: 0 0 8px rgba(255, 209, 102, 0.45); }
.xt-shifts__cell.is-b .xt-shifts__shift-dot { background: #66b2ff; box-shadow: 0 0 8px rgba(102, 178, 255, 0.45); }
.xt-shifts__cell.is-c .xt-shifts__shift-dot { background: #74f5ff; box-shadow: 0 0 8px rgba(116, 245, 255, 0.45); }
.xt-shifts__shift-name { color: #f3f6fb; font-weight: 800; }
.xt-shifts__shift-window {
  color: rgba(180, 200, 235, 0.55); font-weight: 700; font-size: 11px;
  font-variant-numeric: tabular-nums;
}
.xt-shifts__crown { color: rgba(102, 178, 255, 0.85); font-size: 11px; }

.xt-shifts__metric { display: flex; align-items: baseline; gap: 6px; }
.xt-shifts__metric-value {
  font-size: 30px; font-weight: 850; color: #ffffff;
  font-variant-numeric: tabular-nums; letter-spacing: -0.02em; line-height: 1;
}
.xt-shifts__metric-unit { color: rgba(180, 200, 235, 0.7); font-size: 12px; font-weight: 700; }

.xt-shifts__share { display: flex; align-items: center; gap: 8px; }
.xt-shifts__share-bar {
  flex: 1; height: 4px; background: rgba(255, 255, 255, 0.07);
  border-radius: 2px; overflow: hidden; position: relative;
}
.xt-shifts__share-fill {
  display: block; height: 100%;
  background: linear-gradient(90deg, rgba(102, 178, 255, 0.85), rgba(102, 178, 255, 0.45));
  border-radius: 2px;
  transition: width 320ms cubic-bezier(.4,0,.2,1);
}
.xt-shifts__cell.is-a .xt-shifts__share-fill { background: linear-gradient(90deg, rgba(255, 209, 102, 0.85), rgba(255, 209, 102, 0.45)); }
.xt-shifts__cell.is-c .xt-shifts__share-fill { background: linear-gradient(90deg, rgba(116, 245, 255, 0.85), rgba(116, 245, 255, 0.45)); }
.xt-shifts__share-text {
  font-size: 11px; color: rgba(180, 200, 235, 0.7);
  font-weight: 700; font-variant-numeric: tabular-nums;
}

.xt-shifts__sub {
  list-style: none; margin: 0; padding: 8px 0 0;
  border-top: 1px dashed rgba(140, 168, 220, 0.16);
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px;
}
.xt-shifts__sub-item { display: flex; flex-direction: column; gap: 2px; }
.xt-shifts__sub-label { font-size: 10px; color: rgba(180, 200, 235, 0.55); font-weight: 700; letter-spacing: 0.04em; }
.xt-shifts__sub-value {
  font-size: 13px; color: #e6edf7;
  font-variant-numeric: tabular-nums; font-weight: 700;
  display: flex; align-items: baseline; gap: 3px;
}
.xt-shifts__sub-value b { color: #ffffff; font-weight: 850; font-size: 14px; }
.xt-shifts__sub-value small { color: rgba(180, 200, 235, 0.6); font-size: 10px; font-weight: 700; }
.xt-shifts__sub-value.is-warn b { color: #ffb84d; }
</style>
