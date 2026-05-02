export function shiftReportStatusTagType(status) {
  if (status === 'submitted' || status === 'approved' || status === 'auto_confirmed') return 'success'
  if (status === 'returned') return 'danger'
  if (status === 'draft') return 'warning'
  return 'info'
}

const MEANINGFUL_FIELDS = [
  'attendance_count', 'input_weight', 'output_weight', 'scrap_weight',
  'storage_prepared', 'storage_finished', 'shipment_weight', 'contract_received',
  'electricity_daily', 'gas_daily', 'exception_type', 'note', 'optional_photo_url'
]

export function isMeaningfulLocalDraft(snapshot) {
  if (!snapshot?.form) return false
  return MEANINGFUL_FIELDS.some((field) => {
    const value = snapshot.form[field]
    if (value === null || value === undefined) return false
    if (typeof value === 'string') return value.trim() !== ''
    return true
  })
}
