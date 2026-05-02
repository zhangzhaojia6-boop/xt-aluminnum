import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import dayjs from 'dayjs'
import { ElMessage } from 'element-plus'
import { fetchDeliveryStatus, fetchFactoryDashboard } from '../api/dashboard'
import { requestErrorMessage } from '../utils/reportStatus'

export function useFactoryDashboard(targetDate) {
  const loading = ref(false)
  const data = ref({})
  const delivery = ref({})
  const lastRefreshAt = ref('')
  const lastLoadErrorMessage = ref('')
  let refreshTimer = null

  const leaderMetrics = computed(() => data.value.leader_metrics || {})
  const historyDigest = computed(() => data.value.history_digest || {})
  const runtimeTrace = computed(() => data.value.runtime_trace || {})
  const dailySnapshots = computed(() => historyDigest.value.daily_snapshots || [])
  const monthArchive = computed(() => historyDigest.value.month_archive || {})
  const yearArchive = computed(() => historyDigest.value.year_archive || {})
  const monthToDateOutput = computed(() =>
    data.value.month_to_date_output ?? data.value.leader_metrics?.month_to_date_output ?? null
  )
  const lastRefreshLabel = computed(() =>
    lastRefreshAt.value ? dayjs(lastRefreshAt.value).format('HH:mm:ss') : '--:--:--'
  )
  const retentionSummary = computed(() =>
    `${monthArchive.value.reported_days ?? 0} 天归档`
  )

  async function load() {
    loading.value = true
    try {
      const [dashboardPayload, deliveryPayload] = await Promise.all([
        fetchFactoryDashboard({ target_date: targetDate.value }),
        fetchDeliveryStatus({ target_date: targetDate.value })
      ])
      data.value = dashboardPayload
      delivery.value = deliveryPayload
      lastRefreshAt.value = new Date().toISOString()
      lastLoadErrorMessage.value = ''
    } catch (error) {
      const message = requestErrorMessage(error, '数据加载失败，请稍后重试')
      if (message !== lastLoadErrorMessage.value) {
        ElMessage.error(message)
        lastLoadErrorMessage.value = message
      }
    } finally {
      loading.value = false
    }
  }

  watch(targetDate, () => load())

  onMounted(() => {
    load()
    refreshTimer = setInterval(load, 30000)
  })

  onUnmounted(() => {
    if (refreshTimer) {
      clearInterval(refreshTimer)
      refreshTimer = null
    }
  })

  return {
    loading, data, delivery, lastRefreshAt,
    leaderMetrics, historyDigest, runtimeTrace,
    dailySnapshots, monthArchive, yearArchive,
    monthToDateOutput, lastRefreshLabel, retentionSummary,
    load
  }
}
