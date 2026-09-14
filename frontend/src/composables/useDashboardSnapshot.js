import { ref, computed, watch } from 'vue'
import dayjs from 'dayjs'
import { fetchFactoryDashboard } from '../api/dashboard.js'
import { fetchDailyProduction } from '../api/dashboard.js'
import { fetchFactoryCommandOverview } from '../api/factory-command.js'
import { requestErrorMessage } from '../utils/reportStatus.js'
import { inferLastCompletedBusinessDate } from '../utils/shiftClock.js'

const FRESHNESS_MAP = { fresh: 'green', stale: 'yellow', missing: 'red' }
function normalizeFreshness(raw) {
  if (!raw) return null
  if (raw === 'green' || raw === 'yellow' || raw === 'red') return raw
  return FRESHNESS_MAP[raw] || null
}

export function createDashboardSnapshot({
  fetchImpl = fetchFactoryDashboard,
  fetchDailyImpl = fetchDailyProduction,
  fetchFactoryCommandImpl = fetchFactoryCommandOverview,
  now = new Date()
} = {}) {
  const targetDate = ref(inferLastCompletedBusinessDate(now))
  const data = ref({})
  const loading = ref(false)
  const sourceErrors = ref({})
  const dailyRefreshError = ref('')
  const lastRefreshAt = ref('')
  const pending = ref({ factory: false, daily: false, command: false })
  let token = 0
  let inflight = Promise.resolve()

  function load() {
    loading.value = true
    const my = ++token
    const params = { target_date: targetDate.value }
    const results = { factory: {}, daily: {}, command: {} }
    const errors = {}
    data.value = {}
    sourceErrors.value = {}
    dailyRefreshError.value = ''
    lastRefreshAt.value = ''
    pending.value = { factory: true, daily: true, command: true }
    // Publish each source independently; a stale request must never change this date's view.
    async function receive(key, fetcher, label) {
      try {
        const value = await fetcher(params)
        if (my !== token) return
        results[key] = value || {}
      } catch (err) {
        if (my !== token) return
        errors[key] = `${label}：${requestErrorMessage(err, '加载失败，请重试')}`
      } finally {
        if (my === token) {
          data.value = {
            ...results.factory,
            daily_overview: results.daily,
            factory_command_overview: results.command,
          }
          pending.value = { ...pending.value, [key]: false }
          sourceErrors.value = { ...errors }
          lastRefreshAt.value = new Date().toISOString()
        }
      }
    }
    inflight = receive('daily', fetchDailyImpl, '日报').then(() => {
      if (my !== token) return
      return Promise.all([
        receive('factory', fetchImpl, '经营摘要'),
        receive('command', fetchFactoryCommandImpl, '生产概览'),
      ])
    }).finally(() => {
      if (my === token) loading.value = false
    })
    return inflight
  }

  watch(targetDate, () => load(), { flush: 'sync' })

  async function refreshDaily() {
    if (loading.value || pending.value.daily) return
    const my = token
    pending.value = { ...pending.value, daily: true }
    try {
      const daily = await fetchDailyImpl({ target_date: targetDate.value })
      if (my !== token) return
      data.value = { ...data.value, daily_overview: daily || {} }
      delete sourceErrors.value.daily
      dailyRefreshError.value = ''
      lastRefreshAt.value = new Date().toISOString()
    } catch (err) {
      if (my === token) dailyRefreshError.value = `日报更新失败：${requestErrorMessage(err, '请重试')}`
    } finally {
      if (my === token) pending.value = { ...pending.value, daily: false }
    }
  }

  function stepDate(deltaDays) {
    targetDate.value = dayjs(targetDate.value).add(deltaDays, 'day').format('YYYY-MM-DD')
    return inflight
  }

  return {
    targetDate, data, loading, pending, lastRefreshAt,
    lastError: computed(() => [...Object.values(sourceErrors.value), dailyRefreshError.value].filter(Boolean).join('；')),
    factoryCommandOverview: computed(() => data.value.factory_command_overview || {}),
    leaderMetrics: computed(() => {
      const dailyOverview = data.value.daily_overview || {}
      const plantOutput = dailyOverview.plant_output || {}
      const dailyEnergy = dailyOverview.energy || {}
      const factoryCommand = data.value.factory_command_overview || {}
      const lm = data.value.leader_metrics || {}
      const sm = data.value.leader_summary?.metrics || {}
      const totalOutput = plantOutput.daily_output ?? lm.total_output_weight ?? lm.today_total_output ?? sm.total_output_weight ?? null
      const finishedInboundOutput = plantOutput.finished_inbound_output ?? lm.storage_finished_weight ?? sm.storage_finished_weight ?? null
      const energyPerTon = dailyEnergy.data_available === false
        ? null
        : plantOutput.energy_per_ton ?? lm.energy_per_ton ?? sm.energy_per_ton ?? null
      return {
        ...lm,
        total_output_weight: totalOutput,
        today_total_output: totalOutput,
        storage_finished_weight: finishedInboundOutput,
        energy_per_ton: energyPerTon,
        yield_rate: lm.yield_rate ?? sm.yield_rate ?? factoryCommand.yield_rate ?? null,
        reporting_rate: lm.reporting_rate ?? sm.reporting_rate ?? null,
        anomaly_total: lm.anomaly_total ?? sm.anomaly_total ?? 0
      }
    }),
    monthArchive: computed(() => {
      const archive = data.value.history_digest?.month_archive || {}
      const plantOutput = data.value.daily_overview?.plant_output || {}
      return {
        ...archive,
        total_output: plantOutput.monthly_output ?? archive.total_output ?? null
      }
    }),
    trend: computed(() => {
      const trend = data.value.analysis_handoff?.trend || {}
      const plantOutput = data.value.daily_overview?.plant_output || {}
      if (plantOutput.daily_output == null) return trend
      const currentOutput = Number(plantOutput.daily_output)
      const yesterdayOutput = plantOutput.yesterday_output == null ? null : Number(plantOutput.yesterday_output)
      return {
        ...trend,
        current_output: currentOutput,
        output_delta_vs_yesterday: yesterdayOutput == null ? trend.output_delta_vs_yesterday : currentOutput - yesterdayOutput
      }
    }),
    managementEstimate: computed(() => {
      const estimate = data.value.management_estimate || {}
      const dailyOverview = data.value.daily_overview || {}
      const plantOutput = dailyOverview.plant_output || {}
      const plantCost = dailyOverview.plant_cost || {}
      return {
        ...estimate,
        estimate_ready: plantCost.cost_per_ton != null ? true : estimate.estimate_ready,
        estimated_cost: plantCost.total != null ? Number(plantCost.total) * 10000 : estimate.estimated_cost,
        total_output_weight: plantOutput.daily_output ?? estimate.total_output_weight ?? null,
        output_tons: plantOutput.daily_output ?? estimate.output_tons ?? null,
        cost_basis_label: plantOutput.basis_label || estimate.cost_basis_label || null
      }
    }),
    productionLane: computed(() => {
      const dailyRows = data.value.daily_overview?.workshop_output || []
      if (dailyRows.length) {
        const dayOfMonth = Math.max(dayjs(targetDate.value).date(), 1)
        return dailyRows.map((row) => ({
          workshop_id: row.workshop_id,
          workshop_name: row.workshop,
          total_output: row.daily_output,
          delta_vs_yesterday: row.delta,
          target_value: row.monthly_output != null ? Number(row.monthly_output) / dayOfMonth : null
        }))
      }
      return data.value.production_lane || []
    }),
    yesterdayShiftBreakdown: computed(() => {
      const dailyBreakdown = data.value.daily_overview?.shift_breakdown
      const plantOutput = data.value.daily_overview?.plant_output || {}
      if (dailyBreakdown && Array.isArray(dailyBreakdown.shifts)) {
        return {
          ...dailyBreakdown,
          total_output: plantOutput.daily_output ?? dailyBreakdown.total_output,
          output_basis: plantOutput.basis || dailyBreakdown.output_basis,
          output_basis_label: plantOutput.basis_label || dailyBreakdown.output_basis_label || '包装产量'
        }
      }
      const breakdown = data.value.yesterday_shift_breakdown || { shifts: [] }
      if (plantOutput.daily_output == null) return breakdown
      return {
        ...breakdown,
        total_output: plantOutput.daily_output,
        output_basis: plantOutput.basis || breakdown.output_basis,
        output_basis_label: plantOutput.basis_label || breakdown.output_basis_label || '包装产量'
      }
    }),
    exceptionLane: computed(() => data.value.exception_lane || {}),
    leaderSummary: computed(() => data.value.leader_summary || {}),
    freshnessStatus: computed(() => normalizeFreshness(data.value.analysis_handoff?.freshness?.freshness_status)),
    load, stepDate, refreshDaily
  }
}

export function useDashboardSnapshot() {
  return createDashboardSnapshot()
}
