export const SLOTS = [
  { slot: 'production', label: '生产异常', unit: '件', field: 'production_exception_count', domain: 'production' },
  { slot: 'reconciliation', label: '对账未结', unit: '条', field: 'reconciliation_open_count', domain: 'reconciliation' },
  { slot: 'unreported', label: '未填报班次', unit: '个', field: 'unreported_shift_count', domain: 'reporting' }
]

export function buildKeyEvents(lane = {}) {
  return SLOTS.map((s) => {
    const count = Number(lane?.[s.field] || 0)
    return { ...s, count, active: count > 0 }
  })
}

export function hasAnyEvent(lane = {}) {
  return SLOTS.some((s) => Number(lane?.[s.field] || 0) > 0)
}
