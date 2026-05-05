export const RECONCILIATION_DISPOSITION_REQUIRED_MESSAGE = '请输入处理说明'

export function normalizeReconciliationDispositionNote(value) {
  return String(value ?? '').trim()
}

export function hasReconciliationDispositionNote(value) {
  return Boolean(normalizeReconciliationDispositionNote(value))
}
