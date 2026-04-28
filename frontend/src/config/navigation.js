export const centerNavigation = [
  {
    id: 'overview',
    no: '01',
    title: '系统总览主视图',
    zone: 'review',
    path: '/review/overview',
    routeName: 'review-overview-home',
    icon: '总',
    summary: '今日产量、达成率、异常、待审、交付状态'
  },
  {
    id: 'entry',
    no: '03',
    title: '独立填报端首页',
    zone: 'entry',
    path: '/entry',
    routeName: 'mobile-entry',
    icon: '填',
    summary: '今日班次、待填任务、已提交、异常待补'
  },
  {
    id: 'factory',
    no: '05',
    title: '工厂作业看板',
    zone: 'review',
    path: '/review/factory',
    routeName: 'factory-dashboard',
    icon: '厂',
    summary: '产线产量、OEE、异常、趋势'
  },
  {
    id: 'ingestion',
    no: '06',
    title: '数据接入与字段映射中心',
    zone: 'admin',
    path: '/admin/ingestion',
    routeName: 'admin-ingestion-center',
    icon: '接',
    summary: '数据源、字段映射、导入批次、错误率'
  },
  {
    id: 'tasks',
    no: '07',
    title: '审阅中心',
    zone: 'review',
    path: '/review/tasks',
    routeName: 'review-task-center',
    icon: '审',
    summary: '待审、已审、驳回、风险等级、AI 辅助建议'
  },
  {
    id: 'reports',
    no: '08',
    title: '日报与交付中心',
    zone: 'review',
    path: '/review/reports',
    routeName: 'review-report-center',
    icon: '报',
    summary: '日报、交付清单、导出状态'
  },
  {
    id: 'quality',
    no: '09',
    title: '质量与告警中心',
    zone: 'review',
    path: '/review/quality',
    routeName: 'review-quality-center',
    icon: '质',
    summary: '质量告警、处理状态、追溯'
  },
  {
    id: 'cost',
    no: '10',
    title: '成本核算与效益中心',
    zone: 'review',
    path: '/review/cost-accounting',
    routeName: 'review-cost-accounting',
    icon: '本',
    summary: '经营估算、策略口径、能耗与人工'
  },
  {
    id: 'brain',
    no: '11',
    title: 'AI 总控中心',
    zone: 'review',
    path: '/review/brain',
    routeName: 'review-brain-center',
    icon: 'AI',
    summary: '生产摘要、风险事件、辅助建议'
  },
  {
    id: 'ops',
    no: '12',
    title: '系统运维与观测',
    zone: 'admin',
    path: '/admin/ops',
    routeName: 'admin-ops-reliability',
    icon: '运',
    summary: 'health、ready、版本、响应时间'
  },
  {
    id: 'governance',
    no: '13',
    title: '权限与治理中心',
    zone: 'admin',
    path: '/admin/governance',
    routeName: 'admin-governance-center',
    icon: '权',
    summary: '角色矩阵、审计日志、数据权限'
  },
  {
    id: 'master',
    no: '14',
    title: '主数据与模板中心',
    zone: 'admin',
    path: '/admin/master',
    routeName: 'admin-master-workshop',
    icon: '主',
    summary: '车间、班组、员工、机台、模板'
  }
]

const centerByRouteName = Object.fromEntries(
  centerNavigation.map((center) => [center.routeName, center])
)

