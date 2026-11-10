// 环形进度：只接真实比例；没有数据不画弧，超过 100% 弧画满但数字照实显示。
export const RING_CIRCUMFERENCE = 2 * Math.PI * 20

export function ringArc(ratio) {
  const value = ratio == null || ratio === '' ? NaN : Number(ratio)
  if (!Number.isFinite(value) || value < 0) return { hasArc: false, dash: `0 ${RING_CIRCUMFERENCE}` }
  const filled = Math.min(value, 1) * RING_CIRCUMFERENCE
  return { hasArc: true, dash: `${filled.toFixed(2)} ${RING_CIRCUMFERENCE.toFixed(2)}` }
}

// 实时连接状态 → 呼吸点状态
export function pulseState(tone) {
  if (tone === 'success') return 'live'
  if (tone === 'danger') return 'offline'
  return 'stale'
}
