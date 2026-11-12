<template>
  <div class="xt-metric" :class="`xt-metric--${size}`" data-testid="kpi-card">
    <div class="xt-metric__label">{{ label }}</div>
    <div v-if="isMissing && loading" class="xt-metric__skeleton" aria-hidden="true" data-testid="kpi-loading" />
    <div v-else-if="isMissing" class="xt-metric__empty">暂无可信数据</div>
    <div v-else class="xt-metric__value">{{ displayValue }}<span v-if="unit" class="xt-metric__unit">{{ unit }}</span></div>
    <div v-if="stateLabel || sub" class="xt-metric__foot">
      <component
        :is="sourceRoute ? 'router-link' : 'span'"
        v-if="stateLabel"
        :to="sourceRoute || undefined"
        class="xt-metric__state"
        :class="`is-${state}`"
      >{{ stateLabel }}</component>
      <span v-if="sub" class="xt-metric__sub">{{ sub }}</span>
    </div>
    <slot />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'

const props = defineProps({
  label: { type: String, required: true },
  value: { type: [Number, String], default: null },
  unit: { type: String, default: '' },
  state: { type: String, default: '' },
  sub: { type: String, default: '' },
  size: { type: String, default: 'md' },
  sourceRoute: { type: String, default: '' },
  loading: { type: Boolean, default: false }
})

const STATE_LABELS = { confirmed: '已确认', candidate: '待确认', conflict: '有冲突' }
const isMissing = computed(() => {
  const value = props.value
  return value === null || value === undefined || value === ''
})
const stateLabel = computed(() => (isMissing.value ? '' : STATE_LABELS[props.state] || ''))

const NUMERIC = /^-?[\d,]+(\.\d+)?$/
const displayValue = ref(props.value)
let frame = 0

function countUp(next) {
  cancelAnimationFrame(frame)
  const text = String(next ?? '')
  const reduced = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  if (!NUMERIC.test(text) || reduced) {
    displayValue.value = next
    return
  }
  const target = Number(text.replaceAll(',', ''))
  const digits = text.split('.')[1]?.length || 0
  const start = performance.now()
  const tick = (now) => {
    const progress = Math.min((now - start) / 900, 1)
    const eased = 1 - (1 - progress) ** 4
    displayValue.value = progress === 1
      ? next
      : (target * eased).toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })
    if (progress < 1) frame = requestAnimationFrame(tick)
  }
  frame = requestAnimationFrame(tick)
}

watch(() => props.value, countUp, { immediate: true })
onBeforeUnmount(() => cancelAnimationFrame(frame))
</script>

<style scoped>
.xt-metric { display: grid; align-content: start; gap: 8px; min-width: 0; }
.xt-metric__label { color: var(--xt-text-secondary); font-size: 14px; }
.xt-metric__value { color: var(--xt-text); font-size: 28px; font-weight: 600; line-height: 1.1; font-variant-numeric: tabular-nums; }
.xt-metric--lg .xt-metric__value { font-size: 44px; letter-spacing: -0.02em; }
.xt-metric--xl .xt-metric__value { font-size: 72px; letter-spacing: -0.03em; }
.xt-metric__unit { margin-left: 4px; color: var(--xt-text-muted); font-size: 14px; font-weight: 400; letter-spacing: 0; }
.xt-metric__empty { color: var(--xt-text-muted); font-size: 16px; line-height: 31px; }
.xt-metric__skeleton { width: min(160px, 70%); height: 31px; border-radius: 4px; background: var(--xt-bg-panel-strong); animation: xt-metric-pulse 1.4s ease-in-out infinite; }
.xt-metric--lg .xt-metric__skeleton { height: 48px; }
.xt-metric--xl .xt-metric__skeleton { width: min(260px, 80%); height: 79px; }
@keyframes xt-metric-pulse { 50% { opacity: 0.5; } }
@media (prefers-reduced-motion: reduce) { .xt-metric__skeleton { animation: none; } }
.xt-metric--lg .xt-metric__empty { line-height: 48px; }
.xt-metric__foot { display: flex; flex-wrap: wrap; gap: 4px 12px; color: var(--xt-text-muted); font-size: 12px; }
.xt-metric__state { text-decoration: none; }
.is-confirmed { color: var(--xt-success); }
.is-candidate { color: var(--xt-primary); }
.is-conflict { color: var(--xt-warning); }
@media (max-width: 700px) {
  .xt-metric--lg .xt-metric__value { font-size: 36px; }
  .xt-metric--xl .xt-metric__value { font-size: 56px; }
}
</style>
