import { computeRoleLaborByPassAndMinute } from '../allocators'
import { computeEnergyCost, computePerTon, round2, sum, sumLineItems } from '../formulas'

const ROLE_RULES_2050 = {
  主操: { perPass: 11.2, perMinute: 0.42 },
  副操: { perPass: 6.7, perMinute: 0.31 },
  普工: { perPass: 5.6, perMinute: 0.26 },
  行车工: { perPass: 4.5, perMinute: 0.23 }
}

const ROLE_RULES_1650 = {
  主操: { perPass: 12.9, perMinute: 0.42 },
  副操: { perPass: 7.7, perMinute: 0.31 },
  普工: { perPass: 6.5, perMinute: 0.26 },
  行车工: { perPass: 5.2, perMinute: 0.23 }
}

function resolveRoleRules(workshopCode: string) {
  if (workshopCode === '2050') return ROLE_RULES_2050
  if (workshopCode === '1650') return ROLE_RULES_1650
  return {}
}

export function runLossDualCaliber(scenario, priceSnapshot) {
  const workshopCode = String(scenario.workshopCode || '').trim()
  const roleRules = resolveRoleRules(workshopCode)
  const laborRows = computeRoleLaborByPassAndMinute(roleRules, scenario.roleLaborRows || [])
  const laborCost = sum(laborRows.map((row) => row.cost))
  const materialLossCost = sumLineItems(scenario.lossItems || [], priceSnapshot)
  const energyCost = computeEnergyCost({
    electricityKwh: scenario.electricityKwh
  }, priceSnapshot)
  const supportCost = round2(Number(scenario.supportAmount || 0))
  const extraPatternCost = round2(Number(scenario.patternExtraAmount || 0))
  const totalCost = round2(materialLossCost + energyCost + laborCost + supportCost + extraPatternCost)

  const outputTon = Number(scenario.outputTon || 0)
  const throughputTon = Number(scenario.throughputTon || 0)

  return {
    strategyCode: 'LOSS_DUAL_CALIBER',
    totalCost,
    byOutputTon: computePerTon(totalCost, outputTon),
    byThroughputTon: computePerTon(totalCost, throughputTon),
    breakdown: [
      { key: 'loss', label: '损耗金额', value: materialLossCost },
      { key: 'energy', label: '电耗成本', value: energyCost },
      { key: 'labor', label: '人工成本', value: laborCost },
      { key: 'support', label: '辊系与保障', value: supportCost + extraPatternCost }
    ],
    processRows: [
      {
        process: `${workshopCode || '轧线'}损耗`,
        outputTon,
        throughputTon,
        cost: totalCost,
        perTonByOutput: computePerTon(totalCost, outputTon),
        perTonByThroughput: computePerTon(totalCost, throughputTon)
      }
    ],
    laborRows,
    explanation: [
      '先汇总损耗金额，再除以通货量和产量，形成双口径单耗。',
      workshopCode === '1850'
        ? '1850 当前按人工金额直录，后续可扩展岗位道次规则。'
        : '2050/1650 支持岗位道次+分钟计费。'
    ]
  }
}

