<template>
  <article class="xt-kpi" :class="[`xt-kpi--${tone}`]">
    <div class="xt-kpi__label">{{ label }}</div>
    <div class="xt-kpi__value xt-countup">
      {{ value }}<span v-if="unit" class="xt-kpi__unit">{{ unit }}</span>
    </div>
    <div v-if="trend || $slots.trend" class="xt-kpi__trend">
      <slot name="trend">{{ trend }}</slot>
    </div>
  </article>
</template>

<script setup>
defineOptions({ name: 'XtKpi' })

defineProps({
  label: {
    type: String,
    required: true
  },
  value: {
    type: [String, Number],
    required: true
  },
  unit: {
    type: String,
    default: ''
  },
  trend: {
    type: String,
    default: ''
  },
  tone: {
    type: String,
    default: 'neutral',
    validator: value => ['neutral', 'primary', 'success', 'warning', 'danger', 'info'].includes(value)
  }
})
</script>

<style scoped>
.xt-kpi {
  min-width: 0;
  padding: var(--xt-space-5);
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-xl);
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-sm);
}

.xt-kpi__label {
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-sm);
}

.xt-kpi__value {
  margin-top: var(--xt-space-2);
  color: var(--xt-text);
  font-size: var(--xt-text-3xl);
  font-weight: 700;
  line-height: 1.1;
}

.xt-kpi__unit {
  margin-left: var(--xt-space-1);
  color: var(--xt-text-secondary);
  font-family: var(--xt-font-body);
  font-size: var(--xt-text-sm);
  font-weight: 500;
}

.xt-kpi__trend {
  margin-top: var(--xt-space-2);
  color: var(--xt-text-muted);
  font-size: var(--xt-text-xs);
}

.xt-kpi--primary { border-color: rgba(0, 113, 227, 0.18); background: linear-gradient(180deg, var(--xt-primary-light), var(--xt-bg-panel)); }
.xt-kpi--success { border-color: rgba(34, 197, 94, 0.18); background: linear-gradient(180deg, var(--xt-success-light), var(--xt-bg-panel)); }
.xt-kpi--warning { border-color: rgba(245, 158, 11, 0.18); background: linear-gradient(180deg, var(--xt-warning-light), var(--xt-bg-panel)); }
.xt-kpi--danger { border-color: rgba(239, 68, 68, 0.18); background: linear-gradient(180deg, var(--xt-danger-light), var(--xt-bg-panel)); }
.xt-kpi--info { border-color: rgba(59, 130, 246, 0.18); background: linear-gradient(180deg, var(--xt-info-light), var(--xt-bg-panel)); }
</style>
