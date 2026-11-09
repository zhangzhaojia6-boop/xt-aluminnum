<template>
  <section class="xt-alerts" data-testid="manage-alerts" data-visual-pass="stitch-image2-second-pass">
    <header class="xt-alerts__hero" aria-label="异常总览">
      <h1>异常</h1>
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

    <div
      v-if="capabilityStatusText"
      class="xt-alerts__capability-status"
      data-testid="manage-alerts-capability-status"
      role="status"
      aria-live="polite"
    >
      <span>系统状态</span>
      <strong>{{ capabilityStatusText }}</strong>
    </div>

    <section class="xt-alerts__stats" data-testid="manage-alerts-stats">
      <article
        v-for="item in alertStats"
        :key="item.key"
        class="xt-alerts__stat"
        :class="`xt-alerts__stat--${item.tone}`"
      >
        <span class="xt-alerts__stat-label">{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </article>
      <div
        v-if="businessEvents.length"
        class="xt-alerts__ratio"
        role="img"
        :aria-label="`未结 ${openCount} 条，已处理 ${businessEvents.length - openCount} 条`"
      >
        <i class="is-open" :style="{ flexGrow: openCount }"></i>
        <i class="is-closed" :style="{ flexGrow: businessEvents.length - openCount }"></i>
      </div>
    </section>

    <section class="xt-alerts__filters" data-testid="manage-alerts-filters">
      <DomainFilterChips
        :model-value="timeline.domains.value"
        :counts="timeline.domainCounts.value"
        @domain-change="onDomainsChange"
      />
    </section>

    <p v-if="initialLoading" class="xt-alerts__loading" role="status">正在读取异常</p>

    <section v-if="!initialLoading" class="xt-alerts__queues" data-testid="manage-alert-work-queues">
      <header class="xt-alerts__queue-head">
        <h2>异常处理队列</h2>
        <p>{{ workQueueSummary }}</p>
      </header>
      <div class="xt-alerts__queue-grid">
        <article
          v-for="queue in workQueues"
          :key="queue.key"
          class="xt-alerts__queue"
          :class="`tone-${queue.tone}`"
        >
          <header>
            <span>{{ queue.title }}</span>
            <strong>
              {{ queue.count }}
              <small v-if="queue.rawCount !== queue.count">{{ queue.rawCount }} 条</small>
            </strong>
          </header>
          <div v-if="queue.items.length" class="xt-alerts__queue-items">
            <RouterLink
              v-for="item in queue.items"
              :key="item.id"
              :to="item.route"
            >
              <span class="xt-alerts__queue-item-copy">
                <b>{{ item.text }}</b>
                <small v-if="queueItemMeta(item)">{{ queueItemMeta(item) }}</small>
              </span>
              <small v-if="item.rawCount > 1">{{ item.rawCount }} 条</small>
            </RouterLink>
          </div>
          <p v-else>当前无待处理</p>
        </article>
      </div>
    </section>

    <section v-if="!initialLoading" class="xt-alerts__timeline-shell" aria-label="异常清单">
      <div class="xt-alerts__timeline-head">
        <h2>异常事件流</h2>
        <div class="xt-alerts__timeline-meta">
          <span>{{ timeline.targetDate.value }}</span>
          <span>{{ actionCases.length }} 项</span>
          <span>{{ businessEvents.length }} 条原始异常</span>
        </div>
      </div>
      <EventTimeline
        :events="actionCases"
        :total-count="businessEvents.length"
        :open-count="openCount"
        :target-date="timeline.targetDate.value"
      />
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import DateSwitcher from '../../../components/manage/DateSwitcher.vue'
import DomainFilterChips from '../../../components/manage/DomainFilterChips.vue'
import EventTimeline from '../../../components/manage/EventTimeline.vue'
import {
  buildAlertQueueItemMeta,
  buildAlertWorkQueues,
  groupAlertEvents,
} from '../../../components/manage/_alertEventNormalize.js'
import { useAlertsTimeline } from '../../../composables/useAlertsTimeline.js'

const route = useRoute()
const router = useRouter()
const timeline = useAlertsTimeline()
let domainRouteSync = Promise.resolve()

const SURFACE_TO_DOMAIN = { anomaly: 'production', quality: 'quality', reconciliation: 'reconciliation', mes: 'mes' }

function readDomainsFromRoute() {
  const surface = route.query.surface
  if (surface && SURFACE_TO_DOMAIN[surface]) return [SURFACE_TO_DOMAIN[surface]]
  const d = route.query.domain
  if (Array.isArray(d)) return d
  if (typeof d === 'string' && d.length) return d.split(',').filter(Boolean)
  return []
}

function readTraceIdFromRoute() {
  const value = route.query.trace_id
  if (Array.isArray(value)) return typeof value[0] === 'string' ? value[0] : ''
  return typeof value === 'string' ? value : ''
}

function readTargetDateFromRoute() {
  const raw = route.query.target_date
  const value = Array.isArray(raw) ? raw[0] : raw
  return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : ''
}

function replaceRouteQuery(query) {
  domainRouteSync = domainRouteSync
    .catch(() => {})
    .then(() => router.replace({ query }))
}

function syncRouteFromDomains(domains) {
  const next = { ...route.query }
  delete next.surface
  if (domains.length === 0) delete next.domain
  else next.domain = domains.join(',')
  next.target_date = timeline.targetDate.value
  replaceRouteQuery(next)
}

function onDomainsChange(next) {
  timeline.setDomains(next)
  syncRouteFromDomains(next)
}

const initialLoading = computed(() => timeline.loading.value && timeline.events.value.length === 0)
const businessEvents = computed(
  () => timeline.filteredEvents.value.filter((event) => !event.isFallback)
)
const capabilityEvents = computed(
  () => timeline.events.value.filter((event) => event.isFallback)
)
const capabilityStatusText = computed(() => {
  const messages = capabilityEvents.value
    .map((event) => event.summary)
    .filter((message) => typeof message === 'string' && message.trim())
  const lastError = timeline.lastError.value.trim()
  if (lastError) messages.push(lastError)
  return [...new Set(messages)].join(' · ')
})
const openCount = computed(
  () => businessEvents.value.filter((event) => event.status === 'open').length
)
const actionCases = computed(() => groupAlertEvents(businessEvents.value))
const workQueues = computed(() => buildAlertWorkQueues(businessEvents.value))
const workQueueSummary = computed(() => {
  const caseCount = workQueues.value.reduce((sum, item) => sum + item.count, 0)
  const rawCount = workQueues.value.reduce((sum, item) => sum + item.rawCount, 0)
  const openCases = workQueues.value.reduce((sum, item) => sum + item.openCount, 0)
  return openCases > 0
    ? `${openCases} 项待处理 / ${rawCount} 条原始异常`
    : `${caseCount} 项已处理 / ${rawCount} 条原始异常`
})

const OWNER_ROLE_LABELS = {
  machine_operator: '机台主操',
  energy_chief: '全厂总电工',
  shipment_outflow_owner: '园区剪切内勤',
  overhaul_owner: '大修内勤',
  recovery_owner: '回收内勤',
  storage_owner: '成品库内勤',
  planning_owner: '计划内勤',
  quality_owner: '质检内勤',
  factory_dispatch: '工厂调度',
}

function queueItemMeta(item) {
  return buildAlertQueueItemMeta(item, OWNER_ROLE_LABELS)
}
const alertStats = computed(() => {
  const total = businessEvents.value.length
  const shown = (value) => (initialLoading.value ? '—' : value)
  return [
    { key: 'total', label: '全部异常', value: shown(total), tone: 'cyan' },
    { key: 'open', label: '未结', value: shown(openCount.value), tone: 'alert' },
    { key: 'closed', label: '已处理', value: shown(Math.max(0, total - openCount.value)), tone: 'blue' },
    { key: 'case', label: '处理事项', value: shown(actionCases.value.length), tone: 'amber' }
  ]
})

onMounted(() => {
  timeline.setDomains(readDomainsFromRoute())
  timeline.setTraceId(readTraceIdFromRoute())
  const requestedDate = readTargetDateFromRoute()
  if (requestedDate && requestedDate !== timeline.targetDate.value) {
    timeline.targetDate.value = requestedDate
  } else {
    timeline.load()
  }
  if (route.query.surface) syncRouteFromDomains(timeline.domains.value)
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
  const requestedDate = readTargetDateFromRoute()
  if (requestedDate && requestedDate !== timeline.targetDate.value) {
    timeline.targetDate.value = requestedDate
  }
  timeline.setTraceId(readTraceIdFromRoute())
})

watch(timeline.targetDate, (next) => {
  if (readTargetDateFromRoute() === next) return
  replaceRouteQuery({ ...route.query, target_date: next })
})
</script>

<style scoped>
.xt-alerts {
  display: flex;
  flex-direction: column;
  gap: var(--xt-space-8);
}

.xt-alerts__hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-4);
}

