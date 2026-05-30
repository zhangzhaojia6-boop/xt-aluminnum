export const centerNavigation = [
  {
    id: 'overview',
    no: '01',
    title: '系统总览主视图',
    zone: 'review',
    path: '/manage/today',
    routeName: 'manage-today',
    icon: '总',
    summary: '昨日产量、达成率、补录、交付状态'
  },
  {
    id: 'entry',
    no: '03',
    title: '独立填报端首页',
    zone: 'entry',
    path: '/entry',
    routeName: 'mobile-entry',
    icon: '填',
    summary: '今日班次、待填任务、已提交'
  },
  {
    id: 'factory',
    no: '05',
    title: '工厂作业看板',
    zone: 'review',
    path: '/manage/production',
    routeName: 'manage-production',
    icon: '厂',
    summary: '产线产量、OEE、趋势'
  },
  {
    id: 'reports',
    no: '08',
    title: '日报与交付中心',
    zone: 'review',
    path: '/manage/reports',
    routeName: 'review-report-center',
    icon: '报',
    summary: '日报、交付清单、导出状态'
  },
  {
    id: 'cost',
    no: '10',
    title: '经营效益',
    zone: 'review',
    path: '/manage/today',
    routeName: 'factory-command-cost',
    icon: '效',
    summary: '经营估算、策略口径、能耗与人工'
  },
  {
    id: 'brain',
    no: '11',
    title: 'AI 助手',
    zone: 'review',
    path: '/manage/ai-assistant',
    routeName: 'factory-ai-assistant',
    icon: 'AI',
    summary: '生产摘要、风险事件、辅助建议'
  },
  {
    id: 'ops',
    no: '12',
    title: '系统运维与观测',
    zone: 'admin',
    path: '/manage/admin/settings',
    routeName: 'admin-ops-reliability',
    icon: '运',
    summary: 'health、ready、版本、响应时间'
  },
  {
    id: 'governance',
    no: '13',
    title: '权限与治理中心',
    zone: 'admin',
    path: '/manage/admin/governance',
    routeName: 'admin-governance-center',
    icon: '权',
    summary: '角色矩阵、审计日志、数据权限'
  },
  {
    id: 'master',
    no: '14',
    title: '主数据与模板中心',
    zone: 'admin',
    path: '/manage/master',
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

  'manage-today': { center: 'overview', group: '三页骨架', order: 1, icon: 'House', legacy: false, roles: ['review'], keepAlive: true },
  'manage-production': { center: 'factory', group: '三页骨架', order: 2, icon: 'DataBoard', legacy: false, roles: ['review'], keepAlive: true },
  'manage-fill-details': { center: 'factory', group: '生产', order: 3, icon: 'DataLine', legacy: false, roles: ['review'], keepAlive: true },
  'manage-alerts': { group: '兼容入口', order: 103, icon: 'WarningFilled', legacy: true, roles: ['review'], keepAlive: false },
  'review-report-center': { center: 'reports', group: '审阅处置', order: 5, icon: 'TrendCharts', legacy: false, roles: ['review'], keepAlive: true },
  'review-quality-center': { center: 'quality', group: '质量与核对', order: 6, icon: 'WarningFilled', legacy: false, roles: ['review'], keepAlive: true },
  'review-reconciliation-center': { center: 'quality', group: '质量与核对', order: 7, icon: 'Connection', legacy: false, roles: ['review'], keepAlive: true },
  'factory-ai-assistant': { center: 'brain', group: '经营与智能', order: 9, icon: 'MagicStick', legacy: false, roles: ['review'], keepAlive: true },
  'review-brain-center': { center: 'brain', group: '兼容入口', order: 109, icon: 'MagicStick', legacy: true, roles: ['review'], keepAlive: false },

  'admin-overview': { center: 'ops', group: '兼容入口', order: 100, icon: 'Cpu', legacy: true, roles: ['admin'], keepAlive: false },
  'admin-ingestion-center': { group: '兼容入口', order: 202, icon: 'Connection', legacy: true, roles: ['admin'], keepAlive: false },
  'admin-template-center': { center: 'master', group: '数据与模板', order: 3, icon: 'SetUp', legacy: false, roles: ['admin'], keepAlive: true },
  'admin-master-workshop': { center: 'master', group: '数据与模板', order: 4, icon: 'OfficeBuilding', legacy: false, roles: ['admin'], keepAlive: true },
  'admin-ops-reliability': { center: 'ops', group: '运行保障', order: 5, icon: 'Cpu', legacy: false, roles: ['admin'], keepAlive: true },
  'admin-governance-center': { center: 'governance', group: '权限治理', order: 6, icon: 'UserFilled', legacy: false, roles: ['admin'], keepAlive: true },
  'admin-users': { center: 'governance', group: '权限治理', order: 7, icon: 'User', legacy: false, roles: ['admin'], keepAlive: true },

  'review-ingestion-center': { group: '兼容入口', order: 101, icon: 'Connection', legacy: true, roles: ['admin'], keepAlive: false },
  'review-ops-reliability': { center: 'ops', group: '兼容入口', order: 102, icon: 'Cpu', legacy: true, roles: ['admin'], keepAlive: false },
  'review-governance-center': { center: 'governance', group: '兼容入口', order: 103, icon: 'UserFilled', legacy: true, roles: ['admin'], keepAlive: false },
  'review-template-center': { center: 'master', group: '兼容入口', order: 104, icon: 'SetUp', legacy: true, roles: ['admin'], keepAlive: false },
  'file-import': { group: '兼容入口', order: 201, icon: 'UploadFilled', legacy: true, roles: ['admin'], keepAlive: false },
  'import-history': { group: '兼容入口', order: 203, icon: 'Document', legacy: true, roles: ['admin'], keepAlive: false },
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

const commandMetaByName = {
  'manage-today': { shortLabel: '昨日报', commandGroup: '昨日日报', secondaryGroup: '全局' },
  'manage-production': { shortLabel: '生产', commandGroup: '生产', secondaryGroup: '作业' },
  'manage-fill-details': { shortLabel: '明细', commandGroup: '生产', secondaryGroup: '填报' },
  'review-report-center': { shortLabel: '日报', commandGroup: '总览', secondaryGroup: '交付' },
  'review-quality-center': { shortLabel: '质量', commandGroup: '工厂', secondaryGroup: '质量' },
  'review-reconciliation-center': { shortLabel: '核对', commandGroup: '工厂', secondaryGroup: '质量' },
  'factory-ai-assistant': { shortLabel: 'AI 助手', commandGroup: 'AI 助手', secondaryGroup: '站内' },
  'review-brain-center': { shortLabel: 'AI 助手', commandGroup: '兼容入口', secondaryGroup: '站内' },
  'admin-master-workshop': { shortLabel: '主数据', commandGroup: '管理', secondaryGroup: '模板' },
  'admin-template-center': { shortLabel: '模板', commandGroup: '管理', secondaryGroup: '模板' },
  'admin-ops-reliability': { shortLabel: '设置', commandGroup: '管理', secondaryGroup: '运行' },
  'admin-governance-center': { shortLabel: '治理', commandGroup: '管理', secondaryGroup: '权限' },
  'admin-users': { shortLabel: '用户', commandGroup: '管理', secondaryGroup: '权限' },
  'mobile-entry': { shortLabel: '填报', commandGroup: '填报', secondaryGroup: '移动' }
}

Object.entries(commandMetaByName).forEach(([routeName, meta]) => {
  routeMetaByName[routeName] = { ...(routeMetaByName[routeName] || {}), ...meta }
})

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
    key: 'owner-tabs',
    label: '三页骨架',
    items: [
      { routeName: 'manage-today', label: '昨日日报', access: 'review' },
      { routeName: 'manage-production', label: '生产', access: 'review' },
      { routeName: 'manage-fill-details', label: '填报明细', access: 'review' }
    ]
  }
]

const adminNavigation = [
  {
    key: 'admin-main',
    label: '管理端',
    items: [
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
