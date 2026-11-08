<template>
  <div class="xt-metric" :class="`xt-metric--${size}`" data-testid="kpi-card">
    <div class="xt-metric__label">{{ label }}</div>
    <div v-if="isMissing" class="xt-metric__empty">暂无可信数据</div>
    <div v-else class="xt-metric__value">{{ value }}<span v-if="unit" class="xt-metric__unit">{{ unit }}</span></div>
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
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  label: { type: String, required: true },
  value: { type: [Number, String], default: null },
  unit: { type: String, default: '' },
  state: { type: String, default: '' },
  sub: { type: String, default: '' },
  size: { type: String, default: 'md' },
  sourceRoute: { type: String, default: '' }
})

const STATE_LABELS = { confirmed: '已确认', candidate: '待确认', conflict: '有冲突' }
const isMissing = computed(() => {
  const value = props.value
  return value === null || value === undefined || value === ''
})
const stateLabel = computed(() => (isMissing.value ? '' : STATE_LABELS[props.state] || ''))
</script>

<style scoped>
.xt-metric { display: grid; align-content: start; gap: 8px; min-width: 0; }
.xt-metric__label { color: var(--xt-text-secondary); font-size: 14px; }
.xt-metric__value { color: var(--xt-text); font-size: 28px; font-weight: 600; line-height: 1.1; font-variant-numeric: tabular-nums; }
.xt-metric--lg .xt-metric__value { font-size: 48px; letter-spacing: -0.02em; }
.xt-metric__unit { margin-left: 4px; color: var(--xt-text-muted); font-size: 14px; font-weight: 400; letter-spacing: 0; }
.xt-metric__empty { color: var(--xt-text-muted); font-size: 16px; line-height: 31px; }
.xt-metric--lg .xt-metric__empty { line-height: 53px; }
.xt-metric__foot { display: flex; flex-wrap: wrap; gap: 4px 12px; color: var(--xt-text-muted); font-size: 12px; }
.xt-metric__state { text-decoration: none; }
.is-confirmed { color: var(--xt-success); }
.is-candidate { color: var(--xt-primary); }
.is-conflict { color: var(--xt-warning); }
@media (max-width: 700px) {
  .xt-metric--lg .xt-metric__value { font-size: 40px; }
}
</style>
