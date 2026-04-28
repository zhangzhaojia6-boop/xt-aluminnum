<template>
  <div class="xt-grid" :style="gridStyle">
    <slot />
  </div>
</template>

<script setup>
import { computed } from 'vue'

defineOptions({ name: 'XtGrid' })

const props = defineProps({
  min: {
    type: [String, Number],
    default: 240
  },
  gap: {
    type: [String, Number],
    default: 'var(--xt-space-4)'
  }
})

const gridStyle = computed(() => ({
  '--xt-grid-min': typeof props.min === 'number' ? `${props.min}px` : props.min,
  '--xt-grid-gap': typeof props.gap === 'number' ? `${props.gap}px` : props.gap
}))
</script>

<style scoped>
.xt-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(min(100%, var(--xt-grid-min)), 1fr));
  gap: var(--xt-grid-gap);
}
</style>
