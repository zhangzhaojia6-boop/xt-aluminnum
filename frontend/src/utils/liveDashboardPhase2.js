import { compareShiftLabels, formatNumber, formatShiftLabel } from './display.js'

const MISSING_TEXT = '暂无可信数据'
const REMOVED_WORKSHOP_NAMES = new Set(['冷轧三车间', '二分厂精整车间'])

function isPresent(value) {
  if (value === null || value === undefined || value === '') return false
  return Number.isFinite(Number(value))
}

function numberValue(value) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : 0
}

function pickValue(source = {}, keys = []) {
  for (const key of keys) {
    if (isPresent(source[key])) return source[key]
  }
  return null
}

export function formatTrustedMetric(value, unit = '', digits = 2) {
  if (!isPresent(value)) return MISSING_TEXT
  const text = formatNumber(value, digits)
  return unit ? `${text} ${unit}` : text
}

function formatCount(value) {
  return isPresent(value) ? String(Number(value)) : MISSING_TEXT
}

function formatLag(seconds) {
  if (!isPresent(seconds)) return MISSING_TEXT
  const lag = Number(seconds)
  if (lag < 60) return `${lag.toFixed(0)}s`
  return `${(lag / 60).toFixed(1)}m`
}

function resolveEnergySummary(aggregation = {}) {
  return aggregation.energy_summary || aggregation.energySummary || {}
}

function resolveFactoryTotal(aggregation = {}) {
  return aggregation.factory_total || aggregation.factoryTotal || {}
}

function isEnergyUsable(energy = {}) {
  return energy.data_available !== false && energy.dataAvailable !== false
}

export function buildLiveTickerItems(aggregation = {}) {
  const factoryTotal = resolveFactoryTotal(aggregation)
  const energy = resolveEnergySummary(aggregation)
  const progress = aggregation.overall_progress || aggregation.overallProgress || {}
  const sync = aggregation.mes_sync_status || aggregation.mesSyncStatus || {}
  const missingCellCount = progress.missing_cell_count ?? progress.missingCellCount
  const attentionCellCount = progress.attention_cell_count ?? progress.attentionCellCount
  const syncLagSeconds = sync.lag_seconds ?? sync.lagSeconds

  const storageFinishedWeight = pickValue(factoryTotal, [
    'storage_finished_weight',
    'storageFinishedWeight',
    'finished_storage_weight',
    'finishedStorageWeight',
    'warehouse_finished_weight',
  ])
  const throughProcessOutput = pickValue(factoryTotal, [
    'process_output',
    'through_process_output',
    'throughProcessOutput',
    'output',
  ])
  const algorithmEnergy = isEnergyUsable(energy)
    ? pickValue(energy, [
      'algorithm_total_energy',
      'algorithmTotalEnergy',
      'total_electricity',
      'totalElectricity',
    ])
    : null
  const algorithmPerTon = isEnergyUsable(energy)
    ? pickValue(energy, [
      'algorithm_energy_per_ton',
      'algorithmEnergyPerTon',
      'energy_per_ton',
      'energyPerTon',
    ])
    : null

  return [
    {
      label: '成品入库',
      value: formatTrustedMetric(storageFinishedWeight, '吨'),
      tone: isPresent(storageFinishedWeight) ? 'success' : 'muted',
      source: '最终产量',
    },
    {
      label: '过站下机',
      value: formatTrustedMetric(throughProcessOutput, '吨'),
      tone: isPresent(throughProcessOutput) ? 'primary' : 'muted',
      source: '工序通过量',
    },
    {
      label: '总电耗',
      value: formatTrustedMetric(algorithmEnergy, 'kWh'),
      tone: isPresent(algorithmEnergy) ? 'warning' : 'muted',
      source: '算法',
    },
    {
      label: '吨电耗',
      value: formatTrustedMetric(algorithmPerTon, 'kWh/吨'),
      tone: isPresent(algorithmPerTon) ? 'warning' : 'muted',
      source: '算法',
    },
    {
      label: '未填',
      value: formatCount(missingCellCount),
      tone: isPresent(missingCellCount) ? (numberValue(missingCellCount) > 0 ? 'danger' : 'success') : 'muted',
      source: '填报',
    },
    {
      label: '异常',
      value: formatCount(attentionCellCount),
      tone: isPresent(attentionCellCount) ? (numberValue(attentionCellCount) > 0 ? 'warning' : 'success') : 'muted',
      source: '状态',
    },
    {
      label: '外部 MES',
      value: formatLag(syncLagSeconds),
      tone: isPresent(syncLagSeconds) ? (numberValue(syncLagSeconds) > 300 ? 'warning' : 'success') : 'muted',
      source: '新鲜度',
    },
  ]
}

