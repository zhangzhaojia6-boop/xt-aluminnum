export function round2(value: number): number {
  if (!Number.isFinite(value)) return 0
  return Math.round(value * 100) / 100
}

export function safeNumber(value: unknown, fallback = 0): number {
  const numeric = Number(value)
  if (!Number.isFinite(numeric)) return fallback
  return numeric
}

export function sum(values: Array<number | null | undefined>): number {
  return round2(values.reduce((acc, item) => acc + safeNumber(item, 0), 0))
}

export function sumLineItems(
  items: Array<{ code?: string; amount?: number; quantity?: number }> = [],
  priceMap: Record<string, number> = {}
): number {
  const total = items.reduce((acc, item) => {
    if (Number.isFinite(item.amount)) return acc + safeNumber(item.amount, 0)
    const unitPrice = safeNumber(priceMap[item.code || ''], 0)
    return acc + safeNumber(item.quantity, 0) * unitPrice
  }, 0)
  return round2(total)
}

export function computeEnergyCost(
  payload: { electricityKwh?: number; gasM3?: number; waterTon?: number; steamTon?: number; airKwh?: number } = {},
  priceMap: Record<string, number> = {}
): number {
  const electricity = safeNumber(payload.electricityKwh, 0) * safeNumber(priceMap.ELECTRICITY, 0)
  const gas = safeNumber(payload.gasM3, 0) * safeNumber(priceMap.NATURAL_GAS, 0)
  const water = safeNumber(payload.waterTon, 0) * safeNumber(priceMap.WATER, 0)
  const steam = safeNumber(payload.steamTon, 0) * safeNumber(priceMap.STEAM, 0)
  const air = safeNumber(payload.airKwh, 0) * safeNumber(priceMap.AIR_ELECTRICITY, 0)
  return round2(electricity + gas + water + steam + air)
}

export function computePerTon(totalCost: number, denominatorTon: number): number {
  const denominator = safeNumber(denominatorTon, 0)
  if (denominator <= 0) return 0
  return round2(safeNumber(totalCost, 0) / denominator)
}

