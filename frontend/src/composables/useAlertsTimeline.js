import { ref, computed, watch } from 'vue'
import dayjs from 'dayjs'
import {
  normalizeFactoryDirector,
  normalizeQuality,
  normalizeReconciliation,
  mergeAndSort
} from '../components/manage/_alertEventNormalize.js'

const DOMAINS = ['production', 'reporting', 'quality', 'reconciliation']
const FALLBACK_ROUTE = {
  production: '/manage/alerts/legacy?surface=anomaly',
  reporting: '/manage/alerts/legacy?surface=anomaly',
  quality: '/manage/alerts/legacy?surface=quality',
  reconciliation: '/manage/alerts/legacy?surface=reconciliation'
}

async function defaultFetchFD(params) {
  const { fetchFactoryDashboard } = await import('../api/dashboard.js')
  return fetchFactoryDashboard(params)
}
async function defaultFetchQ(params) {
  const { fetchQualityIssues } = await import('../api/quality.js')
  return fetchQualityIssues(params)
}
async function defaultFetchR(params) {
  const { fetchReconciliationItems } = await import('../api/reconciliation.js')
  return fetchReconciliationItems(params)
}

export function createAlertsTimeline({
  fetchFactoryDashboard: fdImpl = defaultFetchFD,
  fetchQualityIssues: qImpl = defaultFetchQ,
  fetchReconciliationItems: rImpl = defaultFetchR,
  now = new Date()
} = {}) {
  const yesterday = dayjs(now).subtract(1, 'day').format('YYYY-MM-DD')
  const targetDate = ref(yesterday)
  const domains = ref([])
  const events = ref([])
  const loading = ref(false)
  const lastError = ref('')
  const failed = ref({ production: false, reporting: false, quality: false, reconciliation: false })
  let inflight = Promise.resolve()

  function fallbackCard(domain) {
    return {
      id: `${domain}:__fallback__`,
      domain,
      occurredAt: `${targetDate.value}T23:59:59`,
      summary: '加载失败，点击查看老页',
      detailRoute: FALLBACK_ROUTE[domain],
      status: null,
      isFallback: true
    }
  }

  function load() {
    loading.value = true
    inflight = (async () => {
      const date = targetDate.value
      const [fd, q, r] = await Promise.allSettled([
        fdImpl({ target_date: date }),
        qImpl({ target_date: date }),
        rImpl({ target_date: date, status: 'open' })
      ])
      const buckets = []
      const fail = { production: false, reporting: false, quality: false, reconciliation: false }
      if (fd.status === 'fulfilled') {
        buckets.push(normalizeFactoryDirector(fd.value, date))
      } else {
        fail.production = true
        fail.reporting = true
        buckets.push([fallbackCard('production')])
      }
      if (q.status === 'fulfilled') {
        buckets.push(normalizeQuality(q.value, date))
      } else {
        fail.quality = true
        buckets.push([fallbackCard('quality')])
      }
      if (r.status === 'fulfilled') {
        buckets.push(normalizeReconciliation(r.value, date))
      } else {
        fail.reconciliation = true
        buckets.push([fallbackCard('reconciliation')])
      }
      failed.value = fail
      events.value = mergeAndSort(buckets)
      lastError.value = ''
      loading.value = false
    })()
    return inflight
  }

  watch(targetDate, () => load(), { flush: 'sync' })

  function stepDate(deltaDays) {
    targetDate.value = dayjs(targetDate.value).add(deltaDays, 'day').format('YYYY-MM-DD')
    return inflight
  }

  const domainCounts = computed(() => {
    const counts = { production: 0, reporting: 0, quality: 0, reconciliation: 0 }
    for (const e of events.value) {
      if (e.isFallback) continue
      if (counts[e.domain] != null) counts[e.domain] += 1
    }
    return counts
  })

  const filteredEvents = computed(() => {
    if (!domains.value.length) return events.value
    return events.value.filter((e) => domains.value.includes(e.domain))
  })

  const freshnessStatus = computed(() => {
    const fails = DOMAINS.filter((d) => failed.value[d]).length
    if (fails === 0) return 'green'
    if (fails >= 3) return 'red'
    return 'yellow'
  })

  return {
    targetDate, domains, events, filteredEvents, domainCounts,
    loading, lastError, freshnessStatus,
    load, stepDate
  }
}

export function useAlertsTimeline() {
  return createAlertsTimeline()
}
