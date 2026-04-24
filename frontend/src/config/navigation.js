const routeMetaByName = {
  login: { center: 'auth', group: '认证入口', order: 0, icon: 'Lock', legacy: false, roles: ['public'], keepAlive: false },
  'mobile-entry': { center: 'entry', group: '录入端', order: 1, icon: 'EditPen', legacy: false, roles: ['fill'], keepAlive: true },
  'mobile-report-form': { center: 'entry', group: '录入端', order: 2, icon: 'Document', legacy: false, roles: ['fill'], keepAlive: true },
  'mobile-report-form-advanced': { center: 'entry', group: '录入端', order: 3, icon: 'Grid', legacy: false, roles: ['fill'], keepAlive: true },
  'mobile-ocr-capture': { center: 'entry', group: '录入端', order: 4, icon: 'Camera', legacy: false, roles: ['fill'], keepAlive: true },
  'mobile-attendance-confirm': { center: 'entry', group: '录入端', order: 5, icon: 'Clock', legacy: false, roles: ['fill'], keepAlive: false },
  'mobile-report-history': { center: 'entry', group: '录入端', order: 6, icon: 'Tickets', legacy: false, roles: ['fill'], keepAlive: true },
  'entry-drafts': { center: 'entry', group: '录入端', order: 7, icon: 'DocumentCopy', legacy: false, roles: ['fill'], keepAlive: true },

  'review-overview-home': { center: 'overview', group: '总览中心', order: 1, icon: 'House', legacy: false, roles: ['review'], keepAlive: true },
  'factory-dashboard': { center: 'overview', group: '总览中心', order: 2, icon: 'DataBoard', legacy: false, roles: ['review'], keepAlive: true },
  'workshop-dashboard': { center: 'overview', group: '总览中心', order: 3, icon: 'Monitor', legacy: false, roles: ['review'], keepAlive: true },
  'review-task-center': { center: 'review', group: '审阅处置', order: 4, icon: 'List', legacy: false, roles: ['review'], keepAlive: true },
  'review-report-center': { center: 'delivery', group: '审阅处置', order: 5, icon: 'TrendCharts', legacy: false, roles: ['review'], keepAlive: true },
  'review-quality-center': { center: 'quality', group: '质量与核对', order: 6, icon: 'WarningFilled', legacy: false, roles: ['review'], keepAlive: true },
  'review-reconciliation-center': { center: 'quality', group: '质量与核对', order: 7, icon: 'Connection', legacy: false, roles: ['review'], keepAlive: true },
  'review-cost-accounting': { center: 'cost', group: '经营与智能', order: 8, icon: 'Coin', legacy: false, roles: ['review'], keepAlive: true },
  'review-brain-center': { center: 'brain', group: '经营与智能', order: 9, icon: 'MagicStick', legacy: false, roles: ['review'], keepAlive: true },
  'review-roadmap-center': { center: 'roadmap', group: '经营与智能', order: 10, icon: 'Compass', legacy: false, roles: ['review'], keepAlive: true },

  'admin-overview': { center: 'admin', group: '管理总览', order: 1, icon: 'DataAnalysis', legacy: false, roles: ['config'], keepAlive: true },
  'admin-ingestion-center': { center: 'data', group: '数据与模板', order: 2, icon: 'Connection', legacy: false, roles: ['config'], keepAlive: true },
  'admin-template-center': { center: 'master', group: '数据与模板', order: 3, icon: 'SetUp', legacy: false, roles: ['config'], keepAlive: true },
  'admin-master-workshop': { center: 'master', group: '数据与模板', order: 4, icon: 'OfficeBuilding', legacy: false, roles: ['config'], keepAlive: true },
  'admin-ops-reliability': { center: 'ops', group: '运行保障', order: 5, icon: 'Cpu', legacy: false, roles: ['config'], keepAlive: true },
  'admin-governance-center': { center: 'governance', group: '权限治理', order: 6, icon: 'UserFilled', legacy: false, roles: ['admin'], keepAlive: true },
  'admin-users': { center: 'governance', group: '权限治理', order: 7, icon: 'User', legacy: false, roles: ['admin'], keepAlive: true },
  'admin-roadmap-center': { center: 'roadmap', group: '运行保障', order: 8, icon: 'Compass', legacy: false, roles: ['config'], keepAlive: true },

  'review-ingestion-center': { center: 'data', group: '兼容入口', order: 101, icon: 'Connection', legacy: true, roles: ['config'], keepAlive: false },
  'review-ops-reliability': { center: 'ops', group: '兼容入口', order: 102, icon: 'Cpu', legacy: true, roles: ['config'], keepAlive: false },
  'review-governance-center': { center: 'governance', group: '兼容入口', order: 103, icon: 'UserFilled', legacy: true, roles: ['admin'], keepAlive: false },
  'review-template-center': { center: 'master', group: '兼容入口', order: 104, icon: 'SetUp', legacy: true, roles: ['config'], keepAlive: false },
  'file-import': { center: 'data', group: '兼容入口', order: 201, icon: 'UploadFilled', legacy: true, roles: ['review'], keepAlive: false },
  'import-history': { center: 'data', group: '兼容入口', order: 202, icon: 'Document', legacy: true, roles: ['review'], keepAlive: false },
  'master-workshop': { center: 'master', group: '兼容入口', order: 301, icon: 'OfficeBuilding', legacy: true, roles: ['config'], keepAlive: false },
  'master-team': { center: 'master', group: '兼容入口', order: 302, icon: 'UserFilled', legacy: true, roles: ['config'], keepAlive: false },
  'master-employee': { center: 'master', group: '兼容入口', order: 303, icon: 'User', legacy: true, roles: ['config'], keepAlive: false },
  'master-equipment': { center: 'master', group: '兼容入口', order: 304, icon: 'Monitor', legacy: true, roles: ['config'], keepAlive: false },
  'master-users': { center: 'master', group: '兼容入口', order: 305, icon: 'User', legacy: true, roles: ['admin'], keepAlive: false },
  'master-shift-config': { center: 'master', group: '兼容入口', order: 306, icon: 'Clock', legacy: true, roles: ['config'], keepAlive: false },
  'master-alias': { center: 'master', group: '兼容入口', order: 307, icon: 'Switch', legacy: true, roles: ['config'], keepAlive: false },
  'master-yield-rate-map': { center: 'master', group: '兼容入口', order: 308, icon: 'TrendCharts', legacy: true, roles: ['config'], keepAlive: false },
  'master-workshop-template': { center: 'master', group: '兼容入口', order: 309, icon: 'SetUp', legacy: true, roles: ['admin'], keepAlive: false }
}

