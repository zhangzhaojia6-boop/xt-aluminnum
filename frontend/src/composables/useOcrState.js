import { reactive } from 'vue'

const OCR_STORAGE_PREFIX = 'aluminum-ocr-submission:'

function ocrStorageKey(submissionId) {
  return `${OCR_STORAGE_PREFIX}${submissionId}`
}

export function confidenceTone(confidence) {
  if (confidence === null || confidence === undefined) return 'warn'
  if (confidence >= 0.85) return 'good'
  if (confidence >= 0.6) return 'warn'
  return 'danger'
}

export function confidenceLabel(confidence) {
  if (confidence === null || confidence === undefined) return '待核对'
  return `${Math.round(confidence * 100)}%`
}

export function useOcrState() {
  const ocrState = reactive({
    submissionId: null,
    imageUrl: '',
    rawText: '',
    fields: {},
    verified: false,
  })

  function ocrMetaForField(fieldName) {
    return ocrState.fields?.[fieldName] || null
  }

  function clearOcrState({ clearStorage = false } = {}) {
    if (clearStorage && ocrState.submissionId) {
      sessionStorage.removeItem(ocrStorageKey(ocrState.submissionId))
    }
    ocrState.submissionId = null
    ocrState.imageUrl = ''
    ocrState.rawText = ''
    ocrState.fields = {}
    ocrState.verified = false
  }

  function loadOcrFromStorage({ submissionId, editableFields, formValues, formatFieldValue, isEmptyValue }) {
    clearOcrState()
    if (!submissionId) return
    const raw = sessionStorage.getItem(ocrStorageKey(submissionId))
    if (!raw) return

    try {
      const payload = JSON.parse(raw)
      ocrState.submissionId = submissionId
      ocrState.imageUrl = payload.image_url || ''
      ocrState.rawText = payload.raw_text || ''
      ocrState.fields = payload.fields || {}
      ocrState.verified = Boolean(payload.status === 'verified' || payload.verified)

      editableFields.forEach((field) => {
        const meta = payload.fields?.[field.name]
        if (!meta || meta.value === null || meta.value === undefined || meta.value === '') return
        if (isEmptyValue(formValues[field.name])) {
          formValues[field.name] = formatFieldValue(field, meta.value)
        }
      })
    } catch {
      clearOcrState({ clearStorage: true })
    }
  }

  function saveOcrToStorage() {
    if (!ocrState.submissionId) return
    sessionStorage.setItem(
      ocrStorageKey(ocrState.submissionId),
      JSON.stringify({
        ocr_submission_id: ocrState.submissionId,
        image_url: ocrState.imageUrl,
        raw_text: ocrState.rawText,
        fields: ocrState.fields,
        status: ocrState.verified ? 'verified' : 'pending',
        verified: ocrState.verified,
      })
    )
  }

  function removeOcrStorage() {
    if (ocrState.submissionId) {
      sessionStorage.removeItem(ocrStorageKey(ocrState.submissionId))
    }
  }

  return {
    ocrState,
    ocrMetaForField,
    clearOcrState,
    loadOcrFromStorage,
    saveOcrToStorage,
    removeOcrStorage,
  }
}
