import { computeEnergyCost, computePerTon, round2, sumLineItems } from '../formulas'

export function runCastingMachineLaborSplit(scenario, priceSnapshot) {
  const directCost = sumLineItems(scenario.directItems || [], priceSnapshot)
  const alloyCost = sumLineItems(scenario.alloyItems || [], priceSnapshot)
  const energyCost = computeEnergyCost({
    electricityKwh: scenario.electricityKwh,
    gasM3: scenario.gasM3
  }, priceSnapshot)
  const laborCost = round2(Number(scenario.laborTotal || 0))
  const totalCost = round2(directCost + alloyCost + energyCost + laborCost)
  const outputTon = Number(scenario.outputTon || 0)

  return {
    strategyCode: 'CASTING_MACHINE_LABOR_SPLIT',
    totalCost,
    byOutputTon: computePerTon(totalCost, outputTon),
    byThroughputTon: computePerTon(totalCost, Number(scenario.throughputTon || outputTon)),
    breakdown: [
      { key: 'direct', label: '机列直接成本', value: directCost },
      { key: 'alloy', label: '合金与辅材', value: alloyCost },
      { key: 'energy', label: '能源成本', value: energyCost },
      { key: 'labor', label: '人工分摊', value: laborCost }
    ],
    processRows: [
      {
        process: '铸造机列',
        outputTon,
        cost: totalCost,
        perTon: computePerTon(totalCost, outputTon)
      }
    ],
    explanation: [
      '公式：综合吨耗 = (直接成本 + 人工总额 + 能源成本) / 当日产量。',
      '默认价格：电 0.8 元/度，天然气 3.6 元/立方。'
    ]
  }
}

