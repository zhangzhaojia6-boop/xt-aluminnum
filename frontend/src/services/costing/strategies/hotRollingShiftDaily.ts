import { computeEnergyCost, computePerTon, round2, sum, sumLineItems } from '../formulas'

export function runHotRollingShiftDaily(scenario, priceSnapshot) {
  const shifts = (scenario.shifts || []).map((shift) => {
    const laborCost = Number.isFinite(shift.laborAmount)
      ? round2(Number(shift.laborAmount))
      : round2(Number(shift.laborCount || 0) * 178)
    const materialCost = sumLineItems(shift.items || [], priceSnapshot)
    const energyCost = computeEnergyCost({
      electricityKwh: shift.electricityKwh,
      gasM3: shift.gasM3,
      waterTon: shift.waterTon
    }, priceSnapshot)
    const supportCost = round2(Number(shift.supportAmount || 0))
    const total = round2(laborCost + materialCost + energyCost + supportCost)
    const outputTon = Number(shift.outputTon || 0)
    return {
      process: shift.name || shift.shiftName || '班次',
      outputTon,
      laborCost,
      materialCost,
      energyCost,
      supportCost,
      cost: total,
      perTon: computePerTon(total, outputTon)
    }
  })

  const totalCost = sum(shifts.map((row) => row.cost))
  const totalOutput = sum(shifts.map((row) => row.outputTon))

  return {
    strategyCode: 'HOT_ROLLING_SHIFT_DAILY',
    totalCost,
    byOutputTon: computePerTon(totalCost, totalOutput),
    byThroughputTon: computePerTon(totalCost, Number(scenario.throughputTon || totalOutput)),
    breakdown: [
      { key: 'labor', label: '人工成本', value: sum(shifts.map((row) => row.laborCost)) },
      { key: 'material', label: '油品与辅材', value: sum(shifts.map((row) => row.materialCost)) },
      { key: 'energy', label: '能源成本', value: sum(shifts.map((row) => row.energyCost)) },
      { key: 'support', label: '设备保障', value: sum(shifts.map((row) => row.supportCost)) }
    ],
    processRows: shifts,
    explanation: [
      '热轧按白班/小夜/大夜逐班归集，日总吨耗=日总成本/日产量。',
      '示例口径支持：2026-04-15 产量 410.93 吨，总成本 136085.37 元，吨耗 331.16 元/吨。'
    ]
  }
}

