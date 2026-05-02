export function numberValue(value, fallback = 0) {
  if (value === null || value === undefined || value === '') return fallback
  const number = Number(value)
  return Number.isFinite(number) ? number : fallback
}

function rounded(value, digits = 2) {
  if (value === null || value === undefined) return null
  const number = Number(value)
  if (!Number.isFinite(number)) return null
  return Number(number.toFixed(digits))
}

function countMissingCells(aggregation) {
  const progress = aggregation?.overall_progress || {}
  if (progress.missing_cell_count !== undefined) return numberValue(progress.missing_cell_count, 0)
  const total = numberValue(progress.total_cells, 0)
  const submitted = numberValue(progress.submitted_cells, 0)
  return Math.max(total - submitted, 0)
}

export function marginTone(value) {
  if (value === null || value === undefined) return 'muted'
  const number = Number(value)
  if (!Number.isFinite(number)) return 'muted'
  if (number > 0) return 'success'
  if (number < 0) return 'danger'
  return 'neutral'
}

export function buildManagementOverview({ aggregation = {}, dashboard = {}, delivery = {} } = {}) {
  const factoryTotal = aggregation.factory_total || {}
  const leaderMetrics = dashboard.leader_metrics || {}
  const estimate = dashboard.management_estimate || {}
  const exceptionLane = dashboard.exception_lane || {}
  const progress = aggregation.overall_progress || {}

  const inputWeight = numberValue(factoryTotal.input, null)
  const outputWeight = numberValue(
    factoryTotal.output,
    numberValue(leaderMetrics.today_total_output, 0)
  )
  const lossWeight = numberValue(factoryTotal.scrap, 0)
  const lossRate = inputWeight && inputWeight > 0
    ? rounded((lossWeight / inputWeight) * 100)
    : null
  const yieldRate = rounded(numberValue(factoryTotal.yield_rate, numberValue(leaderMetrics.yield_rate, null)))

  const estimateReady = estimate.estimate_ready === true
  const estimatedRevenue = estimateReady ? rounded(numberValue(estimate.estimated_revenue, null)) : null
  const estimatedCost = estimateReady ? rounded(numberValue(estimate.estimated_cost, null)) : null
  const estimatedMargin = estimateReady ? rounded(numberValue(estimate.estimated_margin, null)) : null

  const missingCells = countMissingCells(aggregation)
  const attentionCells = numberValue(progress.attention_cell_count, 0)
  const returnedShifts = numberValue(exceptionLane.returned_shift_count, 0)
  const mobileExceptions = numberValue(exceptionLane.mobile_exception_count, 0)
  const productionExceptions = numberValue(exceptionLane.production_exception_count, 0)
  const lateReminders = numberValue(exceptionLane.reminder_late_count, 0)
  const reconciliationOpen = numberValue(exceptionLane.reconciliation_open_count, 0)
  const pendingPublish = numberValue(exceptionLane.pending_report_publish_count, 0)
  const deliveryReady = Boolean(delivery.delivery_ready ?? dashboard.delivery_ready)
  const anomalyCount = returnedShifts + mobileExceptions + productionExceptions + lateReminders + reconciliationOpen
  const deliveryBlocker = deliveryReady ? 0 : 1
  const blockerBreakdown = {
    missingCells,
    attentionCells,
    anomalyCount,
    deliveryBlocker,
    pendingPublish,
  }
  const blockerCount = missingCells + anomalyCount + deliveryBlocker + pendingPublish

  return {
    inputWeight,
    outputWeight,
    lossWeight,
    lossRate,
    yieldRate,
    estimatedRevenue,
    estimatedCost,
    estimatedMargin,
    estimateReady,
    marginLabel: estimateReady ? (estimatedMargin >= 0 ? '毛利估算' : '亏损估算') : '待配置',
    missingCells,
    attentionCells,
    deliveryReady,
    storageFinishedWeight: rounded(numberValue(leaderMetrics.storage_finished_weight, 0)),
    shipmentWeight: rounded(numberValue(leaderMetrics.shipment_weight, 0)),
    blockerBreakdown,
    blockerCount,
    deliveryMissingSteps: delivery.missing_steps || dashboard.delivery_status?.missing_steps || [],
  }
}