function isRemovedWorkshop(workshop = {}) {
  const name = String(workshop.workshop_name || workshop.workshopName || '').trim()
  const status = String(workshop.status || workshop.workshop_status || workshop.workshopStatus || '').toLowerCase()
  return workshop.is_removed === true
    || workshop.removed === true
    || workshop.is_active === false
    || status === 'removed'
    || REMOVED_WORKSHOP_NAMES.has(name)
}

function isUnboundMachine(machine = {}) {
  const status = String(machine.machine_binding_status || machine.machineBindingStatus || '').toLowerCase()
  const name = String(machine.machine_name || machine.machineName || '')
  return status === 'unbound' || Number(machine.machine_id ?? machine.machineId) < 0 || name.includes('未绑定')
}

function resolveMachineTone(machine = {}) {
  const shifts = Array.isArray(machine.shifts) ? machine.shifts : []
  if (isUnboundMachine(machine)) return 'pending'
  if (shifts.some((shift) => shift.submission_status === 'not_started' || shift.status_tone === 'danger')) return 'danger'
  if (shifts.some((shift) => shift.submission_status === 'in_progress' || shift.status_tone === 'warning')) return 'warning'
  if (shifts.some((shift) => shift.submission_status === 'all_submitted')) return 'success'
  return 'muted'
}

function normalizeMachine(workshop, machine) {
  const dayTotal = machine.day_total || machine.dayTotal || {}
  return {
    id: machine.machine_id ?? machine.machineId ?? machine.machine_name,
    workshopId: workshop.workshop_id ?? workshop.workshopId,
    workshopName: workshop.workshop_name || workshop.workshopName || '--',
    machineId: machine.machine_id ?? machine.machineId,
    machineName: machine.machine_name || machine.machineName || '--',
    output: numberValue(dayTotal.output),
    input: numberValue(dayTotal.input),
    scrap: numberValue(dayTotal.scrap),
    yieldRate: dayTotal.yield_rate ?? dayTotal.yieldRate ?? null,
    tone: resolveMachineTone(machine),
    shifts: (machine.shifts || [])
      .map((shift) => ({
        shiftId: shift.shift_id ?? shift.shiftId,
        shiftName: formatShiftLabel(shift.shift_name || shift.shiftName, '--'),
        status: shift.submission_status || shift.status || 'not_started',
        statusText: shift.status_text || shift.statusText || (shift.submission_status === 'all_submitted' ? '已填' : (shift.submission_status === 'in_progress' ? '进行中' : '缺报')),
        submittedCount: numberValue(shift.submitted_count ?? shift.submittedCount),
        output: numberValue(shift.total_output ?? shift.totalOutput),
        isApplicable: shift.is_applicable !== false,
      }))
      .sort((left, right) => compareShiftLabels(left.shiftName, right.shiftName)),
  }
}

export function buildLiveMachineMatrix(workshops = []) {
  const pendingMachines = []
  const normalizedWorkshops = []

  ;(workshops || []).forEach((workshop) => {
    if (isRemovedWorkshop(workshop)) return

    const machines = []
    ;(workshop.machines || []).forEach((machine) => {
      const normalized = normalizeMachine(workshop, machine)
      if (isUnboundMachine(machine)) {
        pendingMachines.push(normalized)
      } else {
        machines.push(normalized)
      }
    })

    if (machines.length) {
      normalizedWorkshops.push({
        workshopId: workshop.workshop_id ?? workshop.workshopId,
        workshopName: workshop.workshop_name || workshop.workshopName || '--',
        output: numberValue(workshop.workshop_total?.output ?? workshop.workshopTotal?.output),
        machines,
      })
    }
  })

  return {
    workshops: normalizedWorkshops,
    pendingMachines,
    machineCount: normalizedWorkshops.reduce((sum, workshop) => sum + workshop.machines.length, 0),
  }
}

function resolveOwnerValue(energy = {}, keys = []) {
  const ownerTotals = energy.owner_totals || energy.ownerTotals || {}
  return pickValue({ ...ownerTotals, ...energy }, keys)
}

