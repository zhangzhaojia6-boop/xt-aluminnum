export type PriceMasterRow = {
  item_code: string
  item_name: string
  unit: string
  unit_price: number
  effective_from: string
  effective_to: string
  workshop_scope: string
  process_scope: string
  source_note: string
}

export const COST_PRICE_MASTER_TABLE = 'cost_price_master'

export const DEFAULT_PRICE_MASTER_ROWS: PriceMasterRow[] = [
  { item_code: 'ELECTRICITY', item_name: '电费', unit: 'kWh', unit_price: 0.8, effective_from: '2026-04-01', effective_to: '', workshop_scope: 'ALL', process_scope: 'ALL', source_note: '大推进.md 默认单价' },
  { item_code: 'NATURAL_GAS', item_name: '天然气', unit: 'm3', unit_price: 3.6, effective_from: '2026-04-01', effective_to: '', workshop_scope: 'ALL', process_scope: 'ALL', source_note: '大推进.md 默认单价' },
  { item_code: 'WATER', item_name: '水', unit: 't', unit_price: 1.1, effective_from: '2026-04-01', effective_to: '', workshop_scope: 'HR', process_scope: 'ALL', source_note: '热轧默认单价' },
  { item_code: 'WATER_LEVELING', item_name: '拉矫水', unit: 't', unit_price: 4, effective_from: '2026-04-01', effective_to: '', workshop_scope: 'LJ', process_scope: 'leveling', source_note: '拉矫主线默认单价' },
  { item_code: 'D40', item_name: 'D40 包装材', unit: 'kg', unit_price: 9.5, effective_from: '2026-04-01', effective_to: '', workshop_scope: 'JZ,LJ', process_scope: 'packaging', source_note: '精整/拉矫默认单价' },
  { item_code: 'ALUMINUM_SLEEVE', item_name: '铝套筒', unit: 'kg', unit_price: 5, effective_from: '2026-04-01', effective_to: '', workshop_scope: 'LJ', process_scope: 'leveling', source_note: '拉矫主线默认单价' },
  { item_code: 'STEEL_BELT', item_name: '钢带', unit: 'kg', unit_price: 4.1, effective_from: '2026-04-01', effective_to: '', workshop_scope: 'LJ', process_scope: 'slitting', source_note: '拉矫大分切默认单价' },
  { item_code: 'STEEL_BUCKLE', item_name: '钢带扣', unit: 'kg', unit_price: 4.37, effective_from: '2026-04-01', effective_to: '', workshop_scope: 'LJ', process_scope: 'slitting', source_note: '拉矫大分切默认单价' },
  { item_code: 'THERMOCOUPLE', item_name: '热电偶', unit: 'm', unit_price: 17, effective_from: '2026-04-01', effective_to: '', workshop_scope: 'LJ', process_scope: 'anneal', source_note: '退火炉默认单价' },
  { item_code: 'ROLLING_OIL', item_name: '轧制油', unit: 'kg', unit_price: 8.2, effective_from: '2026-04-01', effective_to: '', workshop_scope: '2050,1650,1850,HWB,HR', process_scope: 'rolling', source_note: '损耗策略默认单价' },
  { item_code: 'WHITE_SOIL', item_name: '白土', unit: 'bag', unit_price: 39, effective_from: '2026-04-01', effective_to: '', workshop_scope: '2050,1650,1850,HWB', process_scope: 'loss', source_note: '损耗策略默认单价' },
  { item_code: 'DIATOMITE', item_name: '硅藻土', unit: 'bag', unit_price: 54, effective_from: '2026-04-01', effective_to: '', workshop_scope: '2050,1650,1850,HWB', process_scope: 'loss', source_note: '损耗策略默认单价' },
  { item_code: 'ROLLER_GUARANTEE', item_name: '辊系保障', unit: 'time', unit_price: 2000, effective_from: '2026-04-01', effective_to: '', workshop_scope: '2050,1650,1850', process_scope: 'support', source_note: '损耗策略默认单价' },
  { item_code: 'PATTERN_ROLLER_GUARANTEE', item_name: '花纹板辊系保障', unit: 'time', unit_price: 6000, effective_from: '2026-04-01', effective_to: '', workshop_scope: 'HWB', process_scope: 'support', source_note: '花纹板额外单价' },
  { item_code: 'PATTERN_ROLL_MATCHING', item_name: '花纹板配辊', unit: 'time', unit_price: 1000, effective_from: '2026-04-01', effective_to: '', workshop_scope: 'HWB', process_scope: 'support', source_note: '花纹板额外单价' },
  { item_code: 'FILTER_AGENT', item_name: '飞滤素', unit: 'kg', unit_price: 9, effective_from: '2026-04-01', effective_to: '', workshop_scope: 'HWB', process_scope: 'loss', source_note: '花纹板额外单价' },
  { item_code: 'STEAM', item_name: '蒸汽', unit: 't', unit_price: 0, effective_from: '2026-04-01', effective_to: '', workshop_scope: 'ALL', process_scope: 'utility', source_note: '预留价格主数据' },
  { item_code: 'AIR_ELECTRICITY', item_name: '空压机电耗', unit: 'kWh', unit_price: 0.8, effective_from: '2026-04-01', effective_to: '', workshop_scope: 'LJ', process_scope: 'utility', source_note: '公辅分摊默认单价' }
]

export const DEFAULT_PRICE_MASTER: Record<string, number> = Object.fromEntries(
  DEFAULT_PRICE_MASTER_ROWS.map((row) => [row.item_code, row.unit_price])
)

export type PriceOverride = {
  code: string
  unitPrice: number
}

export function resolvePriceSnapshot(overrides: PriceOverride[] = []): Record<string, number> {
  const resolved = { ...DEFAULT_PRICE_MASTER }
  for (const item of overrides) {
    const key = String(item.code || '').trim()
    if (!key) continue
    const unitPrice = Number(item.unitPrice)
    if (!Number.isFinite(unitPrice)) continue
    resolved[key] = unitPrice
  }
  return resolved
}

export function buildPriceRows(snapshot: Record<string, number>): Array<{ code: string; unitPrice: number }> {
  const masterByCode = new Map(DEFAULT_PRICE_MASTER_ROWS.map((row) => [row.item_code, row]))
  return Object.keys(snapshot)
    .sort((a, b) => a.localeCompare(b))
    .map((code) => {
      const master = masterByCode.get(code)
      return {
        code,
        item_code: code,
        item_name: master?.item_name || code,
        unit: master?.unit || '',
        unitPrice: Number(snapshot[code]),
        unit_price: Number(snapshot[code]),
        effective_from: master?.effective_from || '',
        effective_to: master?.effective_to || '',
        workshop_scope: master?.workshop_scope || 'CUSTOM',
        process_scope: master?.process_scope || 'CUSTOM',
        source_note: master?.source_note || '场景覆盖价'
      }
    })
}
