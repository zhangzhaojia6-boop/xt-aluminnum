<template>
  <nav class="xt-kpi-ribbon" role="list">
    <slot />
  </nav>
</template>

<script setup>
defineOptions({ name: 'XtKpiRibbon' })

defineProps({
  wrap: {
    type: Boolean,
    default: false
  }
})
</script>

<style scoped>
.xt-kpi-ribbon {
  display: flex;
  gap: var(--xt-space-4);
  overflow-x: auto;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.xt-kpi-ribbon::-webkit-scrollbar {
  display: none;
}

.xt-kpi-ribbon > :deep(*) {
  flex: 1 1 0;
  min-width: 160px;
}
</style>
