<template>
  <section class="xt-alerts" data-testid="manage-alerts">
    <header class="xt-alerts__header">
      <h1>异常</h1>
      <DateSwitcher
        :model-value="timeline.targetDate.value"
        :loading="timeline.loading.value"
        :freshness="timeline.freshnessStatus.value"
        @step="timeline.stepDate"
        @refresh="timeline.load"
      />
    </header>
    <DomainFilterChips
      :model-value="timeline.domains.value"
      :counts="timeline.domainCounts.value"
      @update:model-value="onDomainsChange"
    />
    <EventTimeline
      :events="timeline.filteredEvents.value"
      :total-count="timeline.filteredEvents.value.length"
      :open-count="openCount"
      :target-date="timeline.targetDate.value"
    />
  </section>
</template>

<script setup>
import { computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import DateSwitcher from '../../../components/manage/DateSwitcher.vue'
import DomainFilterChips from '../../../components/manage/DomainFilterChips.vue'
import EventTimeline from '../../../components/manage/EventTimeline.vue'
import { useAlertsTimeline } from '../../../composables/useAlertsTimeline.js'

const route = useRoute()
const router = useRouter()
const timeline = useAlertsTimeline()

const SURFACE_TO_DOMAIN = { anomaly: 'production', quality: 'quality', reconciliation: 'reconciliation' }

function readDomainsFromRoute() {
  const surface = route.query.surface
  if (surface && SURFACE_TO_DOMAIN[surface]) return [SURFACE_TO_DOMAIN[surface]]
  const d = route.query.domain
  if (Array.isArray(d)) return d
  if (typeof d === 'string' && d.length) return d.split(',').filter(Boolean)
  return []
}

function syncRouteFromDomains(domains) {
  const next = { ...route.query }
  delete next.surface
  if (domains.length === 0) delete next.domain
  else next.domain = domains.join(',')
  router.replace({ query: next })
}

function onDomainsChange(next) {
  timeline.domains.value = next
  syncRouteFromDomains(next)
}

const openCount = computed(
  () => timeline.filteredEvents.value.filter((e) => e.status === 'open').length
)

onMounted(() => {
  timeline.domains.value = readDomainsFromRoute()
  if (route.query.surface) syncRouteFromDomains(timeline.domains.value)
  timeline.load()
})

watch(() => route.query, () => {
  const next = readDomainsFromRoute()
  if (JSON.stringify(next) !== JSON.stringify(timeline.domains.value)) {
    timeline.domains.value = next
  }
})
</script>

<style scoped>
.xt-alerts { display: flex; flex-direction: column; gap: var(--xt-space-4); }
.xt-alerts__header { display: flex; align-items: center; justify-content: space-between; gap: var(--xt-space-3); flex-wrap: wrap; }
.xt-alerts__header h1 { margin: 0; font-size: var(--xt-text-2xl); font-weight: 850; color: var(--xt-text); }
@media (max-width: 720px) {
  .xt-alerts__header { flex-direction: column; align-items: stretch; }
}
</style>
