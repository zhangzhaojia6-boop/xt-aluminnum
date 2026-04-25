export const referenceModules = Object.freeze([
  {
    moduleId: '01',
    title: '系统总览主视图',
    surface: 'review',
    routeName: 'review-overview-home',
    routePath: '/review/overview',
    layout: 'canvas-hero',
    kpiKeys: ['todayOutput', 'orderCompletion', 'qualityRate', 'riskCount'],
    primary: { type: 'flowMap', source: 'commandOverview' },
    side: { type: 'statusRail', source: 'commandOverview' },
    actions: ['enterReview', 'exportSnapshot']
  },
  {
    moduleId: '02',
    title: '登录与角色入口',
    surface: 'system',
    routeName: 'login',
    routePath: '/login',
    layout: 'role-handoff',
    kpiKeys: ['entry', 'review', 'admin'],
    primary: { type: 'roleCards', source: 'auth' },
    side: { type: 'loginForm', source: 'auth' },
    actions: ['login']
  },
  {
    moduleId: '03',
    title: '独立填报端首页',
    surface: 'entry',
    routeName: 'mobile-entry',
    routePath: '/entry',
    layout: 'entry-terminal',
    kpiKeys: ['todayShift', 'pendingTasks', 'submitted', 'abnormal'],
    primary: { type: 'quickActions', source: 'entryHome' },
    side: { type: 'recentStatus', source: 'entryHome' },
    actions: ['fill', 'history', 'photo']
  },
  {
    moduleId: '04',
    title: '填报流程页',
    surface: 'entry',
    routeName: 'dynamic-entry-form',
    routePath: '/entry/report/new',
    layout: 'entry-flow',
    kpiKeys: ['step', 'planned', 'actual', 'quality'],
    primary: { type: 'formGrid', source: 'entryFlow' },
    side: { type: 'aiSummary', source: 'entryFlow' },
    actions: ['previous', 'saveDraft', 'next']
  },
  {
    moduleId: '05',
    title: '工厂作业看板',
    surface: 'review',
    routeName: 'factory-dashboard',
    routePath: '/review/factory',
    layout: 'factory-board',
    kpiKeys: ['output', 'oee', 'qualityRate', 'abnormal'],
    primary: { type: 'table', source: 'factoryBoard' },
    side: { type: 'trend', source: 'factoryBoard' },
    actions: ['export']
  },
  {
    moduleId: '06',
    title: '数据接入与字段映射中心',
    surface: 'admin',
    routeName: 'admin-ingestion-center',
    routePath: '/admin/ingestion',
    layout: 'mapping-center',
    kpiKeys: ['mes', 'plc', 'manual', 'mapped'],
    primary: { type: 'table', source: 'ingestion' },
    side: { type: 'ring', source: 'ingestion' },
    actions: ['import', 'map']
  },
  {
    moduleId: '07',
    title: '审阅中心',
    surface: 'review',
    routeName: 'review-task-center',
    routePath: '/review/tasks',
    layout: 'table-with-side-risk',
    kpiKeys: ['pending', 'approved', 'rejected'],
    primary: { type: 'table', source: 'reviewTasks' },
    side: { type: 'riskList', source: 'reviewRisks' },
    actions: ['approve', 'reject', 'export']
  },
  {
    moduleId: '08',
    title: '日报与交付中心',
    surface: 'review',
    routeName: 'review-report-center',
    routePath: '/review/reports',
    layout: 'report-delivery',
    kpiKeys: ['todayOutput', 'orderCompletion', 'qualityRate', 'delivered'],
    primary: { type: 'trend', source: 'reports' },
    side: { type: 'deliveryList', source: 'reports' },
    actions: ['exportPdf', 'exportExcel', 'send']
  },
  {
    moduleId: '09',
    title: '质量与告警中心',
    surface: 'review',
    routeName: 'review-quality-center',
    routePath: '/review/quality',
    layout: 'quality-alerts',
    kpiKeys: ['alerts', 'severe', 'closed', 'aiSignals'],
    primary: { type: 'table', source: 'quality' },
    side: { type: 'actionList', source: 'quality' },
    actions: ['close', 'trace']
  },
  {
    moduleId: '10',
    title: '成本核算与效益中心',
    surface: 'review',
    routeName: 'review-cost-accounting',
    routePath: '/review/cost-accounting',
    layout: 'cost-stack',
    kpiKeys: ['unitCost', 'labor', 'energy', 'profit'],
    primary: { type: 'stackBars', source: 'cost' },
    side: { type: 'plan', source: 'cost' },
    actions: ['simulate']
  },
  {
    moduleId: '11',
    title: 'AI 总控中心',
    surface: 'review',
    routeName: 'review-brain-center',
    routePath: '/review/brain',
    layout: 'ai-brain',
    kpiKeys: ['summary', 'risks', 'actions', 'confidence'],
    primary: { type: 'insightList', source: 'brain' },
    side: { type: 'assistant', source: 'brain' },
    actions: ['ask', 'dispatch']
  },
  {
    moduleId: '12',
    title: '系统运维与可观测',
    legacyTitle: '系统运维与观测',
    surface: 'admin',
    routeName: 'admin-ops-reliability',
    routePath: '/admin/ops',
    layout: 'ops-observability',
    kpiKeys: ['health', 'availability', 'latency', 'errors'],
    primary: { type: 'timeline', source: 'ops' },
    side: { type: 'serviceList', source: 'ops' },
    actions: ['diagnose']
  },
  {
    moduleId: '13',
    title: '权限与治理中心',
    surface: 'admin',
    routeName: 'admin-governance-center',
    routePath: '/admin/governance',
    layout: 'governance-matrix',
    kpiKeys: ['roles', 'users', 'policies', 'exceptions'],
    primary: { type: 'matrix', source: 'governance' },
    side: { type: 'auditLog', source: 'governance' },
    actions: ['reviewPolicy']
  },
  {
    moduleId: '14',
    title: '主数据与模板中心',
    surface: 'admin',
    routeName: 'admin-master-workshop',
    routePath: '/admin/master',
    layout: 'master-templates',
    kpiKeys: ['workshops', 'templates', 'fields', 'users'],
    primary: { type: 'tileGrid', source: 'master' },
    side: { type: 'changeLog', source: 'master' },
    actions: ['editTemplate']
  },
  {
    moduleId: '15',
    title: '响应式录入体验',
    surface: 'entry',
    routeName: 'mobile-entry',
    routePath: '/entry',
    layout: 'responsive-entry',
    kpiKeys: ['mobile', 'tablet', 'desktop', 'entryFlow'],
    primary: { type: 'responsiveFrames', source: 'entryHome' },
    side: { type: 'checkList', source: 'entryHome' },
    actions: ['testEntry']
  }
])

export const modulesById = new Map(referenceModules.map((module) => [module.moduleId, module]))
export const modulesByRouteName = new Map(referenceModules.map((module) => [module.routeName, module]))

for (const module of referenceModules) {
  for (const routeName of module.alternateRouteNames || []) {
    modulesByRouteName.set(routeName, module)
  }
}

export const modulesBySurface = (surface) => referenceModules.filter((module) => module.surface === surface)
export const findModuleByRouteName = (routeName) => modulesByRouteName.get(routeName)
export const findModuleById = (moduleId) => modulesById.get(moduleId)
