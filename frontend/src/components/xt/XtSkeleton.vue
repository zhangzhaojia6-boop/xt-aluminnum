<template>
  <div class="xt-skeleton" aria-label="正在加载">
    <div v-for="row in rows" :key="row" class="xt-skeleton__row xt-shimmer" :style="rowStyle(row)" />
  </div>
</template>

<script setup>
defineOptions({ name: 'XtSkeleton' })

defineProps({
  rows: {
    type: Number,
    default: 3
  }
})

function rowStyle(row) {
  const width = row % 3 === 0 ? '72%' : row % 2 === 0 ? '88%' : '100%'
  return { width }
}
</script>

<style scoped>
.xt-skeleton {
  display: grid;
  gap: var(--xt-space-3);
}

.xt-skeleton__row {
  height: 16px;
}
</style>
