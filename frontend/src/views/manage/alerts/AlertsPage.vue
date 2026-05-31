<template>
  <section class="xt-alerts" data-testid="manage-alerts">
    <header class="xt-alerts__hero">
      <div class="xt-alerts__title-block">
        <span class="xt-alerts__eyebrow">ALERT COMMAND</span>
        <h1>异常</h1>
      </div>
      <div class="xt-alerts__date-dock">
        <DateSwitcher
          :model-value="timeline.targetDate.value"
          :loading="timeline.loading.value"
          :freshness="timeline.freshnessStatus.value"
          @step="timeline.stepDate"
          @refresh="timeline.load"
          @pick="(d) => timeline.targetDate.value = d"
        />
      </div>
    </header>

    <section class="xt-alerts__stats" data-testid="manage-alerts-stats">
      <article
        v-for="item in alertStats"
        :key="item.key"
        class="xt-alerts__stat"
        :class="`xt-alerts__stat--${item.tone}`"
      >
        <span class="xt-alerts__stat-label"><i></i>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </article>
    </section>

    <section class="xt-alerts__filters" data-testid="manage-alerts-filters">
      <DomainFilterChips
        :model-value="timeline.domains.value"
        :counts="timeline.domainCounts.value"
        @update:model-value="onDomainsChange"
      />
    </section>

    <section class="xt-alerts__timeline-shell">
      <div class="xt-alerts__timeline-head">
        <div>
          <span class="xt-alerts__eyebrow">EXCEPTION MATRIX</span>
          <h2>异常事件流</h2>
        </div>
        <div class="xt-alerts__timeline-meta">
          <span>{{ timeline.targetDate.value }}</span>
          <span>{{ timeline.filteredEvents.value.length }} 件</span>
        </div>
      </div>
      <EventTimeline
        :events="timeline.filteredEvents.value"
        :total-count="timeline.filteredEvents.value.length"
        :open-count="openCount"
        :target-date="timeline.targetDate.value"
      />
    </section>
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
  timeline.setDomains(next)
  syncRouteFromDomains(next)
}

const openCount = computed(
  () => timeline.filteredEvents.value.filter((e) => e.status === 'open').length
)
const alertStats = computed(() => {
  const total = timeline.filteredEvents.value.length
  return [
    { key: 'total', label: '全部异常', value: total, tone: 'cyan' },
    { key: 'open', label: '未结', value: openCount.value, tone: 'alert' },
    { key: 'closed', label: '已处理', value: Math.max(0, total - openCount.value), tone: 'blue' },
    { key: 'domain', label: '筛选域', value: timeline.domains.value.length || '全部', tone: 'amber' }
  ]
})

onMounted(() => {
  timeline.setDomains(readDomainsFromRoute())
  if (route.query.surface) syncRouteFromDomains(timeline.domains.value)
  timeline.load()
})

function sameDomains(a, b) {
  if (a.length !== b.length) return false
  const sa = [...a].sort()
  const sb = [...b].sort()
  return sa.every((v, i) => v === sb[i])
}

watch(() => route.query, () => {
  const next = readDomainsFromRoute()
  if (!sameDomains(next, timeline.domains.value)) {
    timeline.setDomains(next)
  }
})
</script>

<style scoped>
.xt-alerts {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: var(--xt-space-4);
}

.xt-alerts::before {
  position: fixed;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  content: '';
  background:
    radial-gradient(circle at top left, color-mix(in srgb, var(--xt-primary) 18%, transparent), transparent 30%),
    linear-gradient(color-mix(in srgb, var(--xt-primary) 5%, transparent) 1px, transparent 1px),
    linear-gradient(90deg, color-mix(in srgb, var(--xt-primary) 5%, transparent) 1px, transparent 1px);
  background-size: auto, var(--xt-space-8) var(--xt-space-8), var(--xt-space-8) var(--xt-space-8);
}

.xt-alerts__hero,
.xt-alerts__stat,
.xt-alerts__filters,
.xt-alerts__timeline-shell {
  position: relative;
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--xt-primary) 22%, var(--xt-border));
  background:
    linear-gradient(180deg, color-mix(in srgb, var(--xt-primary) 8%, transparent), transparent),
    color-mix(in srgb, var(--xt-bg-ink-panel) 88%, var(--xt-bg-panel));
  box-shadow: inset 0 1px 0 color-mix(in srgb, var(--xt-text-inverse) 8%, transparent);
  backdrop-filter: blur(14px);
}

