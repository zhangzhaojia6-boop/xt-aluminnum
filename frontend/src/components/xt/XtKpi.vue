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
  position: relative;
  min-width: 0;
  padding: var(--xt-space-5);
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-xl);
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-sm);
}

.xt-kpi::before {
  content: '';
  position: absolute;
  top: var(--xt-space-4);
  right: var(--xt-space-4);
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--xt-border-strong);
}

.xt-kpi__label {
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-sm);
  font-weight: 700;
}

.xt-kpi__value {
  margin-top: var(--xt-space-2);
  color: var(--xt-text);
  font-size: var(--xt-text-3xl);
  font-weight: 900;
  line-height: 1.1;
  letter-spacing: 0;
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
  font-weight: 800;
}

.xt-kpi--primary { border-color: rgba(11, 99, 246, 0.20); }
.xt-kpi--success { border-color: rgba(22, 138, 85, 0.20); }
.xt-kpi--warning { border-color: rgba(183, 121, 31, 0.22); }
.xt-kpi--danger { border-color: rgba(194, 65, 52, 0.20); }
.xt-kpi--info { border-color: rgba(37, 99, 235, 0.18); }

.xt-kpi--primary::before { background: var(--xt-primary); box-shadow: 0 0 0 4px var(--xt-primary-light); }
.xt-kpi--success::before { background: var(--xt-success); box-shadow: 0 0 0 4px var(--xt-success-light); }
.xt-kpi--warning::before { background: var(--xt-warning); box-shadow: 0 0 0 4px var(--xt-warning-light); }
.xt-kpi--danger::before { background: var(--xt-danger); box-shadow: 0 0 0 4px var(--xt-danger-light); }
.xt-kpi--info::before { background: var(--xt-info); box-shadow: 0 0 0 4px var(--xt-info-light); }
</style>
