function numberValue(value) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : 0
}

function flattenCells(workshops = []) {
  return workshops.flatMap((workshop) =>
    (workshop.machines || []).flatMap((machine) => machine.shifts || [])
  )
}

export function statusToneForCell(cell = {}) {
  if (cell.status_tone) return cell.status_tone
  if (!cell.is_applicable || cell.submission_status === 'not_applicable') return 'muted'
  if (numberValue(cell.attendance_exception_count) > 0) return 'danger'
  if (cell.submission_status === 'not_started') return 'danger'
  if (cell.submission_status === 'in_progress') return 'warning'
  if (cell.attendance_status === 'pending') return 'warning'
  if (cell.submission_status === 'all_submitted') return 'success'
  return 'muted'
}

export function statusTextForCell(cell = {}) {
  if (cell.status_text) return cell.status_text
  if (!cell.is_applicable || cell.submission_status === 'not_applicable') return '不适用'
  if (numberValue(cell.attendance_exception_count) > 0) return '考勤异常'
  if (cell.submission_status === 'not_started') return '缺报'
  if (cell.submission_status === 'in_progress') return '进行中'
  if (cell.attendance_status === 'pending') return '考勤待确认'
  if (cell.submission_status === 'all_submitted') return '已填'
  return '未开始'
}

export function isAttentionCell(cell = {}) {
  return ['danger', 'warning'].includes(statusToneForCell(cell))
}

export function workshopAttentionCount(workshop = {}) {
  return flattenCells([workshop]).filter((cell) => cell.is_applicable !== false && isAttentionCell(cell)).length
}

export function sortWorkshopsForCommandCenter(workshops = []) {
  return [...workshops].sort((left, right) => {
    const attentionDiff = workshopAttentionCount(right) - workshopAttentionCount(left)
    if (attentionDiff !== 0) return attentionDiff
    return numberValue(left.sort_order ?? left.workshop_id) - numberValue(right.sort_order ?? right.workshop_id)
  })
}

export function dataSourceLabel(dataSource) {
  if (dataSource === 'mes_projection') return 'MES 投影'
  if (dataSource === 'work_order_compat' || dataSource === 'work_order_runtime') return '工单兼容口径'
  return '未知来源'
}

export function formatSyncLag(seconds) {
  const lag = Number(seconds)
  if (!Number.isFinite(lag)) return '--'
  if (lag < 60) return `${lag.toFixed(0)}s`
  return `${(lag / 60).toFixed(1)}m`
}

export function buildCommandCenterSummary(aggregation = {}) {
  const progress = aggregation.overall_progress || {}
  const cells = flattenCells(aggregation.workshops || []).filter((cell) => cell.is_applicable !== false)
  const submittedCells = numberValue(progress.submitted_cells)
  const totalCells = numberValue(progress.total_cells)
  const fallbackMissing = cells.filter((cell) => cell.submission_status === 'not_started').length
  const fallbackAttention = cells.filter(isAttentionCell).length
  const completionRate = progress.completion_rate ?? (totalCells ? (submittedCells / totalCells) * 100 : 0)

  return {
    submittedCells,
    totalCells,
    missingCellCount: numberValue(progress.missing_cell_count ?? fallbackMissing),
    attentionCellCount: numberValue(progress.attention_cell_count ?? fallbackAttention),
    completionRate: Number(Number(completionRate).toFixed(2)),
    todayOutput: numberValue(aggregation.factory_total?.output),
    yieldRate: aggregation.factory_total?.yield_rate ?? null,
    dataSourceLabel: dataSourceLabel(aggregation.data_source),
    syncLagLabel: formatSyncLag(aggregation.mes_sync_status?.lag_seconds),
  }
}
