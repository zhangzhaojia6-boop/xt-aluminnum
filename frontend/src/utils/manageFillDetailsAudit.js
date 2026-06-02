import { formatShiftLabel } from './display.js'

export const MISSING_AUDIT_VALUE = '暂无可信数据'

const REMOVED_WORKSHOP_NAMES = new Set(['冷轧三车间', '二分厂精整车间'])

function toNumber(value) {
  if (value === null || value === undefined || value === '') return null
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}

function formatNumber(value, digits = 2) {
  const numeric = toNumber(value)
  if (numeric === null) return MISSING_AUDIT_VALUE
  return numeric.toLocaleString('zh-CN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  })
}

function formatMetric(value, unit = '', digits = 2) {
  const text = formatNumber(value, digits)
  if (text === MISSING_AUDIT_VALUE) return text
  return unit ? `${text} ${unit}` : text
}

function isRemovedWorkshop(row = {}) {
  const name = String(row.workshop || row.workshop_name || row.workshopName || '').trim()
  const status = String(row.status || row.workshop_status || '').toLowerCase()
  return row.is_active === false
    || row.is_removed === true
    || row.removed === true
    || status === 'removed'
    || REMOVED_WORKSHOP_NAMES.has(name)
}

function activeWorkshopRows(rows = []) {
  return (rows || []).filter((row) => !isRemovedWorkshop(row))
}

function sumWorkshopOutput(rows = []) {
  const activeRows = activeWorkshopRows(rows)
  if (!activeRows.length) return null
  return activeRows.reduce((sum, row) => sum + (toNumber(row.daily_output) || 0), 0)
}

function hasEnergyData(energy = {}) {
  if (energy.data_available === false) return false
  return toNumber(energy.total_electricity) !== null
    || toNumber(energy.total_energy) !== null
    || toNumber(energy.energy_per_ton) !== null
}

function mesSyncText(status = {}) {
  const state = String(status.status || status.sync_status || '').toLowerCase()
  if (state.includes('recover')) return '同步恢复中'
  if (state.includes('fail') || state.includes('error')) return '同步异常'
  if (state.includes('fresh') || state.includes('success') || state.includes('ok')) return '同步正常'
  if (toNumber(status.lag_seconds) !== null) return `${Math.round(Number(status.lag_seconds))} 秒`
  return MISSING_AUDIT_VALUE
}

function toneByMissing(value, preferred = 'primary') {
  return value === MISSING_AUDIT_VALUE ? 'muted' : preferred
}

export function buildAuditTickerItems({ dailyOverview = {}, liveAggregation = {} } = {}) {
  const plantOutput = dailyOverview.plant_output || {}
  const energy = dailyOverview.energy || {}
  const contracts = dailyOverview.contracts || {}
  const processThroughput = sumWorkshopOutput(dailyOverview.workshop_output || [])
  const algorithmEnergy = hasEnergyData(energy) ? formatMetric(energy.total_electricity, '度') : MISSING_AUDIT_VALUE
  const ownerEnergy = formatMetric(energy.owner_electricity, '度')

  return [
    {
      key: 'plant-output',
      label: '全厂入库产量',
      value: formatMetric(plantOutput.daily_output, '吨'),
      tone: toneByMissing(formatMetric(plantOutput.daily_output, '吨'), 'success'),
    },
    {
      key: 'process-throughput',
      label: '过站下机参考',
      value: formatMetric(processThroughput, '吨'),
      tone: processThroughput === null ? 'muted' : 'primary',
    },
    {
      key: 'algorithm-energy',
      label: '算法总用电',
      value: algorithmEnergy,
      tone: toneByMissing(algorithmEnergy, 'warning'),
    },
    {
      key: 'owner-energy',
      label: '电工填报',
      value: ownerEnergy,
      tone: toneByMissing(ownerEnergy, 'warning'),
    },
    {
      key: 'contract-tonnage',
      label: '合同吨数',
      value: formatMetric(contracts.daily_new, contracts.unit || '吨'),
      tone: toneByMissing(formatMetric(contracts.daily_new, contracts.unit || '吨'), 'primary'),
    },
    {
      key: 'mes-sync',
      label: '外部 MES',
      value: mesSyncText(liveAggregation.mes_sync_status || {}),
      tone: 'primary',
    },
  ]
}

export function buildSourceChainCards(dailyOverview = {}) {
  const plantOutput = dailyOverview.plant_output || {}
  const energy = dailyOverview.energy || {}
  const contracts = dailyOverview.contracts || {}
  const yieldRates = dailyOverview.yield_rates || {}
  const processThroughput = sumWorkshopOutput(dailyOverview.workshop_output || [])
  const algorithmEnergy = hasEnergyData(energy) ? formatMetric(energy.total_electricity, '度') : MISSING_AUDIT_VALUE

  return [
    {
      key: 'output',
      title: '全厂最终产量',
      primaryLabel: '入库产量',
      primaryValue: formatMetric(plantOutput.daily_output, '吨'),
      compareLabel: '过站下机参考',
      compareValue: formatMetric(processThroughput, '吨'),
      tone: 'success',
    },
    {
      key: 'energy',
      title: '总用电',
      primaryLabel: '算法总用电',
      primaryValue: algorithmEnergy,
      compareLabel: '电工填报',
      compareValue: formatMetric(energy.owner_electricity, '度'),
      tone: toneByMissing(algorithmEnergy, 'warning'),
    },
    {
      key: 'yield',
      title: '成品率',
      primaryLabel: '算法成品率',
      primaryValue: formatMetric(yieldRates.daily, '%'),
      compareLabel: '内勤填报',
      compareValue: formatMetric(yieldRates.owner_daily, '%'),
      tone: toneByMissing(formatMetric(yieldRates.daily, '%'), 'primary'),
    },
    {
      key: 'contract',
      title: '合同量',
      primaryLabel: '当天接合同',
      primaryValue: formatMetric(contracts.daily_new, contracts.unit || '吨'),
      compareLabel: '总余合同量',
      compareValue: formatMetric(contracts.remaining, contracts.unit || '吨'),
      tone: toneByMissing(formatMetric(contracts.daily_new, contracts.unit || '吨'), 'primary'),
    },
  ]
}

function formatDateTime(value) {
  if (!value) return '-'
  const match = String(value).match(/^(\d{4})-(\d{2})-(\d{2})[T\s](\d{2}):(\d{2})/)
  if (match) return `${match[2]}-${match[3]} ${match[4]}:${match[5]}`
  return '-'
}

function statusText(value) {
  const map = {
    submitted: '已提交',
    verified: '已核验',
    approved: '已确认',
    auto_confirmed: '自动确认',
    draft: '草稿',
    returned: '退回',
    not_started: '未填报',
  }
  return map[value] || value || '-'
}

function fixedMetric(value, digits = 3) {
  const numeric = toNumber(value)
  if (numeric === null) return null
  return numeric.toLocaleString('zh-CN', {
    minimumFractionDigits: 0,
    maximumFractionDigits: digits,
  })
}

function contentText(row = {}) {
  const parts = []
  const input = fixedMetric(row.input_weight)
  const output = fixedMetric(row.output_weight)
  const scrap = fixedMetric(row.scrap_weight)
  const energy = fixedMetric(row.energy_kwh, 1)
  const gas = fixedMetric(row.gas_m3, 1)

  if (output !== null) parts.push(`产量 ${output} 吨`)
  if (input !== null) parts.push(`上料 ${input} 吨`)
  if (scrap !== null) parts.push(`废料 ${scrap} 吨`)
  if (energy !== null) parts.push(`用电 ${energy} kWh`)
  if (gas !== null) parts.push(`天然气 ${gas} m³`)
  for (const item of row.metrics || []) {
    if (item?.value !== null && item?.value !== undefined && item?.value !== '') {
      parts.push(`${item.label || item.key} ${item.value}${item.unit || ''}`)
    }
  }
  return parts.length ? parts.join('；') : '-'
}

export function buildFillLedgerRows(rows = []) {
  return (rows || [])
    .filter((row) => !isRemovedWorkshop(row))
    .filter((row) => (row.source_type || row.sourceType) !== 'mes_projection')
    .map((row, index) => {
      const isOwnerDaily = row.source_type === 'owner_daily'
      const normalized = {
        ...row,
        rowId: row.row_id || row.id || `row-${index}`,
        sourceType: row.source_type || '',
        sourceLabel: row.source_label || row.source_type || '-',
        workshopName: row.workshop_name || '-',
        machineName: isOwnerDaily ? (row.machine_name || '内勤岗') : (row.machine_name || '-'),
        shiftName: isOwnerDaily ? '每日一录' : formatShiftLabel(row.shift_name),
        responsibleText: row.responsible_name || row.responsible_username || '-',
        responsibleUsername: row.responsible_username || '',
        submittedText: formatDateTime(row.submitted_at || row.updated_at),
        contentText: contentText(row),
        statusLabel: statusText(row.status),
      }
      normalized.auditSearchText = [
        normalized.search_text,
        normalized.sourceLabel,
        normalized.workshopName,
        normalized.machineName,
        normalized.shiftName,
        normalized.responsibleText,
        normalized.responsibleUsername,
        normalized.tracking_card_no,
        normalized.contentText,
        normalized.statusLabel,
      ].filter(Boolean).join(' ').toLowerCase()
      return normalized
    })
}

export function filterFillLedgerRows(rows = [], { keyword = '', sourceType = '' } = {}) {
  const text = String(keyword || '').trim().toLowerCase()
  return (rows || []).filter((row) => {
    if (sourceType && row.sourceType !== sourceType) return false
    if (!text) return true
    return String(row.auditSearchText || '').includes(text)
  })
}

function notSubmittedOwnerItems(status = {}) {
  return (status.items || []).filter((item) => item.status !== 'submitted')
}

function queueItems(items = [], formatter) {
  return items.slice(0, 3).map(formatter).filter(Boolean)
}

export function buildIssueQueues({ dailyOverview = {}, liveAggregation = {} } = {}) {
  const pending = liveAggregation.overall_progress?.pending_assignment || {}
  const pendingCount = Number(pending.entry_count || pending.pending_assignment_entry_count || 0)
  const missingOwners = notSubmittedOwnerItems(liveAggregation.owner_daily_status || {})
  const energy = dailyOverview.energy || {}
  const energyMissing = hasEnergyData(energy) ? 0 : 1
  const mes = liveAggregation.mes_machine_binding || {}
  const mesUnmatched = Number(mes.unresolved_machine_count || 0)

  return [
    {
      key: 'pending-assignment',
      title: '待归属机列',
      count: pendingCount,
      tone: pendingCount > 0 ? 'warning' : 'muted',
      items: [
        `缺机列 ${Number(pending.missing_machine_count || 0)} 条`,
        `缺班次 ${Number(pending.missing_shift_count || 0)} 条`,
      ],
    },
    {
      key: 'missing-owner',
      title: '未填报角色',
      count: missingOwners.length,
      tone: missingOwners.length ? 'danger' : 'muted',
      items: queueItems(missingOwners, (item) => `${item.role_label || item.role || '内勤'} · ${item.person_name || item.username || '-'} · ${item.workshop_name || '全厂专项'}`),
    },
    {
      key: 'missing-energy',
      title: '能耗缺失',
      count: energyMissing,
      tone: energyMissing ? 'danger' : 'muted',
      items: energyMissing ? ['算法总用电暂无可信数据'] : ['能耗主口径可用'],
    },
    {
      key: 'mes-unmatched',
      title: '外部 MES 未匹配机列',
      count: mesUnmatched,
      tone: mesUnmatched ? 'warning' : 'muted',
      items: [
        `未解析 ${Number(mes.unresolved_machine_count || 0)} 条`,
        `上游缺机列码 ${Number(mes.upstream_machine_code_missing_count || 0)} 条`,
      ],
    },
  ]
}
