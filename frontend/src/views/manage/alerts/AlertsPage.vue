<template>
  <section class="xt-alerts" data-testid="manage-alerts">
    <header class="xt-alerts__header">
      <h1>异常</h1>
    </header>
    <component :is="activeSurfaceComponent" />
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import AnomalyReview from '../../attendance/AnomalyReview.vue'
import QualityCenter from '../../quality/QualityCenter.vue'
import ReconciliationCenter from '../../reconciliation/ReconciliationCenter.vue'

const route = useRoute()
const activeSurfaceComponent = computed(() => {
  if (route.query.surface === 'reconciliation') return ReconciliationCenter
  if (route.query.surface === 'quality') return QualityCenter
  return AnomalyReview
})
</script>

<style scoped>
.xt-alerts {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.xt-alerts__header h1 {
  margin: 0;
  font-size: 22px;
}
</style>
