import { onBeforeUnmount, ref } from 'vue'
import { SUBMIT_COOLDOWN_MS } from '../utils/submitGuard.js'

export function useSubmitCooldown() {
  const lastSubmitTime = ref(0)
  const submitCooldownActive = ref(false)
  let timer = null

  function clearCooldownTimer() {
    if (timer) {
      clearTimeout(timer)
      timer = null
    }
  }

  function startCooldown() {
    lastSubmitTime.value = Date.now()
    submitCooldownActive.value = true
    clearCooldownTimer()
    timer = setTimeout(() => {
      submitCooldownActive.value = false
      timer = null
    }, SUBMIT_COOLDOWN_MS)
  }

  onBeforeUnmount(() => clearCooldownTimer())

  return {
    lastSubmitTime,
    submitCooldownActive,
    startCooldown,
    clearCooldownTimer,
  }
}
