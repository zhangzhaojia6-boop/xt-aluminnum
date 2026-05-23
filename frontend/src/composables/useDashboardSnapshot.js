import { ref, computed, watch } from 'vue'
import dayjs from 'dayjs'
import { fetchFactoryDashboard } from '../api/dashboard.js'
import { requestErrorMessage } from '../utils/reportStatus.js'

export function createDashboardSnapshot({ fetchImpl = fetchFactoryDashboard, now = new Date() } = {}) {
  const yesterday = dayjs(now).subtract(1, 'day').format('YYYY-MM-DD')
  const targetDate = ref(yesterday)
  const data = ref({})
  const loading = ref(false)
  const lastError = ref('')
  const lastRefreshAt = ref('')
  let inflight = Promise.resolve()

  function load() {
    loading.value = true
    inflight = (async () => {
      try {
        data.value = await fetchImpl({ target_date: targetDate.value })
        lastRefreshAt.value = new Date().toISOString()
        lastError.value = ''
      } catch (err) {
        lastError.value = requestErrorMessage(err, '数据加载失败，请稍后重试')
      } finally {
        loading.value = false
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
    leaderMetrics: computed(() => data.value.leader_metrics || {}),
    monthArchive: computed(() => data.value.history_digest?.month_archive || {}),
    trend: computed(() => data.value.analysis_handoff?.trend || {}),
    managementEstimate: computed(() => data.value.management_estimate || {}),
    productionLane: computed(() => data.value.production_lane || []),
    exceptionLane: computed(() => data.value.exception_lane || {}),
    leaderSummary: computed(() => data.value.leader_summary || {}),
    freshnessStatus: computed(() => data.value.analysis_handoff?.freshness?.freshness_status || null),
    load, stepDate
  }
}

export function useDashboardSnapshot() {
  return createDashboardSnapshot()
}
