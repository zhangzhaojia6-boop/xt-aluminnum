import { round2, safeNumber, sum } from './formulas'

export function allocateByRatio(
  total: number,
  rows: Array<{ key: string; ratio?: number }>
): Array<{ key: string; allocated: number; ratio: number }> {
  const normalized = rows.map((row) => ({
    key: row.key,
    ratio: Math.max(safeNumber(row.ratio, 0), 0)
  }))
  const ratioTotal = sum(normalized.map((row) => row.ratio))
  if (ratioTotal <= 0) {
    return normalized.map((row) => ({ key: row.key, ratio: 0, allocated: 0 }))
  }
  const result = normalized.map((row) => ({
    key: row.key,
    ratio: round2(row.ratio / ratioTotal),
    allocated: round2((safeNumber(total, 0) * row.ratio) / ratioTotal)
  }))
  return result
}

export function computeRoleLaborByPassAndMinute(
  roleRules: Record<string, { perPass: number; perMinute: number }>,
  rows: Array<{ role: string; passes?: number; minutes?: number; amount?: number }>
): Array<{ role: string; cost: number; formula: string }> {
  return rows.map((row) => {
    if (Number.isFinite(row.amount)) {
      return {
        role: row.role,
        cost: round2(safeNumber(row.amount, 0)),
        formula: '金额直录'
      }
    }
    const rule = roleRules[row.role] || { perPass: 0, perMinute: 0 }
    const passes = safeNumber(row.passes, 0)
    const minutes = safeNumber(row.minutes, 0)
    const cost = round2(passes * safeNumber(rule.perPass, 0) + minutes * safeNumber(rule.perMinute, 0))
    return {
      role: row.role,
      cost,
      formula: `${passes}道*${rule.perPass}+${minutes}分*${rule.perMinute}`
    }
  })
}

