export const ACTIVE_WORKSHOP_NAMES = [
  '铸锭',
  '铸二',
  '铸三',
  '热轧',
  '淬火车间',
  '精整',
  '拉矫',
  '园区剪切',
  '新厂在线',
  '园区在线',
  '冷轧1650',
  '冷轧1850',
  '冷轧2050',
]

const ACTIVE_WORKSHOP_SET = new Set(ACTIVE_WORKSHOP_NAMES)

const RETIRED_WORKSHOP_NAMES = new Set([
  '冷轧三车间',
  '二分厂精整车间',
])

const WORKSHOP_ALIASES = new Map([
  ['铸锭分厂', '铸锭'],
  ['铸锭车间', '铸锭'],
  ['铸锭', '铸锭'],
  ['铸轧二', '铸二'],
  ['铸轧二车间', '铸二'],
  ['铸二车间', '铸二'],
  ['铸二', '铸二'],
  ['铸轧三', '铸三'],
  ['铸轧三车间', '铸三'],
  ['铸三车间', '铸三'],
  ['铸三', '铸三'],
  ['热轧2050', '热轧'],
  ['热轧2050车间', '热轧'],
  ['热轧车间', '热轧'],
  ['热轧', '热轧'],
  ['淬火', '淬火车间'],
  ['淬火车间', '淬火车间'],
  ['园区淬火', '淬火车间'],
  ['园区淬火车间', '淬火车间'],
  ['精整车间', '精整'],
  ['冷轧精整车间', '精整'],
  ['园区精整', '精整'],
  ['精整', '精整'],
  ['拉矫车间', '拉矫'],
  ['拉矫', '拉矫'],
  ['剪切车间', '园区剪切'],
  ['园区剪切车间', '园区剪切'],
  ['园区剪切', '园区剪切'],
  ['新厂在线退火', '新厂在线'],
  ['新厂在线车间', '新厂在线'],
  ['新厂在线', '新厂在线'],
  ['园区在线退火', '园区在线'],
  ['园区在线车间', '园区在线'],
  ['园区在线', '园区在线'],
  ['1650冷轧', '冷轧1650'],
  ['1650冷轧车间', '冷轧1650'],
  ['1650车间', '冷轧1650'],
  ['冷轧1650', '冷轧1650'],
  ['冷轧1650车间', '冷轧1650'],
  ['1850冷轧', '冷轧1850'],
  ['1850冷轧车间', '冷轧1850'],
  ['1850车间', '冷轧1850'],
  ['冷轧1850', '冷轧1850'],
  ['冷轧1850车间', '冷轧1850'],
  ['2050冷轧', '冷轧2050'],
  ['2050冷轧车间', '冷轧2050'],
  ['2050车间', '冷轧2050'],
  ['冷轧2050', '冷轧2050'],
  ['冷轧2050车间', '冷轧2050'],
])

function rawWorkshopName(row = {}) {
  return String(row.workshop || row.workshop_name || row.workshopName || row.name || '').trim()
}

export function normalizeWorkshopName(value) {
  const name = String(value || '').trim()
  return WORKSHOP_ALIASES.get(name) || name
}

export function isRetiredWorkshopName(value) {
  return RETIRED_WORKSHOP_NAMES.has(String(value || '').trim())
}

export function isActiveWorkshopName(value) {
  const name = String(value || '').trim()
  if (!name || isRetiredWorkshopName(name)) return false
  return ACTIVE_WORKSHOP_SET.has(normalizeWorkshopName(name))
}

export function filterActiveWorkshopRows(rows = []) {
  return (rows || []).reduce((activeRows, row) => {
    const rawName = rawWorkshopName(row)
    if (!isActiveWorkshopName(rawName)) return activeRows
    if (row.is_active === false || row.is_removed === true || row.removed === true) return activeRows
    const status = String(row.status || row.workshop_status || '').toLowerCase()
    if (status === 'removed') return activeRows

    const normalizedName = normalizeWorkshopName(rawName)
    const normalizedRow = { ...row }
    if ('name' in normalizedRow) normalizedRow.name = normalizedName
    if ('workshop' in normalizedRow) normalizedRow.workshop = normalizedName
    if ('workshop_name' in normalizedRow) normalizedRow.workshop_name = normalizedName
    if ('workshopName' in normalizedRow) normalizedRow.workshopName = normalizedName
    activeRows.push(normalizedRow)
    return activeRows
  }, [])
}