const routeMetaByName = {
  login: {
    center: 'auth',
    group: '公共入口',
    order: 0,
    icon: 'Lock',
    legacy: false,
    roles: ['public'],
    keepAlive: false,
    zone: 'public',
    access: 'public',
    title: '登录与角色入口',
    centerNo: '02',
    canonical: '/login'
  },
  'mobile-entry': { center: 'entry', group: '录入端', order: 1, icon: 'EditPen', legacy: false, roles: ['entry'], keepAlive: true },
  'mobile-report-form': { center: 'entry-flow', group: '录入端', order: 2, icon: 'Document', legacy: false, roles: ['entry'], keepAlive: true, centerNo: '04' },
  'mobile-report-form-advanced': { center: 'entry-flow', group: '录入端', order: 3, icon: 'Grid', legacy: false, roles: ['entry'], keepAlive: true, centerNo: '04' },
  'mobile-ocr-capture': { center: 'entry-flow', group: '录入端', order: 4, icon: 'Camera', legacy: false, roles: ['entry'], keepAlive: true, centerNo: '04' },
  'mobile-attendance-confirm': { center: 'entry', group: '录入端', order: 5, icon: 'Clock', legacy: false, roles: ['entry'], keepAlive: false },
  'mobile-report-history': { center: 'entry', group: '录入端', order: 6, icon: 'Tickets', legacy: false, roles: ['entry'], keepAlive: true },
  'entry-drafts': { center: 'entry', group: '录入端', order: 7, icon: 'DocumentCopy', legacy: false, roles: ['entry'], keepAlive: true },

  'review-overview-home': { center: 'overview', group: '总览中心', order: 1, icon: 'House', legacy: false, roles: ['review'], keepAlive: true },
  'factory-dashboard': { center: 'factory', group: '总览中心', order: 2, icon: 'DataBoard', legacy: false, roles: ['review'], keepAlive: true },
  'workshop-dashboard': { center: 'factory', group: '总览中心', order: 3, icon: 'Monitor', legacy: false, roles: ['review'], keepAlive: true },
  'review-task-center': { center: 'tasks', group: '审阅处置', order: 4, icon: 'List', legacy: false, roles: ['review'], keepAlive: true },
  'review-report-center': { center: 'reports', group: '审阅处置', order: 5, icon: 'TrendCharts', legacy: false, roles: ['review'], keepAlive: true },
  'review-quality-center': { center: 'quality', group: '质量与核对', order: 6, icon: 'WarningFilled', legacy: false, roles: ['review'], keepAlive: true },
  'review-reconciliation-center': { center: 'quality', group: '质量与核对', order: 7, icon: 'Connection', legacy: false, roles: ['review'], keepAlive: true },
  'review-cost-accounting': { center: 'cost', group: '经营与智能', order: 8, icon: 'Coin', legacy: false, roles: ['review'], keepAlive: true },
  'review-brain-center': { center: 'brain', group: '经营与智能', order: 9, icon: 'MagicStick', legacy: false, roles: ['review'], keepAlive: true },

  'admin-overview': { center: 'master', group: '管理总览', order: 1, icon: 'DataAnalysis', legacy: false, roles: ['admin'], keepAlive: true },
  'admin-ingestion-center': { center: 'ingestion', group: '数据与模板', order: 2, icon: 'Connection', legacy: false, roles: ['admin'], keepAlive: true },
  'admin-template-center': { center: 'master', group: '数据与模板', order: 3, icon: 'SetUp', legacy: false, roles: ['admin'], keepAlive: true },
  'admin-master-workshop': { center: 'master', group: '数据与模板', order: 4, icon: 'OfficeBuilding', legacy: false, roles: ['admin'], keepAlive: true },
  'admin-ops-reliability': { center: 'ops', group: '运行保障', order: 5, icon: 'Cpu', legacy: false, roles: ['admin'], keepAlive: true },
  'admin-governance-center': { center: 'governance', group: '权限治理', order: 6, icon: 'UserFilled', legacy: false, roles: ['admin'], keepAlive: true },
  'admin-users': { center: 'governance', group: '权限治理', order: 7, icon: 'User', legacy: false, roles: ['admin'], keepAlive: true },

  'review-ingestion-center': { center: 'ingestion', group: '兼容入口', order: 101, icon: 'Connection', legacy: true, roles: ['admin'], keepAlive: false },
  'review-ops-reliability': { center: 'ops', group: '兼容入口', order: 102, icon: 'Cpu', legacy: true, roles: ['admin'], keepAlive: false },
  'review-governance-center': { center: 'governance', group: '兼容入口', order: 103, icon: 'UserFilled', legacy: true, roles: ['admin'], keepAlive: false },
  'review-template-center': { center: 'master', group: '兼容入口', order: 104, icon: 'SetUp', legacy: true, roles: ['admin'], keepAlive: false },
  'file-import': { center: 'ingestion', group: '兼容入口', order: 201, icon: 'UploadFilled', legacy: true, roles: ['admin'], keepAlive: false },
  'import-history': { center: 'ingestion', group: '兼容入口', order: 202, icon: 'Document', legacy: true, roles: ['admin'], keepAlive: false },
  'master-workshop': { center: 'master', group: '兼容入口', order: 301, icon: 'OfficeBuilding', legacy: true, roles: ['admin'], keepAlive: false },
  'master-team': { center: 'master', group: '兼容入口', order: 302, icon: 'UserFilled', legacy: true, roles: ['admin'], keepAlive: false },
  'master-employee': { center: 'master', group: '兼容入口', order: 303, icon: 'User', legacy: true, roles: ['admin'], keepAlive: false },
  'master-equipment': { center: 'master', group: '兼容入口', order: 304, icon: 'Monitor', legacy: true, roles: ['admin'], keepAlive: false },
  'master-users': { center: 'governance', group: '兼容入口', order: 305, icon: 'User', legacy: true, roles: ['admin'], keepAlive: false },
  'master-shift-config': { center: 'master', group: '兼容入口', order: 306, icon: 'Clock', legacy: true, roles: ['admin'], keepAlive: false },
  'master-alias': { center: 'master', group: '兼容入口', order: 307, icon: 'Switch', legacy: true, roles: ['admin'], keepAlive: false },
  'master-yield-rate-map': { center: 'master', group: '兼容入口', order: 308, icon: 'TrendCharts', legacy: true, roles: ['admin'], keepAlive: false },
  'master-workshop-template': { center: 'master', group: '兼容入口', order: 309, icon: 'SetUp', legacy: true, roles: ['admin'], keepAlive: false }
}

