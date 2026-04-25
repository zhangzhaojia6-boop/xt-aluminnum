export const statusToneMap = {
  normal: 'success',
  success: 'success',
  ready: 'success',
  live: 'success',
  pending: 'warning',
  warning: 'warning',
  attention: 'warning',
  processing: 'processing',
  risk: 'danger',
  danger: 'danger',
  blocked: 'danger',
  rejected: 'danger',
  info: 'info',
  neutral: 'neutral',
  closed: 'closed'
}

export function resolveStatusTone(status = 'info') {
  return statusToneMap[status] || 'info'
}