.xt-alerts__hero::after,
.xt-alerts__stat::after,
.xt-alerts__timeline-shell::after {
  position: absolute;
  inset: 0;
  pointer-events: none;
  content: '';
  background: linear-gradient(115deg, transparent, color-mix(in srgb, var(--xt-primary) 14%, transparent), transparent);
  transform: translateX(-120%);
  animation: xtAlertsSweep 7s ease-in-out infinite;
}

.xt-alerts__hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-4);
  min-height: 148px;
  padding: var(--xt-space-6);
  border-radius: var(--xt-radius-2xl);
}

.xt-alerts__title-block,
.xt-alerts__date-dock,
.xt-alerts__timeline-head,
.xt-alerts__stat > * {
  position: relative;
  z-index: 1;
}

.xt-alerts__eyebrow {
  display: inline-flex;
  align-items: center;
  gap: var(--xt-space-2);
  color: var(--xt-primary);
  font-size: var(--xt-text-xs);
  font-weight: 850;
  letter-spacing: 0.16em;
}

.xt-alerts__eyebrow::before {
  width: var(--xt-space-2);
  height: var(--xt-space-2);
  content: '';
  border-radius: var(--xt-radius-pill);
  background: var(--xt-primary);
  box-shadow: 0 0 var(--xt-space-4) var(--xt-primary);
}

.xt-alerts h1,
.xt-alerts h2 {
  margin: 0;
  color: var(--xt-text-inverse);
  font-family: var(--xt-font-number);
  letter-spacing: -0.04em;
}

.xt-alerts h1 {
  margin-top: var(--xt-space-3);
  font-size: clamp(var(--xt-text-3xl), 5vw, calc(var(--xt-text-3xl) * 1.8));
  font-weight: 950;
  line-height: 1;
  text-shadow: 0 0 var(--xt-space-8) color-mix(in srgb, var(--xt-primary) 26%, transparent);
}

.xt-alerts h2 {
  margin-top: var(--xt-space-2);
  font-size: var(--xt-text-xl);
  font-weight: 900;
}

.xt-alerts__date-dock {
  padding: var(--xt-space-2);
  border: 1px solid color-mix(in srgb, var(--xt-primary) 18%, var(--xt-border));
  border-radius: var(--xt-radius-xl);
  background: color-mix(in srgb, var(--xt-bg-ink) 72%, transparent);
}

.xt-alerts__stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--xt-space-4);
}

.xt-alerts__stat {
  min-height: 132px;
  padding: var(--xt-space-5);
  border-radius: var(--xt-radius-xl);
}

.xt-alerts__stat-label {
  display: flex;
  align-items: center;
  gap: var(--xt-space-2);
  color: color-mix(in srgb, var(--xt-text-inverse) 68%, var(--xt-primary));
  font-size: var(--xt-text-xs);
  font-weight: 850;
  letter-spacing: 0.12em;
}

.xt-alerts__stat-label i {
  width: var(--xt-space-2);
  height: var(--xt-space-2);
  border-radius: var(--xt-radius-pill);
  background: currentColor;
  box-shadow: 0 0 var(--xt-space-4) currentColor;
  animation: xtAlertsPulse 1.8s ease-in-out infinite;
}

.xt-alerts__stat strong {
  display: block;
  margin-top: var(--xt-space-5);
  color: var(--xt-primary);
  font-family: var(--xt-font-number);
  font-size: clamp(var(--xt-text-3xl), 4vw, calc(var(--xt-text-3xl) * 1.45));
  line-height: 1;
  text-shadow: 0 0 var(--xt-space-6) color-mix(in srgb, var(--xt-primary) 34%, transparent);
}

.xt-alerts__stat--alert strong,
.xt-alerts__stat--alert .xt-alerts__stat-label i {
  color: color-mix(in srgb, var(--xt-danger) 72%, var(--xt-text-inverse));
}

.xt-alerts__stat--blue strong,
.xt-alerts__stat--blue .xt-alerts__stat-label i {
  color: color-mix(in srgb, var(--xt-info) 72%, var(--xt-text-inverse));
}

