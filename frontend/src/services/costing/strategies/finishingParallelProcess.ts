import { computeEnergyCost, computePerTon, round2, sum, sumLineItems } from '../formulas'

export function runFinishingParallelProcess(scenario, priceSnapshot) {
  const processes = (scenario.processes || []).map((process) => {
    const materialCost = sumLineItems(process.items || [], priceSnapshot)
    const packagingCost = round2(Number(process.packagingAmount || 0))
    const laborCost = round2(Number(process.laborCost || 0))
    const energyCost = computeEnergyCost({ electricityKwh: process.electricityKwh }, priceSnapshot)
    const total = round2(materialCost + packagingCost + laborCost + energyCost)
    const outputTon = Number(process.outputTon || 0)
    return {
      process: process.name,
      outputTon,
      materialCost,
      packagingCost,
      laborCost,
      energyCost,
      cost: total,
      perTon: computePerTon(total, outputTon)
    }
  })

  const totalCost = sum(processes.map((row) => row.cost))
  const totalOutput = sum(processes.map((row) => row.outputTon))

  return {
    strategyCode: 'FINISHING_PARALLEL_PROCESS',
    totalCost,
    byOutputTon: computePerTon(totalCost, totalOutput),
    byThroughputTon: computePerTon(totalCost, Number(scenario.throughputTon || totalOutput)),
    breakdown: [
      { key: 'material', label: '辅料成本', value: sum(processes.map((row) => row.materialCost)) },
      { key: 'packaging', label: '包装成本', value: sum(processes.map((row) => row.packagingCost)) },
      { key: 'labor', label: '人工成本', value: sum(processes.map((row) => row.laborCost)) },
      { key: 'energy', label: '电力成本', value: sum(processes.map((row) => row.energyCost)) }
    ],
    processRows: processes,
    explanation: [
      '各工序并行归集：新19辊 / 纵剪 / 包装分别计算，再汇总。',
      'D40 默认单价 9.5 元/公斤，支持后续价格主数据覆盖。'
    ]
  }
}