.xt-alerts h1,
.xt-alerts h2 {
  margin: 0;
  color: var(--xt-text);
  font-weight: 600;
}

.xt-alerts h1 {
  font-size: clamp(var(--xt-text-2xl), 3vw, 40px);
  letter-spacing: -0.02em;
}

.xt-alerts h2 {
  font-size: var(--xt-text-lg);
}

.xt-alerts__capability-status {
  display: flex;
  align-items: center;
  gap: var(--xt-space-3);
  padding: var(--xt-space-2) 0;
  border-block: 1px solid var(--xt-border);
  color: var(--xt-text);
  font-size: var(--xt-text-xs);
}

.xt-alerts__capability-status span {
  flex: 0 0 auto;
  color: var(--xt-warning);
  font-weight: 600;
}

.xt-alerts__capability-status strong {
  min-width: 0;
  overflow: hidden;
  font-weight: 600;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.xt-alerts__stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--xt-space-4) var(--xt-space-6);
}

.xt-alerts__stat-label {
  display: block;
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-sm);
}

.xt-alerts__stat strong {
  display: block;
  margin-top: var(--xt-space-2);
  color: var(--xt-primary);
  font-size: clamp(32px, 4vw, 48px);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  line-height: 1;
}

.xt-alerts__stat--alert strong {
  color: var(--xt-danger);
}

