<template>
  <section class="xt-alerts-legacy" data-testid="manage-alerts-legacy">
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