const entryNavigation = [
  {
    key: 'entry-main',
    label: '录入端',
    items: [
      { routeName: 'mobile-entry', label: '今日任务', access: 'entry' },
      { routeName: 'mobile-attendance-confirm', label: '异常补录', access: 'entry' },
      { routeName: 'mobile-report-history', label: '历史记录', access: 'entry' },
      { routeName: 'entry-drafts', label: '草稿箱', access: 'entry' }
    ]
  }
]

const reviewNavigation = [
  {
    key: 'overview',
    label: '总览中心',
    items: [
      { routeName: 'review-overview-home', label: '系统总览', access: 'review' },
      { routeName: 'factory-dashboard', label: '工厂看板', access: 'review' },
      { routeName: 'workshop-dashboard', label: '车间看板', access: 'review' }
    ]
  },
  {
    key: 'review',
    label: '审阅处置',
    items: [
      { routeName: 'review-task-center', label: '审阅中心', access: 'review' },
      { routeName: 'review-report-center', label: '日报交付', access: 'review' },
      { routeName: 'review-quality-center', label: '质量告警', access: 'review' },
      { routeName: 'review-reconciliation-center', label: '差异核对', access: 'review' }
    ]
  },
  {
    key: 'analysis',
    label: '经营与智能',
    items: [
      { routeName: 'review-cost-accounting', label: '成本效益', access: 'review' },
      { routeName: 'review-brain-center', label: 'AI 总控', access: 'review' }
    ]
  }
]

const adminNavigation = [
  {
    key: 'admin-main',
    label: '管理端',
    items: [
      { routeName: 'admin-overview', label: '管理总览', access: 'admin' },
      { routeName: 'admin-ingestion-center', label: '数据接入与字段映射中心', access: 'admin' },
      { routeName: 'admin-master-workshop', label: '主数据', access: 'admin' },
      { routeName: 'admin-template-center', label: '模板中心', access: 'admin' },
      { routeName: 'admin-users', label: '用户管理', access: 'admin' },
      { routeName: 'admin-governance-center', label: '权限治理', access: 'admin' },
      { routeName: 'admin-ops-reliability', label: '系统运维', access: 'admin' }
    ]
  }
]

function canAccess(auth, access) {
  if (!access || access === 'public') return true
  if (access === 'entry' || access === 'fill_surface') return Boolean(auth?.entrySurface ?? auth?.canAccessFillSurface)
  if (access === 'review' || access === 'review_surface') return Boolean(auth?.reviewSurface ?? auth?.canAccessReviewSurface)
  if (access === 'admin' || access === 'desktop_config' || access === 'admin_surface') return Boolean(auth?.isAdmin)
  return true
}

export function resolveRouteMeta(routeName, currentMeta = {}) {
  if (!routeName) return currentMeta || {}
  const routeMeta = routeMetaByName[routeName] || {}
  const center = centerByRouteName[routeName]
  const centerMeta = center
    ? {
        zone: center.zone,
        access: center.zone,
        title: center.title,
        centerNo: center.no,
        canonical: center.path
      }
    : {}
  return { ...centerMeta, ...routeMeta, ...(currentMeta || {}) }
}

export function buildShellNavigation(zone, auth) {
  const sourceByZone = {
    entry: entryNavigation,
    review: reviewNavigation,
    admin: adminNavigation
  }
  const source = sourceByZone[zone] || reviewNavigation
  return source
    .map((group) => ({
      ...group,
      items: (group.items || []).filter((item) => canAccess(auth, item.access))
    }))
    .filter((group) => group.items.length > 0)
}

export function findCenterByRouteName(routeName) {
  return centerByRouteName[routeName] || null
}

export const NAV_ROUTE_META = routeMetaByName
