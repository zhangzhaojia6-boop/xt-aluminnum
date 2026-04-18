import { computed, onBeforeUnmount, ref, watch } from 'vue'

function normalizeSegment(value) {
  const text = String(value ?? '').trim()
  return text ? text.toUpperCase() : ''
}

function readDraftStorageEntries() {
  if (typeof localStorage === 'undefined') return []
  return Object.keys(localStorage)
    .filter((key) => key.startsWith('draft:'))
    .map((key) => {
      try {
        const payload = JSON.parse(localStorage.getItem(key) || 'null')
        return {
          key,
          savedAt: payload?.saved_at || '',
          payload
        }
      } catch {
        return null
      }
    })
    .filter(Boolean)
}

function formatAutoSavedLabel(savedAt) {
  if (!savedAt) return ''
  const parsed = new Date(savedAt)
  if (Number.isNaN(parsed.getTime())) return '已自动暂存'
  return `已自动暂存 ${parsed.toLocaleTimeString('zh-CN', { hour12: false })}`
}

function formatSavedAtText(savedAt) {
  const label = formatAutoSavedLabel(savedAt)
  return label.replace(/^已自动暂存\s*/, '')
}

function hasMeaningfulValue(value) {
  if (value === null || value === undefined) return false
  if (typeof value === 'string') return value.trim() !== ''
  if (Array.isArray(value)) return value.some(hasMeaningfulValue)
  if (typeof value === 'object') return Object.values(value).some(hasMeaningfulValue)
  return true
}

export function buildDynamicDraftKey({ workshopId, shiftId, businessDate, trackingCardNo, machineId }) {
  return `draft:${normalizeSegment(workshopId)}:${normalizeSegment(shiftId)}:${normalizeSegment(businessDate)}:${normalizeSegment(machineId)}:${normalizeSegment(trackingCardNo)}`
}

export function findRestorableDraftKey(entries, scope) {
  const exactKey = buildDynamicDraftKey(scope)
  const exactMatch = entries.find((item) => item.key === exactKey)
  if (exactMatch) return exactMatch.key

  const prefix = buildDynamicDraftKey({ ...scope, trackingCardNo: '', machineId: scope.machineId ?? '' })
  const candidates = entries
    .filter((item) => item.key.startsWith(prefix))
    .sort((left, right) => String(right.savedAt || '').localeCompare(String(left.savedAt || '')))
  return candidates[0]?.key || ''
}

export function useLocalDraft({
  scope,
  snapshot,
  applyDraft,
  enabled = ref(true),
  isMeaningful = hasMeaningfulValue
}) {
  const restoreDialogVisible = ref(false)
  const restoreDraftPayload = ref(null)
  const restoreDraftSavedAt = ref('')
  const autoSavedLabel = ref('')
  const currentDraftKey = computed(() => buildDynamicDraftKey(scope.value))

  let autosaveTimer = null
  let suspended = false
  let lastSavedKey = ''

  function clearAutosaveTimer() {
    if (autosaveTimer) {
      clearTimeout(autosaveTimer)
      autosaveTimer = null
    }
  }

  function persistSnapshot() {
    if (typeof localStorage === 'undefined' || !enabled.value || suspended) return
    const currentSnapshot = snapshot.value
    if (!isMeaningful(currentSnapshot)) {
      if (lastSavedKey) {
        localStorage.removeItem(lastSavedKey)
        lastSavedKey = ''
      }
      autoSavedLabel.value = ''
      return
    }

    const draftKey = currentDraftKey.value
    const savedAt = new Date().toISOString()
    if (lastSavedKey && lastSavedKey !== draftKey) {
      localStorage.removeItem(lastSavedKey)
    }
    localStorage.setItem(
      draftKey,
      JSON.stringify({
        saved_at: savedAt,
        data: currentSnapshot
      })
    )
    lastSavedKey = draftKey
    autoSavedLabel.value = formatAutoSavedLabel(savedAt)
  }

  function schedulePersist() {
    if (!enabled.value || suspended) return
    clearAutosaveTimer()
    autosaveTimer = setTimeout(() => {
      persistSnapshot()
      autosaveTimer = null
    }, 500)
  }

  function checkForRestorableDraft() {
    if (typeof localStorage === 'undefined') return
    const entries = readDraftStorageEntries()
    const matchedKey = findRestorableDraftKey(entries, scope.value)
    if (!matchedKey) return
    const matchedEntry = entries.find((item) => item.key === matchedKey)
    if (!matchedEntry?.payload?.data || !isMeaningful(matchedEntry.payload.data)) {
      localStorage.removeItem(matchedKey)
      return
    }
    restoreDraftPayload.value = matchedEntry.payload.data
    restoreDraftSavedAt.value = formatSavedAtText(matchedEntry.savedAt || '')
    lastSavedKey = matchedKey
    restoreDialogVisible.value = true
  }

  function restoreDraft() {
    if (!restoreDraftPayload.value) return
    suspended = true
    applyDraft(restoreDraftPayload.value)
    autoSavedLabel.value = restoreDraftSavedAt.value ? `已自动暂存 ${restoreDraftSavedAt.value}` : ''
    restoreDialogVisible.value = false
    setTimeout(() => {
      suspended = false
    }, 0)
  }

  function discardDraft() {
    if (lastSavedKey) {
      localStorage.removeItem(lastSavedKey)
      lastSavedKey = ''
    }
    restoreDraftPayload.value = null
    restoreDraftSavedAt.value = ''
    restoreDialogVisible.value = false
    autoSavedLabel.value = ''
  }

  function clearDraft(key = currentDraftKey.value) {
    if (typeof localStorage === 'undefined') return
    if (key) {
      localStorage.removeItem(key)
    }
    if (lastSavedKey === key || !key) {
      lastSavedKey = ''
    }
    restoreDraftPayload.value = null
    restoreDraftSavedAt.value = ''
    autoSavedLabel.value = ''
  }

  watch([scope, snapshot, enabled], schedulePersist, { deep: true })

  onBeforeUnmount(() => {
    clearAutosaveTimer()
  })

  return {
    autoSavedLabel,
    checkForRestorableDraft,
    clearDraft,
    currentDraftKey,
    discardDraft,
    restoreDialogVisible,
    restoreDraft,
    restoreDraftSavedAt
  }
}
