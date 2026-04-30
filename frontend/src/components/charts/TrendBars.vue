<template>
  <div class="trend-bars">
    <article v-for="item in safeItems" :key="item.label" class="trend-bars__row">
      <span class="trend-bars__label">{{ item.label }}</span>
      <div class="trend-bars__track">
        <div class="trend-bars__fill" :style="{ width: `${item.percent}%` }"></div>
      </div>
      <span class="trend-bars__value">{{ item.value }}</span>
    </article>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  items: {
    type: Array,
    default: () => []
  }
})

const safeItems = computed(() => {
  return (props.items || []).map((item) => {
    const percent = Number(item?.percent ?? 0)
    return {
      label: item?.label || '--',
      value: item?.value ?? '--',
      percent: Number.isFinite(percent) ? Math.max(0, Math.min(100, percent)) : 0
    }
  })
})
</script>

<style scoped>
.trend-bars {
  display: grid;
  gap: 10px;
}

.trend-bars__row {
  display: grid;
  grid-template-columns: 110px minmax(0, 1fr) 70px;
  align-items: center;
  gap: 10px;
}

.trend-bars__label,
.trend-bars__value {
  font-size: 12px;
  color: var(--app-muted);
}

.trend-bars__value {
  text-align: right;
}

.trend-bars__track {
  height: 8px;
  border-radius: 999px;
  background: var(--xt-bg-panel-muted);
  overflow: hidden;
}

.trend-bars__fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, var(--xt-primary), var(--xt-info));
}
</style>
