import { ref, onMounted, onUnmounted } from 'vue'

/**
 * Focus Trap Composable
 * Traps tab focus within a specific element (e.g., Modals)
 */
export function useFocusTrap(targetRef) {
  const handleKeyDown = (e) => {
    if (e.key !== 'Tab' || !targetRef.value) return

    const focusableElements = targetRef.value.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    )
    const firstElement = focusableElements[0]
    const lastElement = focusableElements[focusableElements.length - 1]

    if (e.shiftKey) {
      if (document.activeElement === firstElement) {
        lastElement.focus()
        e.preventDefault()
      }
    } else {
      if (document.activeElement === lastElement) {
        firstElement.focus()
        e.preventDefault()
      }
    }
  }

  onMounted(() => {
    window.addEventListener('keydown', handleKeyDown)
  })

  onUnmounted(() => {
    window.removeEventListener('keydown', handleKeyDown)
  })
}
