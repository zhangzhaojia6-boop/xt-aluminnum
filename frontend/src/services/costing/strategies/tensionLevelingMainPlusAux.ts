import { allocateByRatio } from '../allocators'
import { computeEnergyCost, computePerTon, round2, sum, sumLineItems } from '../formulas'

export function runTensionLevelingMainPlusAux(scenario, priceSnapshot) {
  const processRows = (scenario.processes || []).map((row) => {
    const energyCost = computeEnergyCost({
      electricityKwh: row.electricityKwh,
      gasM3: row.gasM3,
      waterTon: row.waterTon
    }, priceSnapshot)
    const materialCost = sumLineItems(row.items || [], priceSnapshot)
    const laborCost = round2(Number(row.laborCost || 0))
    const outputTon = Number(row.outputTon || 0)
    return {
      key: row.key || row.name,
      process: row.name,
      outputTon,
      energyCost,
      materialCost,
      laborCost
    }
  })

  const utilityCost = computeEnergyCost({
    airKwh: scenario.airCompressorKwh,
    gasM3: scenario.boilerGasM3
  }, priceSnapshot)

  const allocationRows = allocateByRatio(
    utilityCost,
    processRows.map((row) => ({ key: row.key, ratio: row.outputTon }))
  )

  const allocationMap = Object.fromEntries(allocationRows.map((row) => [row.key, row.allocated]))

  const merged = processRows.map((row) => {
    const utilityAllocated = round2(Number(allocationMap[row.key] || 0))
    const cost = round2(row.energyCost + row.materialCost + row.laborCost + utilityAllocated)
    return {
      process: row.process,
      outputTon: row.outputTon,
      energyCost: row.energyCost,
      materialCost: row.materialCost,
      laborCost: row.laborCost,
      utilityAllocated,
      cost,
      perTon: computePerTon(cost, row.outputTon)
    }
  })

  const totalCost = sum(merged.map((row) => row.cost))
  const totalOutput = sum(merged.map((row) => row.outputTon))

  return {
    strategyCode: 'TENSION_LEVELING_MAIN_PLUS_AUX',
    totalCost,
    byOutputTon: computePerTon(totalCost, totalOutput),
    byThroughputTon: computePerTon(totalCost, Number(scenario.throughputTon || totalOutput)),
    breakdown: [
      { key: 'energy', label: '能源成本', value: sum(merged.map((row) => row.energyCost)) },
      { key: 'material', label: '辅材成本', value: sum(merged.map((row) => row.materialCost)) },
      { key: 'labor', label: '人工成本', value: sum(merged.map((row) => row.laborCost)) },
      { key: 'utility', label: '公辅分摊', value: sum(merged.map((row) => row.utilityAllocated)) }
    ],
    processRows: merged,
    explanation: [
      '输出同时包含：工序吨耗、公辅吨耗、综合吨耗。',
      '退火炉与拉矫主线材料按单价快照计算，空压/锅炉天然气按产量比例分摊。'
    ]
  }
}

