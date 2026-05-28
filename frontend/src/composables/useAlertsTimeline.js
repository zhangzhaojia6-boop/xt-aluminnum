import { ref, computed, watch } from 'vue'
import dayjs from 'dayjs'
import {
  normalizeFactoryDirector,
  normalizeQuality,
  normalizeReconciliation,
  mergeAndSort
} from '../components/manage/_alertEventNormalize.js'

const FALLBACK_ROUTE = {
  production: '/manage/alerts?surface=anomaly',
  quality: '/manage/alerts?surface=quality',
  reconciliation: '/manage/alerts?surface=reconciliation'
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
  const endpointFailed = ref({ factoryDirector: false, quality: false, reconciliation: false })
  let token = 0
  let inflight = Promise.resolve()

  function fallbackCard(domain) {
    return {
      id: `${domain}:__fallback__`,
      domain,
      occurredAt: `${targetDate.value}T23:59:59`,
      summary: '加载失败，点击查看异常页',
      detailRoute: FALLBACK_ROUTE[domain],
      status: null,
      isFallback: true
    }
  }

  function load() {
    loading.value = true
    const my = ++token
    inflight = (async () => {
      const date = targetDate.value
      try {
        const [fd, q, r] = await Promise.allSettled([
          fdImpl({ target_date: date }),
          qImpl({ target_date: date }),
          rImpl({ target_date: date, status: 'open' })
        ])
        if (my !== token) return
        const buckets = []
        const fail = { factoryDirector: false, quality: false, reconciliation: false }
        if (fd.status === 'fulfilled') {
          buckets.push(normalizeFactoryDirector(fd.value, date))
        } else {
          fail.factoryDirector = true
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
        endpointFailed.value = fail
        events.value = mergeAndSort(buckets)
        const fails = (fail.factoryDirector ? 1 : 0) + (fail.quality ? 1 : 0) + (fail.reconciliation ? 1 : 0)
        lastError.value = fails >= 2 ? '部分数据加载失败，已切换占位卡' : ''
      } finally {
        if (my === token) loading.value = false
      }
    })()
    return inflight
  }

  watch(targetDate, () => load(), { flush: 'sync' })

  function setDomains(next) {
    domains.value = Array.isArray(next) ? [...next] : []
  }

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
    const f = endpointFailed.value
    const fails = (f.factoryDirector ? 1 : 0) + (f.quality ? 1 : 0) + (f.reconciliation ? 1 : 0)
    if (fails === 0) return 'green'
    if (fails >= 3) return 'red'
    return 'yellow'
  })

  return {
    targetDate, domains, events, filteredEvents, domainCounts,
    loading, lastError, freshnessStatus,
    load, stepDate, setDomains
  }
}

export function useAlertsTimeline() {
  return createAlertsTimeline()
}
