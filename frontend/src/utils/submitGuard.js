export const SUBMIT_COOLDOWN_MS = 3000

export function isWithinSubmitCooldown(lastSubmitTime, now = Date.now(), cooldownMs = SUBMIT_COOLDOWN_MS) {
  const startedAt = Number(lastSubmitTime || 0)
  if (!startedAt) return false
  return now - startedAt < cooldownMs
}

export function remainingSubmitCooldown(lastSubmitTime, now = Date.now(), cooldownMs = SUBMIT_COOLDOWN_MS) {
  const startedAt = Number(lastSubmitTime || 0)
  if (!startedAt) return 0
  return Math.max(0, cooldownMs - (now - startedAt))
}
