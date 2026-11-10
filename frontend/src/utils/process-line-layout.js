// 实时页 3D 产线：工序节点从左到右一字排开，中间用平条连起来。
export const LINE_PLAN = { width: 700, height: 160 }

const NODE_W = 80
const NODE_H = 60
const GAP = 34
const MIN_HEIGHT = 10
const MAX_HEIGHT = 45
const FLAT_HEIGHT = 3

// items: buildLiveProcessFlowItems 的结果（key、stage、output、valueText）。
// 高度按全线最大吨数缩放；没有可信产量画平块，不画 0。
export function buildProcessLineBlocks(items = []) {
  const count = items.length
  const span = count * NODE_W + Math.max(count - 1, 0) * GAP
  const left = (LINE_PLAN.width - span) / 2
  const top = (LINE_PLAN.height - NODE_H) / 2
  const max = Math.max(0, ...items.map((item) => (item.output == null ? 0 : Number(item.output) || 0)))

  const blocks = []
  items.forEach((item, index) => {
    const x = left + index * (NODE_W + GAP)
    const tons = item.output == null ? null : Number(item.output)
    const hasData = tons != null && Number.isFinite(tons)
    blocks.push({
      key: item.key,
      label: item.stage,
      valueText: item.valueText,
      x,
      y: top,
      w: NODE_W,
      h: NODE_H,
      isWorkshop: true,
      workshopId: null,
      tons: hasData ? tons : null,
      hasData,
      height: hasData && max > 0 ? MIN_HEIGHT + (MAX_HEIGHT - MIN_HEIGHT) * (tons / max) : hasData ? MIN_HEIGHT : FLAT_HEIGHT
    })
    if (index < count - 1) {
      blocks.push({
        key: `link-${item.key}`,
        label: '',
        x: x + NODE_W,
        y: top + NODE_H / 2 - 6,
        w: GAP,
        h: 12,
        isWorkshop: false,
        workshopId: null,
        tons: null,
        hasData: false,
        height: 1
      })
    }
  })
  return blocks
}
