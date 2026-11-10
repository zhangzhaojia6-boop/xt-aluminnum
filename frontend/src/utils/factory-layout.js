// 新厂平面图（约 935×570，左上为原点），按用户 2026-11-10 提供的厂区平面图转录。
export const PLAN_SIZE = { width: 935, height: 570 }

// name 是车间表里的正式名称；没有 name 的是不出产量的建筑。
export const FACTORY_BLOCKS = [
  { key: 'RZ', name: '热轧', process: 'hot_roll', x: 60, y: 30, w: 200, h: 130 },
  { key: 'LZ1850', name: '1850冷轧', process: 'cold_roll', x: 266, y: 30, w: 210, h: 130 },
  { key: 'LZ1650', name: '1650冷轧', process: 'cold_roll', x: 482, y: 30, w: 56, h: 130 },
  { key: 'ZR5', name: '铸轧五', label: '铸五', process: 'casting', x: 544, y: 30, w: 201, h: 130 },
  { key: 'ZR2', name: '铸轧二', process: 'casting', x: 60, y: 205, w: 280, h: 54 },
  { key: 'LZ2050', name: '2050冷轧', process: 'cold_roll', x: 60, y: 264, w: 280, h: 54 },
  { key: 'JZ', name: '精整车间', label: '精整', process: 'finishing', x: 60, y: 323, w: 280, h: 54 },
  { key: 'repair', label: '大修/机加工', x: 60, y: 382, w: 280, h: 58 },
  { key: 'ZR6', name: '铸轧六', label: '铸六', process: 'casting', x: 390, y: 205, w: 235, h: 54 },
  { key: 'ZXTF-N', name: '新厂在线退火', label: '退火', process: 'annealing', x: 390, y: 264, w: 235, h: 54 },
  { key: 'LJ', name: '拉矫车间', label: '拉矫', process: 'straightening', x: 390, y: 323, w: 235, h: 54 },
  { key: 'CT', name: '彩涂', process: 'coating', x: 390, y: 382, w: 235, h: 58 },
  { key: 'ZD', name: '铸锭分厂', label: '铸锭', process: 'casting', x: 670, y: 205, w: 90, h: 115 },
  { key: 'ZR3', name: '铸轧三', process: 'casting', x: 770, y: 205, w: 90, h: 115 },
  { key: 'office', label: '办公楼', x: 670, y: 340, w: 190, h: 100 }
]

const MIN_HEIGHT = 10
const MAX_HEIGHT = 45
const FLAT_HEIGHT = 3

function tonsOf(row) {
  if (row?.total_output == null) return null
  const value = Number(row.total_output)
  return Number.isFinite(value) ? value : null
}

// rows: useDashboardSnapshot().productionLane（workshop_id、workshop_name、total_output）。
// 高度按工序分组各自缩放：不同工序的吨数不可比。没有数据画平块，不画 0。
export function buildFactoryModel(rows = []) {
  const byName = new Map(rows.map((row) => [row.workshop_name, row]))
  const placed = new Set()

  const blocks = FACTORY_BLOCKS.map((block) => {
    const row = block.name ? byName.get(block.name) : null
    if (row) placed.add(block.name)
    const tons = tonsOf(row)
    return {
      ...block,
      label: block.label || block.name,
      workshopId: row?.workshop_id ?? null,
      isWorkshop: Boolean(block.name),
      tons,
      hasData: tons != null
    }
  })

  const groupMax = new Map()
  for (const block of blocks) {
    if (!block.hasData) continue
    groupMax.set(block.process, Math.max(groupMax.get(block.process) || 0, block.tons))
  }
  for (const block of blocks) {
    const max = groupMax.get(block.process)
    block.height = block.hasData && max > 0
      ? MIN_HEIGHT + (MAX_HEIGHT - MIN_HEIGHT) * (block.tons / max)
      : block.hasData ? MIN_HEIGHT : FLAT_HEIGHT
  }

  const offMap = rows
    .filter((row) => !placed.has(row.workshop_name))
    .map((row) => ({ name: row.workshop_name, workshopId: row.workshop_id ?? null, tons: tonsOf(row) }))

  return { blocks, offMap }
}

export function formatTons(tons) {
  if (tons == null) return '—'
  return Number(tons).toLocaleString('zh-CN', { maximumFractionDigits: 1 })
}
