<template>
  <div class="kpi-strip">
    <AppKpiCard
      v-for="item in items"
      :key="item.label"
      :label="item.label"
      :value="item.value"
      :unit="item.unit"
      :trend="item.trend"
      :tone="item.tone"
    />
  </div>
</template>

<script setup>
import AppKpiCard from './AppKpiCard.vue'

defineProps({
  items: {
    type: Array,
    default: () => []
  }
})
</script>