.xt-alerts__stat--blue strong {
  color: var(--xt-text);
}

.xt-alerts__stat--amber strong {
  color: var(--xt-warning);
}

.xt-alerts__ratio {
  display: flex;
  grid-column: 1 / -1;
  gap: 2px;
  height: 8px;
}

.xt-alerts__ratio i {
  flex-basis: 0;
  border-radius: 2px;
  transform-origin: left;
  animation: xt-alerts-ratio-grow 800ms cubic-bezier(0.16, 1, 0.3, 1) backwards;
}

.xt-alerts__ratio .is-open {
  background: var(--xt-danger);
}

.xt-alerts__ratio .is-closed {
  background: var(--xt-primary);
}

.xt-alerts__loading {
  margin: 0;
  color: var(--xt-text-muted);
  font-size: var(--xt-text-sm);
}

.xt-alerts__queues {
  display: grid;
  gap: var(--xt-space-4);
}

.xt-alerts__queue-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--xt-space-4);
  flex-wrap: wrap;
}

.xt-alerts__queue-head p {
  margin: 0;
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-sm);
}

.xt-alerts__queue-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--xt-space-6);
}

.xt-alerts__queue {
  display: grid;
  align-content: start;
  gap: var(--xt-space-2);
  padding-top: var(--xt-space-3);
  border-top: 2px solid var(--xt-border);
}

.xt-alerts__queue.tone-danger {
  border-top-color: var(--xt-danger);
}

.xt-alerts__queue.tone-warning {
  border-top-color: var(--xt-warning);
}

