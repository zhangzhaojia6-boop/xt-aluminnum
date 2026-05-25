<template>
  <ul class="xt-kpi-bar" data-testid="manage-kpi-bar">
    <li
      v-for="item in items"
      :key="item.key"
      class="xt-kpi-bar__card"
      :class="[item.status ? `is-${item.status}` : '', item.tone ? `tone-${item.tone}` : '']"
      data-testid="kpi-card"
    >
      <div class="xt-kpi-bar__top">
        <div class="xt-kpi-bar__label">{{ item.label }}</div>
        <span v-if="item.deltaText" class="xt-kpi-bar__delta" :class="item.deltaTone ? `tone-${item.deltaTone}` : ''">
          {{ item.deltaText }}
        </span>
      </div>
      <div class="xt-kpi-bar__value">
        <span>{{ item.value }}</span>
        <small v-if="item.unit">{{ item.unit }}</small>
      </div>
      <Sparkline
        v-if="item.spark && item.spark.length > 1"
        class="xt-kpi-bar__spark"
        :points="item.spark"
        :tone="item.sparkTone || 'primary'"
      />
      <div v-else-if="item.hint" class="xt-kpi-bar__hint">{{ item.hint }}</div>
      <div v-else class="xt-kpi-bar__hint xt-kpi-bar__hint--placeholder">&nbsp;</div>
    </li>
  </ul>
</template>

<script setup>
import Sparkline from './Sparkline.vue'
defineProps({ items: { type: Array, default: () => [] } })
</script>

<style scoped>
.xt-kpi-bar { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--xt-space-3); grid-template-columns: repeat(5, 1fr); }
@media (max-width: 720px) { .xt-kpi-bar { grid-template-columns: repeat(3, 1fr); } }
.xt-kpi-bar__card {
  position: relative;
  padding: var(--xt-space-3) var(--xt-space-3);
  background: var(--xt-bg-panel);
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-md);
  display: grid; gap: var(--xt-space-1);
  overflow: hidden;
}
.xt-kpi-bar__card.is-muted { opacity: 0.55; }
.xt-kpi-bar__top { display: flex; align-items: center; justify-content: space-between; gap: var(--xt-space-2); }
.xt-kpi-bar__label { font-size: var(--xt-text-xs); color: var(--xt-text-muted); font-weight: 700; }
.xt-kpi-bar__delta {
  font-size: 11px; font-weight: 800;
  padding: 1px 6px; border-radius: var(--xt-radius-pill);
  background: var(--xt-bg-panel-soft); color: var(--xt-text-muted);
  font-variant-numeric: tabular-nums;
  border: 1px solid transparent;
}
.xt-kpi-bar__delta.tone-positive {
  color: var(--xt-success, var(--xt-color-success));
  background: var(--xt-success-light, rgba(59, 165, 92, 0.12));
  border-color: var(--xt-success-border, rgba(59, 165, 92, 0.28));
}
.xt-kpi-bar__delta.tone-negative {
  color: var(--xt-danger, var(--xt-color-danger));
  background: var(--xt-danger-light, rgba(214, 82, 65, 0.12));
  border-color: var(--xt-danger-border, rgba(214, 82, 65, 0.28));
}
.xt-kpi-bar__value { display: flex; align-items: baseline; gap: var(--xt-space-1); font-size: var(--xt-text-2xl); font-weight: 850; color: var(--xt-text); font-variant-numeric: tabular-nums; letter-spacing: -0.01em; }
.xt-kpi-bar__value small { font-size: var(--xt-text-xs); color: var(--xt-text-secondary); font-weight: 700; }
.xt-kpi-bar__card.tone-positive .xt-kpi-bar__value { color: var(--xt-success, var(--xt-color-success)); }
.xt-kpi-bar__card.tone-negative .xt-kpi-bar__value { color: var(--xt-danger, var(--xt-color-danger)); }
.xt-kpi-bar__spark { width: 100%; height: 28px; margin-top: 2px; }
.xt-kpi-bar__hint { font-size: var(--xt-text-xs); color: var(--xt-text-muted); }
.xt-kpi-bar__hint--placeholder { height: 28px; }
</style>