export function buildLiveMetricCompareItems(aggregation = {}) {
  const factoryTotal = resolveFactoryTotal(aggregation)
  const energy = resolveEnergySummary(aggregation)

  const algorithmOutput = pickValue(factoryTotal, [
    'storage_finished_weight',
    'storageFinishedWeight',
    'finished_storage_weight',
    'finishedStorageWeight',
  ])
  const filledOutput = pickValue(factoryTotal, [
    'owner_storage_finished_weight',
    'ownerStorageFinishedWeight',
    'filled_storage_finished_weight',
    'filledStorageFinishedWeight',
  ])
  const algorithmEnergy = isEnergyUsable(energy)
    ? pickValue(energy, [
      'algorithm_total_energy',
      'algorithmTotalEnergy',
      'total_electricity',
      'totalElectricity',
    ])
    : null
  const filledEnergy = isEnergyUsable(energy)
    ? resolveOwnerValue(energy, [
      'owner_total_electricity',
      'ownerTotalElectricity',
      'electricity_value',
      'electricityValue',
    ])
    : null
  const algorithmPerTon = isEnergyUsable(energy)
    ? pickValue(energy, [
      'algorithm_energy_per_ton',
      'algorithmEnergyPerTon',
      'energy_per_ton',
      'energyPerTon',
    ])
    : null

  return [
    {
      label: '全厂总产量',
      primaryLabel: '算法',
      primaryValue: formatTrustedMetric(algorithmOutput, '吨'),
      compareLabel: '填报',
      compareValue: formatTrustedMetric(filledOutput, '吨'),
      tone: isPresent(algorithmOutput) ? 'success' : 'muted',
    },
    {
      label: '全厂总电耗',
      primaryLabel: '算法',
      primaryValue: formatTrustedMetric(algorithmEnergy, 'kWh'),
      compareLabel: '电工填报',
      compareValue: formatTrustedMetric(filledEnergy, 'kWh'),
      tone: isPresent(algorithmEnergy) ? 'warning' : 'muted',
    },
    {
      label: '吨电耗',
      primaryLabel: '算法',
      primaryValue: formatTrustedMetric(algorithmPerTon, 'kWh/吨'),
      compareLabel: '状态',
      compareValue: isPresent(algorithmPerTon) ? '可参考' : MISSING_TEXT,
      tone: isPresent(algorithmPerTon) ? 'primary' : 'muted',
    },
  ]
}

export function buildLiveEventItems({ streamStatus = 'idle', loadError = '', aggregation = {} } = {}) {
  const events = []
  const progress = aggregation.overall_progress || aggregation.overallProgress || {}
  const energy = resolveEnergySummary(aggregation)
  const quality = aggregation.data_quality || aggregation.dataQuality || {}
  const missingOutput = quality.missing_output_weight || quality.missingOutputWeight || {}

  if (['reconnecting', 'closed', 'idle'].includes(streamStatus)) {
    events.push({ title: '实时连接断开', tone: 'warning', text: streamStatus === 'reconnecting' ? '正在重连' : '等待连接' })
  }
  if (loadError) {
    events.push({ title: '接口失败', tone: 'danger', text: String(loadError) })
  }
  if (numberValue(progress.missing_cell_count ?? progress.missingCellCount) > 0) {
    events.push({ title: '未填报', tone: 'danger', text: `${numberValue(progress.missing_cell_count ?? progress.missingCellCount)} 个班次` })
  }
  if (!isPresent(pickValue(energy, ['algorithm_total_energy', 'algorithmTotalEnergy', 'total_energy', 'totalEnergy', 'total_electricity', 'totalElectricity']))) {
    events.push({ title: '无能耗可信数据', tone: 'warning', text: '能耗不显示假 0' })
  }
  if (numberValue(missingOutput.entry_count ?? missingOutput.entryCount) > 0) {
    events.push({ title: '待补产出重量', tone: 'warning', text: `${numberValue(missingOutput.entry_count ?? missingOutput.entryCount)} 条` })
  }

  return events.slice(0, 8)
}

export function buildLivePriorityItems(events = []) {
  const toneRank = { danger: 0, warning: 1, primary: 2, success: 3, muted: 4 }
  return (events || [])
    .map((event, index) => ({
      ...event,
      sourceIndex: index,
      sortRank: toneRank[event.tone] ?? 5,
    }))
    .sort((left, right) => (left.sortRank - right.sortRank) || (left.sourceIndex - right.sourceIndex))
    .slice(0, 3)
    .map((event, index) => ({
      ...event,
      rank: index + 1,
    }))
}

export function shouldReloadForRealtimeEvent({ type = '', payload = {}, targetDate = '' } = {}) {
  if (type === 'heartbeat' || type === 'ping') return false
  const eventDate = payload.business_date || payload.businessDate
  return !eventDate || !targetDate || eventDate === targetDate
}
