import { compareShiftLabels, formatNumber, formatShiftLabel } from './display.js'
import { filterActiveWorkshopRows, normalizeWorkshopName } from './activeWorkshops.js'

const MISSING_TEXT = '待同步'
const PROCESS_FLOW_STAGES = [
  {
    key: 'casting',
    stage: '铸轧',
    match: /铸|熔铸|铸锭/,
  },
  {
    key: 'hot-rolling',
    stage: '热轧',
    match: /热轧/,
  },
  {
    key: 'cold-rolling',
    stage: '冷轧',
    match: /冷轧|1650|1850|2050/,
  },
  {
    key: 'annealing',
    stage: '退火',
    match: /退火/,
  },
  {
    key: 'finishing',
    stage: '精整',
    match: /精整|拉矫|剪切|纵剪|横剪/,
  },
  {
    key: 'packaging',
    stage: '包装入库',
    match: /包装|成品|入库/,
  },
]

function isPresent(value) {
  if (value === null || value === undefined || value === '') return false
  return Number.isFinite(Number(value))
}

function numberValue(value) {
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : 0
}

function roundMetric(value, digits = 2) {
  return Number(Number(value).toFixed(digits))
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

  const packagingOutput = pickValue(factoryTotal, [
    'packaging_output',
    'packagingOutput',
    'daily_output',
    'dailyOutput',
    'factory_total_output',
    'factoryTotalOutput',
  ])
  const finishedInboundOutput = pickValue(factoryTotal, [
    'finished_inbound_output',
    'finishedInboundOutput',
    'owner_storage_finished_weight',
    'ownerStorageFinishedWeight',
    'storage_finished_weight',
    'storageFinishedWeight',
    'finished_storage_weight',
    'finishedStorageWeight',
  ])
  const feedingInput = pickValue(factoryTotal, [
    'feeding_input',
    'feedingInput',
    'factory_feeding_daily_input',
    'factoryFeedingDailyInput',
  ])
  const yieldRate = pickValue(factoryTotal, [
    'yield_rate',
    'yieldRate',
    'daily_yield_rate',
    'dailyYieldRate',
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
      label: '投料量',
      value: formatTrustedMetric(feedingInput, '吨'),
      tone: isPresent(feedingInput) ? 'primary' : 'muted',
      source: 'MES投料',
    },
    {
      label: '全厂包装',
      value: formatTrustedMetric(packagingOutput, '吨'),
      tone: isPresent(packagingOutput) ? 'success' : 'muted',
      source: '包装工序',
    },
    {
      label: '成品入库',
      value: formatTrustedMetric(finishedInboundOutput, '吨'),
      tone: isPresent(finishedInboundOutput) ? 'success' : 'muted',
      source: '成品入库',
    },
    {
      label: '全厂成品率',
      value: formatTrustedMetric(yieldRate, '%'),
      tone: isPresent(yieldRate) ? 'primary' : 'muted',
      source: '投料入库',
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
    workshopName: normalizeWorkshopName(workshop.workshop_name || workshop.workshopName || '--'),
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

  filterActiveWorkshopRows(workshops).forEach((workshop) => {
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
        workshopName: normalizeWorkshopName(workshop.workshop_name || workshop.workshopName || '--'),
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

function resolveProcessStage(workshop = {}) {
  const text = [
    workshop.workshop_name,
    workshop.workshopName,
    workshop.process_name,
    workshop.processName,
  ].filter(Boolean).join(' ')

  return PROCESS_FLOW_STAGES.find((stage) => stage.match.test(text)) || null
}

function dayTotalOf(machine = {}) {
  return machine.day_total || machine.dayTotal || {}
}

function workshopTotalOf(workshop = {}) {
  return workshop.workshop_total || workshop.workshopTotal || {}
}

function addIfPresent(target, key, value) {
  if (!isPresent(value)) return
  target[key] += Number(value)
  target[`${key}Count`] += 1
}

function buildFlowAccumulator(stage) {
  return {
    key: stage.key,
    stage: stage.stage,
    input: 0,
    inputCount: 0,
    output: 0,
    outputCount: 0,
    scrap: 0,
    scrapCount: 0,
    machineCount: 0,
    pendingMachineCount: 0,
    workshopNames: new Set(),
  }
}

function applyFactoryPackagingOutput(stageMap, aggregation = {}) {
  const factoryTotal = resolveFactoryTotal(aggregation)
  const packagingOutput = pickValue(factoryTotal, [
    'packaging_output',
    'packagingOutput',
    'daily_output',
    'dailyOutput',
    'factory_total_output',
    'factoryTotalOutput',
  ])
  if (!isPresent(packagingOutput)) return

  const packaging = stageMap.get('packaging')
  packaging.output = Number(packagingOutput)
  packaging.outputCount = Math.max(packaging.outputCount, 1)
}

export function buildLiveProcessFlowItems(aggregation = {}) {
  const stageMap = new Map(PROCESS_FLOW_STAGES.map((stage) => [stage.key, buildFlowAccumulator(stage)]))

  filterActiveWorkshopRows(aggregation.workshops || []).forEach((workshop) => {
    const stage = resolveProcessStage(workshop)
    if (!stage) return

    const bucket = stageMap.get(stage.key)
    const machines = Array.isArray(workshop.machines) ? workshop.machines : []
    bucket.workshopNames.add(normalizeWorkshopName(workshop.workshop_name || workshop.workshopName || stage.stage))

    if (!machines.length) {
      const workshopTotal = workshopTotalOf(workshop)
      addIfPresent(bucket, 'input', workshopTotal.input)
      addIfPresent(bucket, 'output', workshopTotal.output)
      addIfPresent(bucket, 'scrap', workshopTotal.scrap)
      return
    }

    machines.forEach((machine) => {
      const dayTotal = dayTotalOf(machine)
      bucket.machineCount += 1
      if (isUnboundMachine(machine)) bucket.pendingMachineCount += 1
      addIfPresent(bucket, 'input', dayTotal.input)
      addIfPresent(bucket, 'output', dayTotal.output)
      addIfPresent(bucket, 'scrap', dayTotal.scrap)
    })
  })

  applyFactoryPackagingOutput(stageMap, aggregation)

  return PROCESS_FLOW_STAGES.map((stage) => {
    const bucket = stageMap.get(stage.key)
    const hasTrustedOutput = bucket.outputCount > 0
    const output = hasTrustedOutput ? roundMetric(bucket.output) : null
    const tone = bucket.pendingMachineCount > 0 ? 'warning' : (hasTrustedOutput ? 'success' : 'muted')

    return {
      key: bucket.key,
      stage: bucket.stage,
      output,
      input: bucket.inputCount > 0 ? roundMetric(bucket.input) : null,
      scrap: bucket.scrapCount > 0 ? roundMetric(bucket.scrap) : null,
      valueText: hasTrustedOutput ? formatTrustedMetric(output, '吨') : MISSING_TEXT,
      inputText: bucket.inputCount > 0 ? formatTrustedMetric(bucket.input, '吨') : MISSING_TEXT,
      scrapText: bucket.scrapCount > 0 ? formatTrustedMetric(bucket.scrap, '吨') : MISSING_TEXT,
      machineCount: bucket.machineCount,
      pendingMachineCount: bucket.pendingMachineCount,
      workshopNames: [...bucket.workshopNames],
      hasTrustedOutput,
      source: stage.key === 'packaging' && hasTrustedOutput ? '包装工序' : (hasTrustedOutput ? '实时聚合' : MISSING_TEXT),
      tone,
    }
  })
}

function resolveOwnerValue(energy = {}, keys = []) {
  const ownerTotals = energy.owner_totals || energy.ownerTotals || {}
  return pickValue({ ...ownerTotals, ...energy }, keys)
}

export function buildLiveMetricCompareItems(aggregation = {}) {
  const factoryTotal = resolveFactoryTotal(aggregation)
  const energy = resolveEnergySummary(aggregation)

  const algorithmOutput = pickValue(factoryTotal, [
    'packaging_output',
    'packagingOutput',
    'daily_output',
    'dailyOutput',
    'factory_total_output',
    'factoryTotalOutput',
  ])
  const filledOutput = pickValue(factoryTotal, [
    'finished_inbound_output',
    'finishedInboundOutput',
    'owner_storage_finished_weight',
    'ownerStorageFinishedWeight',
    'filled_storage_finished_weight',
    'filledStorageFinishedWeight',
  ])
  const feedingInput = pickValue(factoryTotal, [
    'feeding_input',
    'feedingInput',
    'factory_feeding_daily_input',
    'factoryFeedingDailyInput',
  ])
  const yieldRate = pickValue(factoryTotal, [
    'yield_rate',
    'yieldRate',
    'daily_yield_rate',
    'dailyYieldRate',
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
      primaryLabel: '全厂包装',
      primaryValue: formatTrustedMetric(algorithmOutput, '吨'),
      compareLabel: '全厂入库',
      compareValue: formatTrustedMetric(filledOutput, '吨'),
      tone: isPresent(algorithmOutput) ? 'success' : 'muted',
    },
    {
      label: '全厂成品率',
      primaryLabel: '成品入库',
      primaryValue: formatTrustedMetric(filledOutput, '吨'),
      compareLabel: '投料量',
      compareValue: formatTrustedMetric(feedingInput, '吨'),
      value: formatTrustedMetric(yieldRate, '%'),
      tone: isPresent(yieldRate) ? 'primary' : 'muted',
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
  if (!isPresent(pickValue(energy, ['algorithm_total_energy', 'algorithmTotalEnergy', 'total_electricity', 'totalElectricity']))) {
    events.push({ title: '能耗待同步', tone: 'warning', text: '等待电工或算法能耗明细' })
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

function eventDateMatches(payload = {}, targetDate = '') {
  const eventDate = payload.business_date || payload.businessDate
  const eventDates = payload.business_dates || payload.businessDates || []
  if (Array.isArray(eventDates) && eventDates.length) {
    return !targetDate || eventDates.includes(targetDate)
  }
  return !eventDate || !targetDate || eventDate === targetDate
}

export function mergeRealtimeEventPatch(currentAggregation = {}, { payload = {}, targetDate = '' } = {}) {
  if (!eventDateMatches(payload, targetDate)) return null
  const aggregationPatch = payload.aggregation || payload.snapshot || {}
  const patch = { ...aggregationPatch }
  for (const key of ['factory_total', 'energy_summary', 'overall_progress', 'mes_sync_status', 'data_quality']) {
    if (payload[key]) {
      patch[key] = {
        ...(currentAggregation[key] || {}),
        ...payload[key],
      }
    }
  }
  if (Array.isArray(payload.workshops)) {
    patch.workshops = payload.workshops
  }
  const businessDate = payload.business_date || payload.businessDate
  if (businessDate) patch.business_date = businessDate
  if (!Object.keys(patch).length) return null
  return {
    ...currentAggregation,
    ...patch,
  }
}

export function shouldReloadForRealtimeEvent({ type = '', payload = {}, targetDate = '' } = {}) {
  if (type === 'heartbeat' || type === 'ping') return false
  const hasEventDate = Boolean(
    payload?.business_date
    || payload?.businessDate
    || (Array.isArray(payload?.business_dates) && payload.business_dates.length)
    || (Array.isArray(payload?.businessDates) && payload.businessDates.length)
  )
  if (!hasEventDate) return false
  return eventDateMatches(payload, targetDate)
}
