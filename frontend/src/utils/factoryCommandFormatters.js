const freshnessLabels = {
  fresh: '实时',
  stale: '滞后',
  offline_or_blocked: '离线/阻塞'
}

const sourceLabels = {
  mes_projection: 'MES 投影',
  local_entry: '本地填报',
  mixed: '混合来源'
}

const destinationLabels = {
  in_progress: '在制',
  finished_stock: '成品库存',
  allocation: '已分配',
  delivery: '交付',
  unknown: '未知'
}

function toNumber(value, fallback = 0) {
  const number = Number(value)
  return Number.isFinite(number) ? number : fallback
}

function roundTons(value) {
  return Math.round(toNumber(value) * 100) / 100
}

export function freshnessLabel(status) {
  return freshnessLabels[status] || '未知'
}

export function sourceLabel(source) {
  return sourceLabels[source] || '未知来源'
}

export function destinationGroupLabel(kind) {
  return destinationLabels[kind] || destinationLabels.unknown
}

export function formatMachineLineMetric(row = {}) {
  const costEstimate = row.cost_estimate || row.costEstimate || {}
  const marginEstimate = row.margin_estimate || row.marginEstimate || {}
  return {
    lineCode: row.line_code || row.lineCode || '',
    lineName: row.line_name || row.lineName || '',
    workshopName: row.workshop_name || row.workshopName || '',
    activeCoilCount: toNumber(row.active_coil_count ?? row.activeCoilCount),
    activeTons: roundTons(row.active_tons ?? row.activeTons),
    finishedTons: roundTons(row.finished_tons ?? row.finishedTons),
    stalledCount: toNumber(row.stalled_count ?? row.stalledCount),
    estimatedCost: costEstimate.estimated_cost ?? costEstimate.estimatedCost ?? null,
    estimatedGrossMargin: marginEstimate.estimated_gross_margin ?? marginEstimate.estimatedGrossMargin ?? null,
    missingCostData: costEstimate.missing_data || costEstimate.missingData || []
  }
}

export function formatDestination(row = {}) {
  const kind = row.kind || row.destination?.kind || 'unknown'
  return {
    kind,
    label: row.label || destinationGroupLabel(kind),
    coilCount: toNumber(row.coil_count ?? row.coilCount),
    tons: roundTons(row.tons),
    freshness: row.freshness || null
  }
}
