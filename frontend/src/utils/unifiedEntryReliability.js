const TARGET_URLS = Object.freeze({
  coil_entry: '/mobile/coil-entry',
  owner_daily: '/mobile/owner-daily',
  shift_report: '/mobile/report/submit',
})

function hasMeaningfulValue(value) {
  if (value === null || value === undefined || value === false) return false
  if (typeof value === 'string') return value.trim() !== ''
  if (Array.isArray(value)) return value.some(hasMeaningfulValue)
  if (typeof value === 'object') return Object.values(value).some(hasMeaningfulValue)
  return true
}

export function filterEntryGroups(groups, requestedFields, dependencyFields = []) {
  const requested = new Set([...(requestedFields || []), ...(dependencyFields || [])])
  if (!requested.size) return groups || []
  return (groups || [])
    .map((group) => ({
      ...group,
      fields: (group.fields || []).filter((field) => requested.has(field.name)),
    }))
    .filter((group) => group.fields.length)
}

export function buildEntryRetryRecord({ submitTarget, payload, draftKey }) {
  const url = TARGET_URLS[submitTarget]
  if (!url) throw new Error(`unsupported submit target: ${submitTarget}`)
  return {
    type: 'http',
    method: 'post',
    url,
    body: payload,
    dedupeKey: `unified-entry:${submitTarget}:${draftKey}`,
    clearDraftKey: draftKey,
  }
}

export function isMeaningfulEntryDraft(snapshot) {
  return hasMeaningfulValue(snapshot?.form)
}
