<template>
  <div class="xt-cost-line" :class="{ 'is-muted': muted }" data-testid="manage-cost-line">
    <span class="xt-cost-line__label">今日估算成本</span>
    <span class="xt-cost-line__value">{{ display }}</span>
    <span class="xt-cost-line__unit">{{ muted ? '' : '万' }}</span>
    <span class="xt-cost-line__pill">口径：估算</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({ estimate: { type: Object, default: () => ({}) } })
const muted = computed(() => !props.estimate?.estimate_ready || props.estimate?.estimated_cost == null)
const display = computed(() => {
  if (muted.value) return '—'
  return (Number(props.estimate.estimated_cost) / 10000).toFixed(2)
})
</script>

<style scoped>
.xt-cost-line {
  display: flex; align-items: baseline; gap: var(--xt-space-2);
  padding: var(--xt-space-3); background: var(--xt-bg-panel);
  border: 1px solid var(--xt-border); border-radius: var(--xt-radius-md);
}
.xt-cost-line.is-muted { opacity: 0.6; }
.xt-cost-line__label { font-size: var(--xt-text-sm); color: var(--xt-text-secondary); font-weight: 700; }
.xt-cost-line__value { font-size: var(--xt-text-xl); font-weight: 850; color: var(--xt-text); font-variant-numeric: tabular-nums; }
.xt-cost-line__unit { font-size: var(--xt-text-sm); color: var(--xt-text-secondary); }
.xt-cost-line__pill {
  margin-left: auto; padding: 2px var(--xt-space-2);
  background: var(--xt-bg-panel-soft); color: var(--xt-text-muted);
  font-size: var(--xt-text-xs); font-weight: 700;
  border-radius: var(--xt-radius-pill);
}
</style>
