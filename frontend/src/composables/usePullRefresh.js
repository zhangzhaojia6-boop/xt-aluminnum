import { ref, onMounted, onUnmounted } from 'vue'

/**
 * Mobile Pull-to-Refresh Composable
 * Handles touch gestures to trigger data reloading with industrial animation
 */
export function usePullRefresh(onRefresh) {
  const pulling = ref(false)
  const pullDistance = ref(0)
  const refreshing = ref(false)
  const THRESHOLD = 80

  let startY = 0

  const handleTouchStart = (e) => {
    if (window.scrollY > 0 || refreshing.value) return
    startY = e.touches[0].pageY
    pulling.value = true
  }

  const handleTouchMove = (e) => {
    if (!pulling.value) return
    const currentY = e.touches[0].pageY
    const diff = currentY - startY
    if (diff > 0) {
      // Apply resistance
      pullDistance.value = Math.min(diff * 0.5, THRESHOLD + 20)
      if (diff > 20) {
        e.preventDefault()
      }
    }
  }

  const handleTouchEnd = async () => {
    if (!pulling.value) return
    pulling.value = false
    
    if (pullDistance.value >= THRESHOLD) {
      refreshing.value = true
      pullDistance.value = THRESHOLD
      try {
        await onRefresh()
      } finally {
        refreshing.value = false
        pullDistance.value = 0
      }
    } else {
      pullDistance.value = 0
    }
  }

  onMounted(() => {
    window.addEventListener('touchstart', handleTouchStart, { passive: false })
    window.addEventListener('touchmove', handleTouchMove, { passive: false })
    window.addEventListener('touchend', handleTouchEnd)
  })

  onUnmounted(() => {
    window.removeEventListener('touchstart', handleTouchStart)
    window.removeEventListener('touchmove', handleTouchMove)
    window.removeEventListener('touchend', handleTouchEnd)
  })

  return {
    pullDistance,
    refreshing
  }
}
