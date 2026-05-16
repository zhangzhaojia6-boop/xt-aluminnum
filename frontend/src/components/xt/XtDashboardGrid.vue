<template>
  <div class="xt-dashboard-grid" :style="gridStyle">
    <slot />
  </div>
</template>

<script setup>
import { computed } from 'vue'

defineOptions({ name: 'XtDashboardGrid' })

const props = defineProps({
  columns: {
    type: Number,
    default: 3
  },
  gap: {
    type: String,
    default: 'normal',
    validator: value => ['tight', 'normal', 'wide'].includes(value)
  }
})

const gapMap = { tight: 'var(--xt-space-3)', normal: 'var(--xt-space-5)', wide: 'var(--xt-space-6)' }

const gridStyle = computed(() => ({
  '--grid-columns': props.columns,
  '--grid-gap': gapMap[props.gap]
}))
</script>

<style scoped>
.xt-dashboard-grid {
  display: grid;
  grid-template-columns: repeat(var(--grid-columns), 1fr);
  gap: var(--grid-gap);
}

@media (max-width: 1200px) {
  .xt-dashboard-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 768px) {
  .xt-dashboard-grid {
    grid-template-columns: 1fr;
  }
}
</style>
