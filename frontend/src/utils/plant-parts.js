// 把平面图上的块换算成厂房部件（世界坐标，1 像素 = 0.1）。纯函数，不依赖 three，方便单测。
import { PLAN_SIZE } from './factory-layout.js'

export const UNIT = 0.1
const GAP = 0.6
const WORKSHOP_WALL = 2.2
const ANNEX_WALL = 1.3
const PLINTH = 0.25
const EAVE = 0.15
const ROOF_PITCH = Math.tan((8 * Math.PI) / 180)
const BAR_SCALE = 0.12

export function toWorld(rect, plan = PLAN_SIZE) {
  return {
    cx: (rect.x + rect.w / 2 - plan.width / 2) * UNIT,
    cz: (rect.y + rect.h / 2 - plan.height / 2) * UNIT,
    w: rect.w * UNIT,
    d: rect.h * UNIT
  }
}

// 厂房外形固定；吨数只体现在屋顶上方的数据柱上（用户 11/10 决定）。
export function buildingParts(block, plan = PLAN_SIZE) {
  const { cx, cz, w: rawW, d: rawD } = toWorld(block, plan)
  const w = Math.max(rawW - GAP, 0.4)
  const d = Math.max(rawD - GAP, 0.4)
  const alongX = w >= d
  const length = alongX ? w : d
  const span = alongX ? d : w
  const wallH = block.isWorkshop ? WORKSHOP_WALL : ANNEX_WALL
  const rise = Math.max((span / 2) * ROOF_PITCH, 0.12)
  const ridgeY = wallH + rise

  const windowLen = length * 0.86
  const windowY = wallH * 0.58
  const windowOffset = span / 2 + 0.02
  const windows = [-1, 1].map((side) => (alongX
    ? { cx, cz: cz + side * windowOffset, w: windowLen, d: 0.04, y: windowY, h: 0.26 }
    : { cx: cx + side * windowOffset, cz, w: 0.04, d: windowLen, y: windowY, h: 0.26 }))

  const ventCount = block.isWorkshop ? Math.max(Math.floor(length / 2.6), 1) : 0
  const vents = Array.from({ length: ventCount }, (_, i) => {
    const t = ventCount === 1 ? 0 : (i / (ventCount - 1) - 0.5) * length * 0.78
    return alongX ? { x: cx + t, z: cz, y: ridgeY } : { x: cx, z: cz + t, y: ridgeY }
  })

  const barWidth = Math.min(Math.max(length / 10, 0.45), 1.1)
  const bar = block.isWorkshop && block.hasData
    ? { cx, cz, y: ridgeY, w: barWidth, d: barWidth, h: Math.max(block.height * BAR_SCALE, 0.3) }
    : null

  return {
    key: block.key,
    alongX,
    wall: { cx, cz, w, d, y: 0, h: wallH },
    plinth: { cx, cz, w: w + 0.04, d: d + 0.04, y: 0, h: PLINTH },
    roof: { cx, cz, y: wallH, w: w + EAVE * 2, d: d + EAVE * 2, rise, alongX },
    skylight: block.isWorkshop
      ? (alongX
        ? { cx, cz, y: ridgeY, w: length * 0.9, d: span / 6, h: 0.05 }
        : { cx, cz, y: ridgeY, w: span / 6, d: length * 0.9, h: 0.05 })
      : null,
    windows,
    vents,
    bar,
    labelY: bar ? bar.y + bar.h + 0.4 : ridgeY + 0.6
  }
}

export function siteRects(rects = [], plan = PLAN_SIZE) {
  return rects.map((rect) => ({ ...toWorld(rect, plan), rect }))
}
