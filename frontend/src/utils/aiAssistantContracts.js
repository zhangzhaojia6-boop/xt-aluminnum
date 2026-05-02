function list(value) {
  return Array.isArray(value) ? value : []
}

export function normalizeAssistantAnswer(value = {}) {
  return {
    answer: value.answer || '',
    confidence: value.confidence || 'low',
    evidenceRefs: list(value.evidence_refs || value.evidenceRefs),
    missingData: list(value.missing_data || value.missingData),
    recommendedNextActions: list(value.recommended_next_actions || value.recommendedNextActions),
    canCreateWatch: Boolean(value.can_create_watch ?? value.canCreateWatch)
  }
}

export function normalizeBriefing(value = {}) {
  const payload = value.payload || {}
  const rules = list(payload.rules_fired || payload.rulesFired)
  const evidenceCount = rules.reduce((total, rule) => {
    return total + list(rule.evidence_refs || rule.evidenceRefs).length
  }, 0)
  return {
    id: value.id || '',
    type: value.briefing_type || value.type || '',
    severity: value.severity || 'info',
    title: value.title || '',
    payload,
    read: Boolean(value.read),
    followUpStatus: value.follow_up_status || value.followUpStatus || 'none',
    evidenceCount,
    expiresAt: value.expires_at || value.expiresAt || '',
    scopeKey: value.scope_key || value.scopeKey || '',
    deliverySuppressed: Boolean(value.delivery_suppressed ?? value.deliverySuppressed)
  }
}

export function normalizeWatchlistItem(value = {}) {
  return {
    id: value.id || '',
    type: value.watch_type || value.type || '',
    scopeKey: value.scope_key || value.scopeKey || '',
    triggerRules: list(value.trigger_rules || value.triggerRules),
    quietHours: value.quiet_hours || value.quietHours || null,
    frequency: value.frequency || 'hourly',
    channels: list(value.channels).length ? list(value.channels) : ['in_app'],
    active: Boolean(value.active)
  }
}
