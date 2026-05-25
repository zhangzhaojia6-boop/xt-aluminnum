import { ref, computed, watch } from 'vue'
import dayjs from 'dayjs'
import { fetchFactoryDashboard } from '../api/dashboard.js'
import { requestErrorMessage } from '../utils/reportStatus.js'

const FRESHNESS_MAP = { fresh: 'green', stale: 'yellow', missing: 'red' }
function normalizeFreshness(raw) {
  if (!raw) return null
  if (raw === 'green' || raw === 'yellow' || raw === 'red') return raw
  return FRESHNESS_MAP[raw] || null
}

export function createDashboardSnapshot({ fetchImpl = fetchFactoryDashboard, now = new Date() } = {}) {
  const yesterday = dayjs(now).subtract(1, 'day').format('YYYY-MM-DD')
  const targetDate = ref(yesterday)
  const data = ref({})
  const loading = ref(false)
  const lastError = ref('')
  const lastRefreshAt = ref('')
  let token = 0
  let inflight = Promise.resolve()

  function load() {
    loading.value = true
    const my = ++token
    inflight = (async () => {
      try {
        const next = await fetchImpl({ target_date: targetDate.value })
        if (my !== token) return
        data.value = next
        lastRefreshAt.value = new Date().toISOString()
        lastError.value = ''
      } catch (err) {
        if (my !== token) return
        lastError.value = requestErrorMessage(err, '数据加载失败，请稍后重试')
      } finally {
        if (my === token) loading.value = false
      }
    })()
    return inflight
  }

  watch(targetDate, () => load(), { flush: 'sync' })

  function stepDate(deltaDays) {
    targetDate.value = dayjs(targetDate.value).add(deltaDays, 'day').format('YYYY-MM-DD')
    return inflight
  }

  return {
    targetDate, data, loading, lastError, lastRefreshAt,
    leaderMetrics: computed(() => {
      const lm = data.value.leader_metrics || {}
      const sm = data.value.leader_summary?.metrics || {}
      return {
        ...lm,
        total_output_weight: lm.total_output_weight ?? lm.today_total_output ?? sm.total_output_weight ?? null,
        energy_per_ton: lm.energy_per_ton ?? sm.energy_per_ton ?? null,
        yield_rate: lm.yield_rate ?? sm.yield_rate ?? null,
        reporting_rate: lm.reporting_rate ?? sm.reporting_rate ?? null,
        anomaly_total: lm.anomaly_total ?? sm.anomaly_total ?? 0
      }
    }),
    monthArchive: computed(() => data.value.history_digest?.month_archive || {}),
    trend: computed(() => data.value.analysis_handoff?.trend || {}),
    managementEstimate: computed(() => data.value.management_estimate || {}),
    productionLane: computed(() => data.value.production_lane || []),
    exceptionLane: computed(() => data.value.exception_lane || {}),
    leaderSummary: computed(() => data.value.leader_summary || {}),
    freshnessStatus: computed(() => normalizeFreshness(data.value.analysis_handoff?.freshness?.freshness_status)),
    load, stepDate
  }
}

export function useDashboardSnapshot() {
  return createDashboardSnapshot()
}
