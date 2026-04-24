export function clampSwipeOffset({ offset, min, max }) {
  if (offset > max) return Math.round((offset - max) * 0.4)
  if (offset < min) return min + Math.round((offset - min) * 0.4)
  return offset
}

export function resolveSwipeSnapIndex({ currentIndex, deltaX, pageWidth, pageCount }) {
  const safePageWidth = Math.max(Number(pageWidth) || 0, 1)
  const threshold = Math.max(48, safePageWidth * 0.18)
  if (deltaX <= -threshold) return Math.min(currentIndex + 1, pageCount - 1)
  if (deltaX >= threshold) return Math.max(currentIndex - 1, 0)
  return currentIndex
}
