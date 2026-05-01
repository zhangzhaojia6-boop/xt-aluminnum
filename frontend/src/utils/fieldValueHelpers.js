import { formatNumber } from './display.js'

export function toNumber(value) {
  if (value === '' || value === null || value === undefined) return null
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

export function isEmptyValue(value) {
  if (value === null || value === undefined) return true
  if (typeof value === 'string') return value.trim() === ''
  if (Array.isArray(value)) return value.length === 0
  if (typeof value === 'object') return Object.keys(value).length === 0
  return false
}

export function emptyFieldValue(field) {
  if (field.type === 'number') return null
  return ''
}

export function normalizeFieldValue(field, rawValue) {
  if (rawValue === null || rawValue === undefined || rawValue === '') return null
  if (field.type === 'number') return toNumber(rawValue)
  if (field.type === 'time') {
    const text = String(rawValue)
    if (!text.trim()) return null
    return text.length === 5 ? `${text}:00` : text
  }
  return String(rawValue).trim()
}

export function formatFieldValue(field, rawValue) {
  if (rawValue === null || rawValue === undefined) return emptyFieldValue(field)
  if (field.type === 'time') return String(rawValue).slice(0, 8)
  return rawValue
}

export function formatFieldValueForDisplay(field, rawValue) {
  if (rawValue === null || rawValue === undefined || rawValue === '') return '-'
  if (field.type === 'number') {
    const digits = Number.isInteger(Number(rawValue)) ? 0 : 2
    const formatted = formatNumber(rawValue, digits)
    return field.unit ? `${formatted} ${field.unit}` : formatted
  }
  if (field.type === 'time') return String(rawValue).slice(0, 5)
  return String(rawValue)
}

export function displayFieldLabel(field) {
  if (!field) return ''
  if (field.name === 'operator_notes') return '备注'
  return field.label || field.name || ''
}

export function fieldPlaceholder(field) {
  const label = displayFieldLabel(field)
  if (field.type === 'number') return '数字'
  if (field.type === 'time') return '时间'
  return label || '填写'
}