.xt-alerts__stat--amber strong,
.xt-alerts__stat--amber .xt-alerts__stat-label i {
  color: color-mix(in srgb, var(--xt-warning) 72%, var(--xt-text-inverse));
}

.xt-alerts__filters {
  padding: var(--xt-space-3);
  border-radius: var(--xt-radius-xl);
}

.xt-alerts__filters :deep(.xt-domain-chip) {
  height: 34px;
  border: 1px solid color-mix(in srgb, var(--xt-primary) 18%, var(--xt-border));
  background: color-mix(in srgb, var(--xt-bg-ink-panel) 78%, transparent);
  color: var(--xt-text-secondary);
}

.xt-alerts__filters :deep(.xt-domain-chip.is-active) {
  background: color-mix(in srgb, var(--xt-primary) 24%, var(--xt-bg-ink-panel));
  color: var(--xt-primary);
  box-shadow: inset 0 0 var(--xt-space-4) color-mix(in srgb, var(--xt-primary) 12%, transparent);
}

.xt-alerts__timeline-shell {
  border-radius: var(--xt-radius-2xl);
}

.xt-alerts__timeline-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-4);
  padding: var(--xt-space-5) var(--xt-space-6);
  border-bottom: 1px solid color-mix(in srgb, var(--xt-primary) 18%, var(--xt-border));
  background: color-mix(in srgb, var(--xt-primary) 5%, transparent);
}

.xt-alerts__timeline-meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--xt-space-2);
}

.xt-alerts__timeline-meta span {
  min-height: 28px;
  padding: var(--xt-space-1) var(--xt-space-3);
  border: 1px solid color-mix(in srgb, var(--xt-primary) 18%, var(--xt-border));
  border-radius: var(--xt-radius-pill);
  background: color-mix(in srgb, var(--xt-primary) 8%, transparent);
  color: var(--xt-text-inverse);
  font-size: var(--xt-text-xs);
  font-weight: 850;
}

.xt-alerts__timeline-shell :deep(.xt-event-timeline) {
  border: 0;
  border-radius: 0;
  background: transparent;
}

.xt-alerts__timeline-shell :deep(.xt-event-timeline__summary) {
  border-bottom-color: color-mix(in srgb, var(--xt-primary) 16%, var(--xt-border));
  background: color-mix(in srgb, var(--xt-primary) 4%, transparent);
  color: color-mix(in srgb, var(--xt-text-inverse) 72%, transparent);
}

.xt-alerts__timeline-shell :deep(.xt-event-timeline__row) {
  border-bottom-color: color-mix(in srgb, var(--xt-primary) 14%, var(--xt-border));
}

.xt-alerts__timeline-shell :deep(.xt-event-timeline__empty) {
  color: color-mix(in srgb, var(--xt-text-inverse) 72%, transparent);
}

.xt-alerts__timeline-shell :deep(.xt-event-card__time),
.xt-alerts__timeline-shell :deep(.xt-event-card__arrow) {
  color: color-mix(in srgb, var(--xt-text-inverse) 48%, transparent);
}

.xt-alerts__timeline-shell :deep(.xt-event-card__summary) {
  color: color-mix(in srgb, var(--xt-text-inverse) 82%, var(--xt-primary));
}

@keyframes xtAlertsSweep {
  0%,
  70% {
    transform: translateX(-120%);
  }

  100% {
    transform: translateX(120%);
  }
}

@keyframes xtAlertsPulse {
  0%,
  100% {
    opacity: 0.56;
    transform: scale(0.88);
  }

  50% {
    opacity: 1;
    transform: scale(1.18);
  }
}

@media (max-width: 1080px) {
  .xt-alerts__stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .xt-alerts__hero,
  .xt-alerts__timeline-head {
    align-items: stretch;
    flex-direction: column;
  }

  .xt-alerts__hero {
    padding: var(--xt-space-5);
  }

  .xt-alerts__date-dock :deep(.xt-date-switcher) {
    width: 100%;
    flex-wrap: wrap;
  }

  .xt-alerts__date-dock :deep(.xt-date-switcher__label) {
    flex: 1 1 auto;
    justify-content: center;
  }

  .xt-alerts__stats {
    grid-template-columns: 1fr;
  }
}
</style>
