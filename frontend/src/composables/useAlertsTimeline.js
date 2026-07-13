import { ref, computed, watch } from 'vue'
import dayjs from 'dayjs'
import {
  normalizeFactoryDirector,
  normalizeLiveMissingReports,
  normalizeMesFillGaps,
  normalizeDailyFactAlerts,
  normalizeQuality,
  normalizeReconciliation,
  mergeAndSort
} from '../components/manage/_alertEventNormalize.js'

const FALLBACK_ROUTE = {
  production: '/manage/alerts?surface=anomaly',
  reporting: '/manage/fill-details',
  quality: '/manage/alerts?surface=quality',
  reconciliation: '/manage/alerts?surface=reconciliation',
  mes: '/manage/fill-details'
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
async function defaultFetchM(params) {
  const { fetchMesFillGaps } = await import('../api/realtime.js')
  return fetchMesFillGaps(params)
}
async function defaultFetchLive(params) {
  const { fetchLiveAggregation } = await import('../api/realtime.js')
  return fetchLiveAggregation(params)
}
async function defaultFetchDaily(params) {
  const { fetchDailyProduction } = await import('../api/dashboard.js')
  return fetchDailyProduction(params)
}

export function createAlertsTimeline(options = {}) {
  const {
    fetchFactoryDashboard: fdImpl = defaultFetchFD,
    fetchQualityIssues: qImpl = defaultFetchQ,
    fetchReconciliationItems: rImpl = defaultFetchR,
    fetchMesFillGaps: mImpl = defaultFetchM,
    fetchLiveAggregation: liveImpl = defaultFetchLive,
    now = new Date(),
    traceId: initialTraceId = '',
  } = options
  const legacyFetchKeys = [
    'fetchFactoryDashboard',
    'fetchQualityIssues',
    'fetchReconciliationItems',
    'fetchMesFillGaps',
    'fetchLiveAggregation',
  ]
  const hasCustomLegacyFetch = legacyFetchKeys.some((key) => Object.prototype.hasOwnProperty.call(options, key))
  const dailyEnabled = Object.prototype.hasOwnProperty.call(options, 'fetchDailyProduction') || !hasCustomLegacyFetch
  const dailyImpl = options.fetchDailyProduction || defaultFetchDaily
  const yesterday = dayjs(now).subtract(1, 'day').format('YYYY-MM-DD')
  const targetDate = ref(yesterday)
  const domains = ref([])
  const traceId = ref(typeof initialTraceId === 'string' ? initialTraceId : '')
  const events = ref([])
  const loading = ref(false)
  const lastError = ref('')
  const endpointFailed = ref({ factoryDirector: false, quality: false, reconciliation: false, mes: false, live: false, daily: false })
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

  function dailyFactFallbackCard() {
    return {
      id: 'reporting:daily-fact-fallback',
      domain: 'reporting',
      occurredAt: `${targetDate.value}T23:59:55`,
      targetDate: targetDate.value,
      summary: '日报事实加载失败',
      detailRoute: '/manage/today?section=daily-report',
      traceId: '',
      status: null,
      isFallback: true,
    }
  }

  function load() {
    loading.value = true
    const my = ++token
    inflight = (async () => {
      const date = targetDate.value
      try {
        const [fd, q, r, m, live, daily] = await Promise.allSettled([
          fdImpl({ target_date: date }),
          qImpl({ business_date: date }),
          rImpl({ business_date: date, status: 'open' }),
          mImpl({ business_date: date }),
          liveImpl({ business_date: date }),
          dailyEnabled ? dailyImpl({ target_date: date }) : Promise.resolve(null),
        ])
        if (my !== token) return
        const buckets = []
        const fail = { factoryDirector: false, quality: false, reconciliation: false, mes: false, live: false, daily: false }
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
        if (m.status === 'fulfilled') {
          buckets.push(normalizeMesFillGaps(m.value, date))
        } else {
          fail.mes = true
          buckets.push([fallbackCard('mes')])
        }
        if (live.status === 'fulfilled') {
          buckets.push(normalizeLiveMissingReports(live.value, date))
        } else {
          fail.live = true
          buckets.push([fallbackCard('reporting')])
        }
        if (dailyEnabled) {
          if (daily.status === 'fulfilled') {
            buckets.push(normalizeDailyFactAlerts(daily.value, date))
          } else {
            fail.daily = true
            buckets.push([dailyFactFallbackCard()])
          }
        }
        endpointFailed.value = fail
        events.value = mergeAndSort(buckets)
        const fails = Object.values(fail).filter(Boolean).length
        lastError.value = fail.daily
          ? '日报事实加载失败'
          : (fails >= 2 ? '部分数据加载失败' : '')
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

  function setTraceId(next) {
    traceId.value = typeof next === 'string' ? next.trim() : ''
  }

  function stepDate(deltaDays) {
    targetDate.value = dayjs(targetDate.value).add(deltaDays, 'day').format('YYYY-MM-DD')
    return inflight
  }

  const domainCounts = computed(() => {
    const counts = { production: 0, reporting: 0, quality: 0, reconciliation: 0, mes: 0 }
    for (const e of events.value) {
      if (e.isFallback) continue
      if (counts[e.domain] != null) counts[e.domain] += 1
    }
    return counts
  })

  const filteredEvents = computed(() => {
    const traceFiltered = traceId.value
      ? events.value.filter((event) => event.traceId === traceId.value)
      : events.value
    if (!domains.value.length) return traceFiltered
    return traceFiltered.filter((e) => domains.value.includes(e.domain))
  })

  const freshnessStatus = computed(() => {
    const f = endpointFailed.value
    const fails = Object.values(f).filter(Boolean).length
    if (fails === 0) return 'green'
    if (fails >= 3) return 'red'
    return 'yellow'
  })

  return {
    targetDate, domains, traceId, events, filteredEvents, domainCounts,
    loading, lastError, freshnessStatus,
    load, stepDate, setDomains, setTraceId
  }
}

export function useAlertsTimeline() {
  return createAlertsTimeline()
}