const entryNavigation = [
  {
    key: 'entry-main',
    label: '现场录入',
    items: [
      { routeName: 'mobile-entry', label: '今日任务', access: 'fill_surface' },
      { routeName: 'mobile-attendance-confirm', label: '异常补录', access: 'fill_surface' },
      { routeName: 'mobile-report-history', label: '历史', access: 'fill_surface' },
      { routeName: 'entry-drafts', label: '草稿', access: 'fill_surface' }
    ]
  }
]

const reviewNavigation = [
  {
    key: 'overview',
    label: '总览中心',
    items: [
      { routeName: 'review-overview-home', label: '系统总览', access: 'review_surface' },
      { routeName: 'factory-dashboard', label: '厂级看板', access: 'review_surface' },
      { routeName: 'workshop-dashboard', label: '车间看板', access: 'review_surface' }
    ]
  },
  {
    key: 'review',
    label: '审阅处置',
    items: [
      { routeName: 'review-task-center', label: '审阅任务', access: 'review_surface' },
      { routeName: 'review-report-center', label: '日报交付', access: 'review' }
    ]
  },
  {
    key: 'quality',
    label: '质量与核对',
    items: [
      { routeName: 'review-quality-center', label: '质量告警', access: 'review' },
      { routeName: 'review-reconciliation-center', label: '差异核对', access: 'review' }
    ]
  },
  {
    key: 'analysis',
    label: '经营与智能',
    items: [
      { routeName: 'review-cost-accounting', label: '成本效益', access: 'review_surface' },
      { routeName: 'review-brain-center', label: 'AI总大脑', access: 'review_surface' },
      { routeName: 'review-roadmap-center', label: '路线图', access: 'review_surface' }
    ]
  }
]

const adminNavigation = [
  {
    key: 'overview',
    label: '管理总览',
    items: [
      { routeName: 'admin-overview', label: '系统总览', access: 'desktop_config' }
    ]
  },
  {
    key: 'data',
    label: '数据与模板',
    items: [
      { routeName: 'admin-ingestion-center', label: '数据接入', access: 'desktop_config' },
      { routeName: 'admin-template-center', label: '字段模板', access: 'desktop_config' },
      { routeName: 'admin-master-workshop', label: '主数据', access: 'desktop_config' }
    ]
  },
  {
    key: 'governance',
    label: '权限治理',
    items: [
      { routeName: 'admin-governance-center', label: '权限矩阵', access: 'admin' },
      { routeName: 'admin-users', label: '用户角色', access: 'admin' }
    ]
  },
  {
    key: 'ops',
    label: '运行保障',
    items: [
      { routeName: 'admin-ops-reliability', label: '系统运维', access: 'desktop_config' },
      { routeName: 'admin-roadmap-center', label: '路线图', access: 'desktop_config' }
    ]
  }
]

const desktopNavigation = [
  {
    key: 'legacy',
    label: '兼容入口',
    items: [
      { routeName: 'master-workshop', label: '主数据', access: 'desktop_config' },
      { routeName: 'review-template-center', label: '字段模板', access: 'desktop_config' },
      { routeName: 'review-ingestion-center', label: '数据接入', access: 'desktop_config' },
      { routeName: 'review-ops-reliability', label: '系统运维', access: 'desktop_config' }
    ]
  }
]

function canAccess(auth, access) {
  if (!access) return true
  if (access === 'fill_surface') return Boolean(auth?.entrySurface ?? auth?.canAccessFillSurface)
  if (access === 'review_surface') return Boolean(auth?.reviewSurface ?? auth?.canAccessReviewSurface)
  if (access === 'admin_surface') return Boolean(auth?.adminSurface ?? auth?.canAccessDesktopConfig)
  if (access === 'review') return Boolean(auth?.canAccessReviewDesk)
  if (access === 'desktop_config') return Boolean(auth?.adminSurface ?? auth?.canAccessDesktopConfig)
  if (access === 'admin') return Boolean(auth?.isAdmin)
  if (access === 'manager') return Boolean(auth?.isAdmin || auth?.isManager)
  return true
}

export function resolveRouteMeta(routeName, currentMeta = {}) {
  if (!routeName) return currentMeta || {}
  return { ...(currentMeta || {}), ...(routeMetaByName[routeName] || {}) }
}

export function buildShellNavigation(zone, auth) {
  const sourceByZone = {
    entry: entryNavigation,
    review: reviewNavigation,
    admin: adminNavigation,
    desktop: desktopNavigation
  }
  const source = sourceByZone[zone] || reviewNavigation
  return source
    .map((group) => ({
      ...group,
      items: (group.items || []).filter((item) => canAccess(auth, item.access))
    }))
    .filter((group) => group.items.length > 0)
}

export const NAV_ROUTE_META = routeMetaByName
