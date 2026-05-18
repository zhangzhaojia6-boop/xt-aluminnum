<template>
  <article class="xt-metric-card" :class="[`xt-metric-card--${tone}`]">
    <div class="xt-metric-card__icon" v-if="$slots.icon">
      <slot name="icon" />
    </div>
    <div class="xt-metric-card__content">
      <div class="xt-metric-card__label">{{ label }}</div>
      <div class="xt-metric-card__value xt-countup">
        {{ formattedValue }}<span v-if="unit" class="xt-metric-card__unit">{{ unit }}</span>
      </div>
      <div v-if="hasChange" class="xt-metric-card__change" :class="changeClass">
        {{ changePrefix }}{{ formattedChange }}%
      </div>
    </div>
    <div v-if="$slots.spark" class="xt-metric-card__spark">
      <slot name="spark" />
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'

defineOptions({ name: 'XtMetricCard' })

const props = defineProps({
  label: {
    type: String,
    required: true
  },
  value: {
    type: Number,
    default: null
  },
  unit: {
    type: String,
    default: ''
  },
  change: {
    type: Number,
    default: null
  },
  precision: {
    type: Number,
    default: 1
  },
  tone: {
    type: String,
    default: 'neutral',
    validator: v => ['neutral', 'primary', 'success', 'warning', 'danger'].includes(v)
  }
})

const formattedValue = computed(() => {
  if (!Number.isFinite(props.value)) return '—'
  if (props.value >= 10000) return (props.value / 10000).toFixed(props.precision) + '万'
  return props.value.toLocaleString('zh-CN', { maximumFractionDigits: props.precision })
})

const hasChange = computed(() => Number.isFinite(props.change))
const formattedChange = computed(() => Math.abs(props.change * 100).toFixed(1))
const changePrefix = computed(() => props.change > 0 ? '+' : props.change < 0 ? '-' : '')
const changeClass = computed(() => ({
  'xt-metric-card__change--up': props.change > 0,
  'xt-metric-card__change--down': props.change < 0
}))
</script>

<style scoped>
.xt-metric-card {
  display: flex;
  align-items: flex-start;
  gap: var(--xt-space-4);
  padding: var(--xt-space-5);
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-xl);
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-sm);
}

.xt-metric-card__icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  border-radius: var(--xt-radius-lg);
  background: var(--xt-bg-subtle);
  color: var(--xt-text-secondary);
  flex-shrink: 0;
}

.xt-metric-card__content {
  flex: 1;
  min-width: 0;
}

.xt-metric-card__label {
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-sm);
  font-weight: 700;
}

.xt-metric-card__value {
  margin-top: var(--xt-space-1);
  color: var(--xt-text);
  font-size: var(--xt-text-2xl);
  font-weight: 900;
  line-height: 1.2;
}

.xt-metric-card__unit {
  margin-left: var(--xt-space-1);
  color: var(--xt-text-muted);
  font-size: var(--xt-text-sm);
  font-weight: 500;
}

.xt-metric-card__change {
  margin-top: var(--xt-space-1);
  font-size: var(--xt-text-xs);
  font-weight: 800;
  color: var(--xt-text-muted);
}

.xt-metric-card__change--up { color: var(--xt-success); }
.xt-metric-card__change--down { color: var(--xt-danger); }

.xt-metric-card__spark {
  flex-shrink: 0;
  width: 64px;
  height: 32px;
}

.xt-metric-card--primary { border-left: 3px solid var(--xt-primary); }
.xt-metric-card--success { border-left: 3px solid var(--xt-success); }
.xt-metric-card--warning { border-left: 3px solid var(--xt-warning); }
.xt-metric-card--danger { border-left: 3px solid var(--xt-danger); }
</style>
