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

const ruleLabels = {
  route_missing: '路线缺失',
  delay_hours_high: '停滞超时',
  sync_stale: '同步滞后',
  weight_anomaly: '重量异常',
  destination_unknown: '去向未知',
  cost_estimate_missing: '经营口径缺失',
  machine_line_cost_spike: '机列成本波动'
}

const missingDataLabels = {
  cost_inputs: '成本系数未配置',
  energy: '能耗数据缺失',
  labor: '人工口径缺失',
  material_loss: '损耗口径缺失',
  mes_stale: 'MES 同步滞后',
  route: '工艺路线缺失'
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

export function formatRuleLabel(key) {
  return ruleLabels[key] || '待核实异常'
}

export function formatMissingDataLabel(key) {
  return missingDataLabels[key] || String(key || '缺少数据')
}

export function formatLagLabel(value) {
  if (value === null || value === undefined || value === '') return '未同步'
  const seconds = toNumber(value, null)
  if (seconds === null) return '未同步'
  if (seconds < 60) return `滞后 ${Math.round(seconds)} 秒`
  return `滞后 ${Math.round(seconds / 60)} 分钟`
}

export function formatSyncTime(value) {
  if (!value) return '--'
  const matched = String(value).match(/^(\d{4})-(\d{2})-(\d{2})[T\s](\d{2}):(\d{2})/)
  if (matched) return `${matched[2]}-${matched[3]} ${matched[4]}:${matched[5]}`
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return String(value)
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  const hour = String(date.getHours()).padStart(2, '0')
  const minute = String(date.getMinutes()).padStart(2, '0')
  return `${month}-${day} ${hour}:${minute}`
}

export function formatLineDisplay(row = {}) {
  const lineName = row.line_name || row.lineName
  const workshopName = row.workshop_name || row.workshopName
  const lineCode = row.line_code || row.lineCode
  return {
    title: lineName || (workshopName ? `${workshopName} 机列` : '未识别机列'),
    meta: workshopName || '未识别车间',
    code: lineCode || ''
  }
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