.xt-alerts__queue header {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--xt-space-2);
}

.xt-alerts__queue header span {
  color: var(--xt-text);
  font-size: var(--xt-text-sm);
  font-weight: 600;
}

.xt-alerts__queue header strong {
  display: inline-flex;
  align-items: baseline;
  gap: var(--xt-space-1);
  color: var(--xt-text);
  font-size: var(--xt-text-2xl);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  line-height: 1;
}

.xt-alerts__queue header strong small {
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-xs);
  font-weight: 400;
}

.xt-alerts__queue-items {
  display: grid;
}

.xt-alerts__queue-items a {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-2);
  min-width: 0;
  padding: var(--xt-space-2) 0;
  color: var(--xt-primary);
  font-size: var(--xt-text-sm);
  text-decoration: none;
}

.xt-alerts__queue-items a + a {
  border-top: 1px solid var(--xt-border);
}

@media (hover: hover) {
  .xt-alerts__queue-items a:hover b {
    text-decoration: underline;
  }
}

.xt-alerts__queue-item-copy {
  display: grid;
  gap: 2px;
  min-width: 0;
}

.xt-alerts__queue-item-copy b {
  overflow: hidden;
  color: inherit;
  font-weight: 500;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.xt-alerts__queue-item-copy small {
  overflow: hidden;
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-xs);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.xt-alerts__queue-items a > small {
  flex: 0 0 auto;
  color: var(--xt-warning);
  font-size: var(--xt-text-xs);
}

.xt-alerts__queue p {
  margin: 0;
  color: var(--xt-text-muted);
  font-size: var(--xt-text-sm);
}

.xt-alerts__filters :deep(.xt-domain-chip) {
  height: 34px;
  border: 1px solid var(--xt-border);
  background: transparent;
  color: var(--xt-text-secondary);
}

.xt-alerts__filters :deep(.xt-domain-chip.is-active) {
  border-color: var(--xt-primary);
  background: var(--xt-primary);
  color: var(--xt-text-inverse);
}

.xt-alerts__timeline-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--xt-space-4);
  padding-bottom: var(--xt-space-3);
}

.xt-alerts__timeline-meta {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: var(--xt-space-4);
}

.xt-alerts__timeline-meta span {
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-sm);
  font-variant-numeric: tabular-nums;
}

.xt-alerts__timeline-shell :deep(.xt-event-timeline) {
  border: 0;
  border-top: 1px solid var(--xt-border);
  border-radius: 0;
  background: transparent;
}

.xt-alerts__timeline-shell :deep(.xt-event-timeline__summary) {
  border-bottom-color: var(--xt-border);
  background: transparent;
  color: var(--xt-text-secondary);
}

.xt-alerts__timeline-shell :deep(.xt-event-timeline__row) {
  border-bottom-color: var(--xt-border);
}

.xt-alerts__timeline-shell :deep(.xt-event-timeline__empty) {
  color: var(--xt-text-muted);
}

.xt-alerts__timeline-shell :deep(.xt-event-card__time),
.xt-alerts__timeline-shell :deep(.xt-event-card__arrow) {
  color: var(--xt-text-secondary);
}

.xt-alerts__timeline-shell :deep(.xt-event-card__summary) {
  color: var(--xt-text-secondary);
}

@keyframes xt-alerts-ratio-grow {
  from { transform: scaleX(0); }
}

@media (max-width: 1080px) {
  .xt-alerts__queue-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .xt-alerts__hero,
  .xt-alerts__timeline-head {
    align-items: stretch;
    flex-direction: column;
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
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .xt-alerts__queue-grid {
    grid-template-columns: 1fr;
  }

  .xt-alerts__timeline-meta {
    justify-content: flex-start;
  }

  .xt-alerts__capability-status {
    align-items: flex-start;
  }

  .xt-alerts__capability-status strong {
    white-space: normal;
  }
}

@media (prefers-reduced-motion: reduce) {
  .xt-alerts__ratio i {
    animation: none;
  }
}
</style>
