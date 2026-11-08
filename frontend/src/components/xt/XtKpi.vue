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
  border-radius: 4px;
  background: var(--xt-bg-panel);

}

.xt-kpi::before {
  content: '';
  position: absolute;
  top: var(--xt-space-4);
  right: var(--xt-space-4);
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: transparent;
}

.xt-kpi__label {
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-sm);
  font-weight: 600;
}

.xt-kpi__value {
  margin-top: var(--xt-space-2);
  color: var(--xt-text);
  font-size: var(--xt-text-3xl);
  font-weight: 600;
  line-height: 1.1;
  letter-spacing: 0;
}

.xt-kpi__unit {
  margin-left: var(--xt-space-1);
  color: var(--xt-text-secondary);

  font-size: var(--xt-text-sm);
  font-weight: 600;
}

.xt-kpi__trend {
  margin-top: var(--xt-space-2);
  color: var(--xt-text-muted);
  font-size: var(--xt-text-xs);
  font-weight: 600;
}

.xt-kpi--primary { border-color: var(--xt-primary-border); }
.xt-kpi--success { border-color: var(--xt-success-border); }
.xt-kpi--warning { border-color: var(--xt-warning-border); }
.xt-kpi--danger { border-color: var(--xt-danger-border); }
.xt-kpi--info { border-color: var(--xt-info-border); }

.xt-kpi--primary::before { background: var(--xt-primary);  }
.xt-kpi--success::before { background: transparent;  }
.xt-kpi--warning::before { background: transparent;  }
.xt-kpi--danger::before { background: transparent;  }
.xt-kpi--info::before { background: transparent;  }
</style>
