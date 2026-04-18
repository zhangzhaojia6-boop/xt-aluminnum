import { readonly, ref } from 'vue'

const DB_NAME = 'aluminum-bypass-mobile'
const DB_VERSION = 1
const STORE_NAME = 'pending_requests'
const pendingCount = ref(0)
const syncing = ref(false)

let dbPromise = null
let onlineListenerBound = false
let refreshScheduled = false

function nowIso() {
  return new Date().toISOString()
}

function buildUuid() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return `req-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function requestConfig() {
  return { skipErrorToast: true }
}

async function loadApiModules() {
  const [{ api }, attendanceApi, mobileApi] = await Promise.all([
    import('../api/index.js'),
    import('../api/attendance.js'),
    import('../api/mobile.js')
  ])
  return {
    api,
    submitAttendanceConfirmation: attendanceApi.submitAttendanceConfirmation,
    createWorkOrder: mobileApi.createWorkOrder,
    createWorkOrderEntry: mobileApi.createWorkOrderEntry,
    findWorkOrderByTrackingCard: mobileApi.findWorkOrderByTrackingCard,
    submitWorkOrderEntry: mobileApi.submitWorkOrderEntry,
    updateWorkOrder: mobileApi.updateWorkOrder,
    updateWorkOrderEntry: mobileApi.updateWorkOrderEntry,
    verifyOcrFields: mobileApi.verifyOcrFields
  }
}

export function isRetryableNetworkError(error) {
  if (error?.response) return false
  return ['ERR_NETWORK', 'ECONNABORTED'].includes(error?.code) || /network error/i.test(String(error?.message || ''))
}

function canUseIndexedDb() {
  return typeof indexedDB !== 'undefined'
}

async function openDatabase() {
  if (!canUseIndexedDb()) return null
  if (dbPromise) return dbPromise
  dbPromise = new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION)
    request.onupgradeneeded = () => {
      const db = request.result
      if (!db.objectStoreNames.contains(STORE_NAME)) {
        db.createObjectStore(STORE_NAME, { keyPath: 'id' })
      }
    }
    request.onsuccess = () => resolve(request.result)
    request.onerror = () => reject(request.error)
  })
  return dbPromise
}

async function withStore(mode, action) {
  const db = await openDatabase()
  if (!db) return null
  return new Promise((resolve, reject) => {
    const transaction = db.transaction(STORE_NAME, mode)
    const store = transaction.objectStore(STORE_NAME)
    const request = action(store)
    transaction.oncomplete = () => resolve(request?.result ?? null)
    transaction.onerror = () => reject(transaction.error || request?.error)
    transaction.onabort = () => reject(transaction.error || request?.error)
  })
}

async function listPendingRecords() {
  const rows = await withStore('readonly', (store) => store.getAll())
  return (rows || []).sort((left, right) => String(left.createdAt || '').localeCompare(String(right.createdAt || '')))
}

async function savePendingRecord(record) {
  return withStore('readwrite', (store) => store.put(record))
}

async function deletePendingRecord(id) {
  return withStore('readwrite', (store) => store.delete(id))
}

function schedulePendingCountRefresh() {
  if (refreshScheduled) return
  refreshScheduled = true
  setTimeout(async () => {
    refreshScheduled = false
    pendingCount.value = (await listPendingRecords())?.length || 0
  }, 0)
}

function serializeFormDataEntries(entries = []) {
  return entries.map((entry) => ({
    key: entry.key,
    kind: entry.kind || 'text',
    value: entry.value,
    filename: entry.filename || null
  }))
}

function buildFormData(entries = []) {
  const formData = new FormData()
  entries.forEach((entry) => {
    if (entry.kind === 'blob') {
      formData.append(entry.key, entry.value, entry.filename || 'upload.bin')
      return
    }
    formData.append(entry.key, entry.value ?? '')
  })
  return formData
}

async function findExistingQueueRecord(dedupeKey) {
  if (!dedupeKey) return null
  const records = await listPendingRecords()
  return records.find((item) => item.dedupeKey === dedupeKey) || null
}

async function replayHttpRecord(record) {
  const { api, submitAttendanceConfirmation } = await loadApiModules()
  const config = {
    ...requestConfig(),
    headers: record.headers || {}
  }
  if (record.kind === 'form-data') {
    await api.request({
      method: record.method || 'post',
      url: record.url,
      data: buildFormData(record.formDataEntries || []),
      ...config
    })
    return
  }
  if (record.url === '/attendance/confirm') {
    await submitAttendanceConfirmation(record.body, config)
    return
  }
  await api.request({
    method: record.method || 'post',
    url: record.url,
    data: record.body,
    ...config
  })
}

async function replayDynamicEntrySubmit(record) {
  const {
    createWorkOrder,
    createWorkOrderEntry,
    findWorkOrderByTrackingCard,
    submitWorkOrderEntry,
    updateWorkOrder,
    updateWorkOrderEntry,
    verifyOcrFields
  } = await loadApiModules()
  const payload = record.payload || {}
  const trackingCardNo = String(payload.trackingCardNo || '').trim().toUpperCase()
  let workOrder = await findWorkOrderByTrackingCard(trackingCardNo)

  if (!workOrder) {
    workOrder = await createWorkOrder(
      {
        tracking_card_no: trackingCardNo,
        ...(payload.workOrderPayload || {})
      },
      requestConfig()
    )
  } else if (payload.workOrderPayload && Object.keys(payload.workOrderPayload).length) {
    workOrder = await updateWorkOrder(workOrder.id, payload.workOrderPayload, requestConfig())
  }

  if (payload.ocrSubmissionId && !payload.ocrVerified) {
    await verifyOcrFields(
      {
        ocr_submission_id: payload.ocrSubmissionId,
        corrected_fields: payload.correctedFields || {},
        rejected: false
      },
      requestConfig()
    )
  }

  let existingEntry = null
  if (payload.entryId && Array.isArray(workOrder?.entries)) {
    existingEntry = workOrder.entries.find((item) => Number(item.id) === Number(payload.entryId)) || null
  }

  let entry = existingEntry
  if (payload.entryId) {
    if (!existingEntry || existingEntry.entry_status === 'draft') {
      entry = await updateWorkOrderEntry(payload.entryId, payload.entryPayload || {}, requestConfig())
    }
  } else {
    entry = await createWorkOrderEntry(workOrder.id, payload.entryPayload || {}, {
      ...requestConfig(),
      headers: {
        'X-Idempotency-Key': payload.idempotencyKey
      }
    })
  }

  await submitWorkOrderEntry(entry.id, {}, requestConfig())
}

async function replayRecord(record) {
  if (record.type === 'dynamic-entry-submit') {
    await replayDynamicEntrySubmit(record)
    return
  }
  await replayHttpRecord(record)
}

export async function enqueuePendingRequest(record) {
  const existing = await findExistingQueueRecord(record.dedupeKey)
  const normalized = {
    id: existing?.id || record.id || buildUuid(),
    createdAt: existing?.createdAt || nowIso(),
    updatedAt: nowIso(),
    ...record
  }
  if (record.formDataEntries) {
    normalized.formDataEntries = serializeFormDataEntries(record.formDataEntries)
  }
  await savePendingRecord(normalized)
  schedulePendingCountRefresh()
  return normalized
}

export async function replayPendingRequests() {
  if (syncing.value) return
  syncing.value = true
  try {
    const records = await listPendingRecords()
    for (const record of records) {
      try {
        await replayRecord(record)
        await deletePendingRecord(record.id)
        if (record.clearDraftKey && typeof localStorage !== 'undefined') {
          localStorage.removeItem(record.clearDraftKey)
        }
      } catch (error) {
        if (isRetryableNetworkError(error)) {
          break
        }
        await deletePendingRecord(record.id)
      }
    }
  } finally {
    syncing.value = false
    schedulePendingCountRefresh()
  }
}

function ensureOnlineListener() {
  if (onlineListenerBound || typeof window === 'undefined') return
  window.addEventListener('online', () => {
    replayPendingRequests()
  })
  onlineListenerBound = true
}

export function useRetryQueue() {
  ensureOnlineListener()
  schedulePendingCountRefresh()
  if (typeof navigator !== 'undefined' && navigator.onLine) {
    setTimeout(() => {
      replayPendingRequests()
    }, 0)
  }
  return {
    enqueuePendingRequest,
    pendingCount: readonly(pendingCount),
    replayPendingRequests,
    syncing: readonly(syncing)
  }
}
