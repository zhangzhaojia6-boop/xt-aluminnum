<template>
  <ul class="xt-kpi-bar" data-testid="manage-kpi-bar">
    <li
      v-for="item in items"
      :key="item.key"
      class="xt-kpi-bar__card"
      :class="[item.status ? `is-${item.status}` : '', item.tone ? `tone-${item.tone}` : '']"
      data-testid="kpi-card"
    >
      <div class="xt-kpi-bar__label">{{ item.label }}</div>
      <div class="xt-kpi-bar__value">
        <span>{{ item.value }}</span>
        <small v-if="item.unit">{{ item.unit }}</small>
      </div>
      <div v-if="item.hint" class="xt-kpi-bar__hint">{{ item.hint }}</div>
    </li>
  </ul>
</template>

<script setup>
defineProps({ items: { type: Array, default: () => [] } })
</script>

<style scoped>
.xt-kpi-bar { list-style: none; margin: 0; padding: 0; display: grid; gap: var(--xt-space-3); grid-template-columns: repeat(5, 1fr); }
@media (max-width: 720px) { .xt-kpi-bar { grid-template-columns: repeat(3, 1fr); } .xt-kpi-bar__card:nth-child(n+4) { grid-column: span 1; } }
.xt-kpi-bar__card {
  padding: var(--xt-space-3) var(--xt-space-3);
  background: var(--xt-bg-panel);
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-md);
  display: grid; gap: var(--xt-space-1);
}
.xt-kpi-bar__card.is-muted { opacity: 0.55; }
.xt-kpi-bar__label { font-size: var(--xt-text-xs); color: var(--xt-text-muted); font-weight: 700; }
.xt-kpi-bar__value { display: flex; align-items: baseline; gap: var(--xt-space-1); font-size: var(--xt-text-2xl); font-weight: 850; color: var(--xt-text); font-variant-numeric: tabular-nums; }
.xt-kpi-bar__value small { font-size: var(--xt-text-xs); color: var(--xt-text-secondary); font-weight: 700; }
.xt-kpi-bar__card.tone-positive .xt-kpi-bar__value { color: var(--xt-color-success); }
.xt-kpi-bar__card.tone-negative .xt-kpi-bar__value { color: var(--xt-color-warning); }
.xt-kpi-bar__hint { font-size: var(--xt-text-xs); color: var(--xt-text-muted); }
</style>
