import { COST_PRICE_MASTER_TABLE, buildPriceRows, resolvePriceSnapshot } from './priceResolver'
import { runCastingMachineLaborSplit } from './strategies/castingMachineLaborSplit'
import { runFinishingParallelProcess } from './strategies/finishingParallelProcess'
import { runHotRollingShiftDaily } from './strategies/hotRollingShiftDaily'
import { runLossDualCaliber } from './strategies/lossDualCaliber'
import { runTensionLevelingMainPlusAux } from './strategies/tensionLevelingMainPlusAux'

export const COST_STRATEGIES = {
  CASTING_MACHINE_LABOR_SPLIT: 'CASTING_MACHINE_LABOR_SPLIT',
  FINISHING_PARALLEL_PROCESS: 'FINISHING_PARALLEL_PROCESS',
  HOT_ROLLING_SHIFT_DAILY: 'HOT_ROLLING_SHIFT_DAILY',
  TENSION_LEVELING_MAIN_PLUS_AUX: 'TENSION_LEVELING_MAIN_PLUS_AUX',
  LOSS_DUAL_CALIBER: 'LOSS_DUAL_CALIBER'
}

const strategyRunners = {
  [COST_STRATEGIES.CASTING_MACHINE_LABOR_SPLIT]: runCastingMachineLaborSplit,
  [COST_STRATEGIES.FINISHING_PARALLEL_PROCESS]: runFinishingParallelProcess,
  [COST_STRATEGIES.HOT_ROLLING_SHIFT_DAILY]: runHotRollingShiftDaily,
  [COST_STRATEGIES.TENSION_LEVELING_MAIN_PLUS_AUX]: runTensionLevelingMainPlusAux,
  [COST_STRATEGIES.LOSS_DUAL_CALIBER]: runLossDualCaliber
}

export const COST_TABLE_KEYS = {
  PRICE_MASTER: COST_PRICE_MASTER_TABLE,
  WORKSHOP_STRATEGY: 'cost_workshop_strategy',
  DAILY_RESULT: 'cost_daily_result',
  MONTHLY_ROLLUP: 'cost_monthly_rollup',
  VARIANCE_RECORD: 'cost_variance_record'
}

function buildWorkshopStrategyRecord(payload) {
  return {
    table: COST_TABLE_KEYS.WORKSHOP_STRATEGY,
    workshop_code: payload?.workshopCode || '',
    strategy_code: payload?.strategyCode || '',
    enabled: true,
    effective_from: payload?.businessDate || '',
    caliber: payload?.caliber || 'output',
    config_snapshot: {
      outputTon: payload?.outputTon,
      throughputTon: payload?.throughputTon,
      processCount: Array.isArray(payload?.processes) ? payload.processes.length : undefined,
      shiftCount: Array.isArray(payload?.shifts) ? payload.shifts.length : undefined
    }
  }
}

function buildDailyResultRecord(payload, result) {
  return {
    table: COST_TABLE_KEYS.DAILY_RESULT,
    business_date: payload?.businessDate || '',
    workshop_code: payload?.workshopCode || '',
    strategy_code: payload?.strategyCode || '',
    total_cost: Number(result.totalCost || 0),
    output_ton_cost: Number(result.byOutputTon || 0),
    throughput_ton_cost: Number(result.byThroughputTon || 0),
    caliber: payload?.caliber || 'output',
    breakdown_count: Array.isArray(result.breakdown) ? result.breakdown.length : 0,
    process_count: Array.isArray(result.processRows) ? result.processRows.length : 0
  }
}

function buildMonthlyRollupRecord(payload, result) {
  const businessDate = String(payload?.businessDate || '')
  return {
    table: COST_TABLE_KEYS.MONTHLY_ROLLUP,
    month: businessDate.slice(0, 7),
    workshop_code: payload?.workshopCode || '',
    strategy_code: payload?.strategyCode || '',
    month_total_cost: Number(result.totalCost || 0),
    month_output_ton_cost: Number(result.byOutputTon || 0),
    month_throughput_ton_cost: Number(result.byThroughputTon || 0),
    source: 'frontend_strategy_snapshot'
  }
}

function buildVarianceRecords(payload, result) {
  const rows = []
  const output = Number(result.byOutputTon || 0)
  const throughput = Number(result.byThroughputTon || 0)
  if (output > 0 && throughput > 0) {
    rows.push({
      table: COST_TABLE_KEYS.VARIANCE_RECORD,
      business_date: payload?.businessDate || '',
      workshop_code: payload?.workshopCode || '',
      variance_type: 'OUTPUT_VS_THROUGHPUT',
      baseline_value: throughput,
      current_value: output,
      diff_value: Number((output - throughput).toFixed(2)),
      status: Math.abs(output - throughput) > 30 ? 'watch' : 'normal'
    })
  }
  return rows
}

export function evaluateCostScenario(payload) {
  const strategyCode = String(payload?.strategyCode || '').trim()
  const runner = strategyRunners[strategyCode]
  if (!runner) {
    throw new Error(`未知成本策略: ${strategyCode}`)
  }

  const priceSnapshot = resolvePriceSnapshot(payload?.priceOverrides || [])
  const result = runner(payload || {}, priceSnapshot)
  const priceRows = buildPriceRows(priceSnapshot)
  const enrichedPayload = {
    ...(payload || {}),
    strategyCode
  }
  const dailyResult = buildDailyResultRecord(enrichedPayload, result)
  const monthlyRollup = buildMonthlyRollupRecord(enrichedPayload, result)
  const varianceRecords = buildVarianceRecords(enrichedPayload, result)
  return {
    ...result,
    strategyCode,
    workshopCode: payload?.workshopCode || '',
    businessDate: payload?.businessDate || '',
    caliber: payload?.caliber || 'output',
    priceRows,
    tableModels: {
      [COST_TABLE_KEYS.PRICE_MASTER]: priceRows,
      [COST_TABLE_KEYS.WORKSHOP_STRATEGY]: [buildWorkshopStrategyRecord(enrichedPayload)],
      [COST_TABLE_KEYS.DAILY_RESULT]: [dailyResult],
      [COST_TABLE_KEYS.MONTHLY_ROLLUP]: [monthlyRollup],
      [COST_TABLE_KEYS.VARIANCE_RECORD]: varianceRecords
    },
    dailyResult,
    monthlyRollup,
    varianceRecords
  }
}
