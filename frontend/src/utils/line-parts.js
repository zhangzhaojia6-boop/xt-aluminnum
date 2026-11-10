// 实时页 3D 产线：每道工序拼成一台可辨认的简化设备，工序间用辊道连接。纯函数，不依赖 three。
export const STATION_GAP = 10
const MIN_BAR = 0.6
const MAX_BAR = 5

const box = (mat, cx, cy, cz, w, h, d) => ({ kind: 'box', mat, cx, cy, cz, w, h, d })
const roll = (mat, cx, cy, cz, r, len) => ({ kind: 'roll', mat, cx, cy, cz, r, len })

// 每种设备以站点中心为原点，x 沿产线方向，z 朝向观众
const EQUIPMENT = {
  casting: () => [
    box('furnace', -2.2, 1.1, 0, 2.6, 2.2, 2.6),
    box('glow', -2.2, 0.9, 1.31, 1.2, 0.18, 0.02),
    box('housing', 0.6, 1.1, -1.1, 0.5, 2.2, 0.3),
    box('housing', 0.6, 1.1, 1.1, 0.5, 2.2, 0.3),
    roll('roll', 0.6, 1.3, 0, 0.42, 2.0),
    roll('roll', 0.6, 0.45, 0, 0.42, 2.0)
  ],
  'hot-rolling': () => millStand(0),
  'cold-rolling': () => [...millStand(-1.3), ...millStand(1.3)],
  annealing: () => [
    box('furnace', 0, 1.0, 0, 5.4, 2.0, 2.4),
    box('glow', 0, 0.5, 1.21, 4.6, 0.12, 0.02),
    box('housing', 0, 2.1, 0, 5.6, 0.2, 2.6)
  ],
  finishing: () => [
    box('table', 0, 0.45, 0, 3.6, 0.9, 1.8),
    box('housing', 0.4, 1.4, 0, 0.5, 1.2, 2.0),
    box('glow', 0.4, 0.95, 1.01, 0.4, 0.06, 0.02)
  ],
  packaging: () => [
    box('table', 0, 0.12, 0, 3.4, 0.24, 2.2),
    roll('coil', -0.8, 0.84, -0.5, 0.6, 0.8),
    roll('coil', 0.8, 0.84, -0.5, 0.6, 0.8),
    roll('coil', -0.8, 0.84, 0.5, 0.6, 0.8),
    roll('coil', 0.8, 0.84, 0.5, 0.6, 0.8),
    roll('coil', 0, 1.9, 0, 0.6, 0.8)
  ]
}

function millStand(dx) {
  return [
    box('housing', dx, 1.5, -1.1, 0.6, 3.0, 0.3),
    box('housing', dx, 1.5, 1.1, 0.6, 3.0, 0.3),
    box('housing', dx, 3.05, 0, 0.7, 0.2, 2.6),
    roll('roll', dx, 2.15, 0, 0.36, 1.9),
    roll('roll', dx, 1.45, 0, 0.22, 1.9),
    roll('roll', dx, 1.0, 0, 0.22, 1.9),
    roll('roll', dx, 0.3, 0, 0.36, 1.9)
  ]
}

function genericStation() {
  return [box('housing', 0, 0.9, 0, 2.4, 1.8, 2.0)]
}

// items: buildLiveProcessFlowItems 的结果（key、stage、output、valueText）
export function buildLineParts(items = []) {
  const count = items.length
  const start = -((count - 1) * STATION_GAP) / 2
  const max = Math.max(0, ...items.map((item) => (item.output == null ? 0 : Number(item.output) || 0)))
  const parts = []
  const stations = []

  items.forEach((item, index) => {
    const x = start + index * STATION_GAP
    for (const part of (EQUIPMENT[item.key] || genericStation)()) {
      parts.push({ ...part, cx: part.cx + x })
    }
    const tons = item.output == null ? null : Number(item.output)
    const hasData = tons != null && Number.isFinite(tons)
    const barH = hasData && max > 0 ? MIN_BAR + (MAX_BAR - MIN_BAR) * (tons / max) : null
    stations.push({
      key: item.key,
      label: item.stage,
      valueText: item.valueText,
      x,
      hasData,
      bar: barH == null ? null : { cx: x, cz: -2.6, w: 0.7, d: 0.7, y: 0, h: barH },
      labelY: Math.max(barH ?? 0, 3.4) + 0.8
    })
  })

  const span = count > 0 ? (count - 1) * STATION_GAP + 6 : 0
  const conveyor = count > 0 ? { cx: 0, cy: 0.18, cz: 0, w: span, h: 0.12, d: 1.6 } : null
  const rollers = []
  for (let x = -span / 2 + 0.4; conveyor && x <= span / 2 - 0.4; x += 0.8) rollers.push({ x })

  return {
    parts,
    stations,
    conveyor,
    rollers,
    coilPath: conveyor ? { from: -span / 2 + 0.6, to: span / 2 - 0.6, y: 0.9 } : null,
    hasAnyData: stations.some((station) => station.hasData)
  }
}
