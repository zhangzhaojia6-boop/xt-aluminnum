export function reportStatusLabel(status) {
  const map = {
    submitted: '主操已报',
    reviewed: '系统处理中',
    auto_confirmed: '已入汇总',
    returned: '退回补录',
    draft: '填报中',
    unreported: '待上报',
    late: '迟报'
  }
  return map[status] || status || '待上报'
}

export function reportStatusTagType(status) {
  const map = {
    submitted: 'success',
    reviewed: 'success',
    auto_confirmed: 'success',
    returned: 'danger',
    draft: 'primary',
    unreported: 'warning',
    late: 'danger'
  }
  return map[status] || 'info'
}

export function reportStatusHint(status) {
  const map = {
    submitted: '主操已报',
    reviewed: '系统处理中',
    auto_confirmed: '已入汇总',
    returned: '退回补录',
    draft: '填报中',
    unreported: '待上报',
    late: '迟报'
  }
  return map[status] || '同步中'
}

export function reportingSourceClass(item) {
  const normalized = String(item?.source_variant || '').toLowerCase()
  if (normalized === 'owner') return 'is-owner'
  if (normalized === 'mobile') return 'is-mobile'
  return 'is-import'
}

export function toFactoryStatus(status) {
  const value = String(status || '').toLowerCase()
  if (['danger', 'error', 'failed', 'blocked', 'returned', 'late'].includes(value)) return 'danger'
  if (['warning', 'alert', 'pending', 'fallback', 'mixed', 'unreported'].includes(value)) return 'warning'
  return 'normal'
}

export function workshopTypeFromName(name) {
  const value = String(name || '')
  if (/铸|熔|锭/.test(value)) return 'casting'
  if (/热轧|热/.test(value)) return 'hot_roll'
  if (/冷轧|冷/.test(value)) return 'cold_roll'
  if (/拉矫|矫/.test(value)) return 'leveling'
  if (/退火/.test(value)) return 'online_annealing'
  if (/库|仓|成品/.test(value)) return 'inventory'
  if (/跨|链路|调度/.test(value)) return 'cross_workshop_flow'
  return 'finishing'
}

export function requestErrorMessage(error, fallback = '数据加载失败，请稍后重试') {
  const detail = error?.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || item).join('；')
  }
  if (detail && typeof detail === 'object') {
    return detail.message || detail.msg || fallback
  }
  if (typeof detail === 'string' && detail.trim()) {
    return detail.trim()
  }
  return error?.message || fallback
}
