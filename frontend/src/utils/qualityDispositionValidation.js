export const QUALITY_DISPOSITION_REQUIRED_MESSAGE = '请输入处置说明'

export function normalizeQualityDispositionNote(value) {
  return String(value ?? '').trim()
}

export function hasQualityDispositionNote(value) {
  return Boolean(normalizeQualityDispositionNote(value))
}
