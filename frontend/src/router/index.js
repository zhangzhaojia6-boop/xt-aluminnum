import { h } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'

import { resolveRouteMeta } from '../config/navigation'
import { useAuthStore } from '../stores/auth'

const Login = () => import('../views/Login.vue')
const EntryShell = () => import('../layout/EntryShell.vue')
const ManageShell = () => import('../layout/ManageShell.vue')
const MobileEntry = () => import('../views/mobile/MobileEntry.vue')
const AttendanceConfirm = () => import('../views/mobile/AttendanceConfirm.vue')
const ShiftReportForm = () => import('../views/mobile/ShiftReportForm.vue')
const DynamicEntryForm = () => import('../views/mobile/DynamicEntryForm.vue')
const CoilEntryWorkbench = () => import('../views/mobile/CoilEntryWorkbench.vue')
const UnifiedEntryForm = () => import('../views/mobile/UnifiedEntryForm.vue')
const OCRCapture = () => import('../views/mobile/OCRCapture.vue')
const ShiftReportHistory = () => import('../views/mobile/ShiftReportHistory.vue')
const EntryDrafts = () => import('../views/entry/EntryDrafts.vue')
const ReviewTaskCenter = () => import('../views/review/ReviewTaskCenter.vue')
const ShiftDetail = () => import('../views/shift/ShiftDetail.vue')
const ReconciliationCenter = () => import('../views/reconciliation/ReconciliationCenter.vue')
const ReconciliationDetail = () => import('../views/reconciliation/ReconciliationDetail.vue')
const AnomalyReview = () => import('../views/attendance/AnomalyReview.vue')
const QualityCenter = () => import('../views/quality/QualityCenter.vue')
const Statistics = () => import('../views/dashboard/Statistics.vue')
const CostAccountingCenter = () => import('../views/review/CostAccountingCenter.vue')
const ReportList = () => import('../views/reports/ReportList.vue')
const IngestionCenter = () => import('../views/review/IngestionCenter.vue')
const GovernanceCenter = () => import('../views/review/GovernanceCenter.vue')
const AiWorkstation = () => import('../views/ai/AiWorkstation.vue')
const Workshop = () => import('../views/master/Workshop.vue')
const AliasMapping = () => import('../views/master/AliasMapping.vue')
const ImportHistory = () => import('../views/imports/ImportHistory.vue')
const UserManagement = () => import('../views/master/UserManagement.vue')
const WorkshopTemplateConfig = () => import('../views/master/WorkshopTemplateConfig.vue')
const LiveDashboard = () => import('../views/reports/LiveDashboard.vue')
const FactoryDirector = () => import('../views/dashboard/FactoryDirector.vue')
const WorkshopDirector = () => import('../views/dashboard/WorkshopDirector.vue')
const FileImport = () => import('../views/imports/FileImport.vue')
const EnergyCenter = () => import('../views/energy/EnergyCenter.vue')
const AttendanceOverview = () => import('../views/attendance/AttendanceOverview.vue')
const AttendanceDetail = () => import('../views/attendance/AttendanceDetail.vue')
const ExceptionList = () => import('../views/attendance/ExceptionList.vue')
const ReportDetail = () => import('../views/reports/ReportDetail.vue')
const QualityDetail = () => import('../views/quality/QualityDetail.vue')
const QRCodePrint = () => import('../views/master/QRCodePrint.vue')
const FactoryOverview = () => import('../views/factory-command/FactoryOverview.vue')
const ProductionFlowScreen = () => import('../views/factory-command/ProductionFlowScreen.vue')
const MachineLineScreen = () => import('../views/factory-command/MachineLineScreen.vue')
const CoilTrace = () => import('../views/factory-command/CoilTrace.vue')
const CostBenefitScreen = () => import('../views/factory-command/CostBenefitScreen.vue')
const DestinationScreen = () => import('../views/factory-command/DestinationScreen.vue')
const ExceptionMap = () => import('../views/factory-command/ExceptionMap.vue')

const appTitle = import.meta.env.VITE_APP_TITLE || '鑫泰铝业'

const PlaceholderPage = {
  props: {
    title: { type: String, required: true },
    moduleNumber: { type: String, default: '' }
  },
  setup(props) {
    return () => h('div', { class: 'xt-placeholder-page' }, [
      h('div', { class: 'xt-placeholder-page__card' }, [
        h('h1', props.title),
        h('p', '功能正在迁移中')
      ])
    ])
  }
}

function page(title, moduleNumber = '') {
  return { render: () => h(PlaceholderPage, { title, moduleNumber }) }
}

function withMeta(route) {
  return {
    ...route,
    meta: resolveRouteMeta(route.name, route.meta),
    children: route.children?.map(withMeta)
  }
}

function isCompactClient() {
  if (typeof window === 'undefined') return false
  const userAgent = window.navigator?.userAgent || ''
  const matchesViewport = typeof window.matchMedia === 'function' && window.matchMedia('(max-width: 900px)').matches
  return matchesViewport || /MicroMessenger|wxwork|DingTalk|iPhone|iPad|Android|Mobile/i.test(userAgent)
}

function resolveRuntimeAuthCode(query = {}) {
  const candidates = [query.authCode, query.auth_code, query.code]
  return candidates.find((value) => typeof value === 'string' && value.trim()) || ''
}

function prefersMobileSurface(authStore, to) {
  if (!isCompactClient() || !authStore.canAccessFillSurface) return false
  if (to.meta.zone === 'entry' || to.name === 'login') return false
  if (typeof to.query?.desktop === 'string' && to.query.desktop === '1') return false
  return to.meta.zone === 'manage' || to.meta.zone === 'review' || to.meta.zone === 'desktop'
}

function reviewLanding(authStore) {
  if (authStore.canAccessReviewSurface) return { name: 'review-overview-home' }
  if (authStore.canAccessFactoryDashboard) return { name: 'factory-dashboard' }
  if (authStore.canAccessWorkshopDashboard) return { name: 'workshop-dashboard' }
  const config = configLanding(authStore)
  if (config.name !== 'login') return config
  return { name: 'login' }
}

function adminLanding(authStore) {
  if (authStore.adminSurface) return { name: 'admin-overview' }
  return { name: 'login' }
}

function configLanding(authStore) {
  if (authStore.adminSurface) return { name: 'admin-overview' }
  if (authStore.isAdmin || authStore.isManager) return { name: 'admin-overview' }
  return { name: 'login' }
}

function defaultLanding(authStore) {
  if (isCompactClient() && authStore.canAccessFillSurface) return { name: 'mobile-entry' }
  if (authStore.canAccessFillSurface && !authStore.canAccessReviewSurface) return { name: 'mobile-entry' }
  if (authStore.defaultSurface === 'admin') return adminLanding(authStore)
  if (authStore.defaultSurface === 'review') return reviewLanding(authStore)
  const review = reviewLanding(authStore)
  if (review.name !== 'login') return review
  if (authStore.canAccessFillSurface) return { name: 'mobile-entry' }
  return { name: 'login' }
}

const entryMeta = { requiresAuth: true, zone: 'entry', access: 'entry' }
const reviewMeta = { requiresAuth: true, zone: 'manage', access: 'review' }
const adminMeta = { requiresAuth: true, zone: 'manage', access: 'admin' }

const rawRoutes = [
  {
    path: '/login',
    name: 'login',
    component: Login,
    meta: { zone: 'public', access: 'public', title: '登录与角色入口', centerNo: '02', canonical: '/login' }
  },
  {
    path: '/entry',
    component: EntryShell,
    meta: { ...entryMeta, title: '独立填报端首页', centerNo: '03', canonical: '/entry' },
    children: [
      { path: '', name: 'mobile-entry', component: MobileEntry, meta: { ...entryMeta, title: '独立填报端首页', centerNo: '03', canonical: '/entry' } },
      { path: 'fill', name: 'mobile-unified-entry', component: UnifiedEntryForm, meta: { ...entryMeta, title: '填报', centerNo: '04', canonical: '/entry/fill' } },
      { path: 'report', redirect: { name: 'mobile-entry' } },
      { path: 'report/:businessDate/:shiftId', name: 'mobile-report-form', component: ShiftReportForm, meta: { ...entryMeta, title: '快速填报', centerNo: '04', canonical: '/entry/report/:businessDate/:shiftId' } },
      { path: 'advanced/:businessDate/:shiftId', name: 'mobile-report-form-advanced', component: DynamicEntryForm, meta: { ...entryMeta, title: '高项填报', centerNo: '04', canonical: '/entry/advanced/:businessDate/:shiftId' } },
      { path: 'coil/:businessDate/:shiftId', name: 'mobile-coil-entry', component: CoilEntryWorkbench, meta: { ...entryMeta, title: '按卷录入', centerNo: '04', canonical: '/entry/coil/:businessDate/:shiftId' } },
      { path: 'ocr/:businessDate/:shiftId', name: 'mobile-ocr-capture', component: OCRCapture, meta: { ...entryMeta, title: 'OCR 试验录入', centerNo: '04', canonical: '/entry/ocr/:businessDate/:shiftId' } },
      { path: 'attendance', name: 'mobile-attendance-confirm', component: AttendanceConfirm, meta: { ...entryMeta, title: '异常补录', centerNo: '03', canonical: '/entry/attendance' } },
      { path: 'anomaly', name: 'entry-anomaly', redirect: { name: 'mobile-attendance-confirm' } },
      { path: 'history', name: 'mobile-report-history', component: ShiftReportHistory, meta: { ...entryMeta, title: '历史记录', centerNo: '03', canonical: '/entry/history' } },
      { path: 'shift-history', redirect: { name: 'mobile-report-history' } },
      { path: 'drafts', name: 'entry-drafts', component: EntryDrafts, meta: { ...entryMeta, title: '草稿箱', centerNo: '03', canonical: '/entry/drafts' } },
      { path: 'profile', name: 'entry-profile', component: MobileEntry, meta: { ...entryMeta, title: '我的', centerNo: '03' } },
      { path: 'dynamic-entry-form', name: 'dynamic-entry-form', redirect: { name: 'mobile-entry' } }
    ]
  },
  {
    path: '/manage',
    component: ManageShell,
    meta: { ...reviewMeta, title: '管理工作台', canonical: '/manage' },
    children: [
      { path: '', redirect: '/manage/overview' },
      { path: 'overview', name: 'review-overview-home', component: FactoryOverview, alias: ['dashboard'], meta: { ...reviewMeta, title: '工厂总览', centerNo: '01', canonical: '/manage/overview' } },
      { path: 'factory/flow', name: 'factory-command-flow', component: ProductionFlowScreen, meta: { ...reviewMeta, title: '生产流转', centerNo: '05', canonical: '/manage/factory/flow' } },
      { path: 'factory/machine-lines', name: 'factory-command-machine-lines', component: MachineLineScreen, meta: { ...reviewMeta, title: '车间机列', centerNo: '05', canonical: '/manage/factory/machine-lines' } },
      { path: 'factory/coils', name: 'factory-command-coils', component: CoilTrace, meta: { ...reviewMeta, title: '卷级追踪', centerNo: '05', canonical: '/manage/factory/coils' } },
      { path: 'factory/cost', name: 'factory-command-cost', component: CostBenefitScreen, meta: { ...reviewMeta, title: '经营效益', centerNo: '10', canonical: '/manage/factory/cost' } },
      { path: 'factory/destinations', name: 'factory-command-destinations', component: DestinationScreen, meta: { ...reviewMeta, title: '库存去向', centerNo: '05', canonical: '/manage/factory/destinations' } },
      { path: 'factory/exceptions', name: 'factory-command-exceptions', component: ExceptionMap, meta: { ...reviewMeta, title: '异常地图', centerNo: '09', canonical: '/manage/factory/exceptions' } },
      { path: 'factory', name: 'factory-dashboard', component: FactoryDirector, meta: { ...reviewMeta, title: '工厂作业看板', centerNo: '05', canonical: '/manage/factory' } },
      { path: 'workshop', name: 'workshop-dashboard', component: WorkshopDirector, meta: { ...reviewMeta, title: '车间作业看板', centerNo: '05', canonical: '/manage/workshop' } },
      { path: 'entry-center', name: 'review-task-center', component: ReviewTaskCenter, meta: { ...reviewMeta, title: '审阅中心', centerNo: '07', canonical: '/manage/entry-center' } },
      { path: 'shift', redirect: '/manage/master' },
      { path: 'reconciliation', name: 'review-reconciliation-center', component: ReconciliationCenter, meta: { ...reviewMeta, title: '差异核对中心', centerNo: '09', canonical: '/manage/reconciliation' } },
      { path: 'reconciliation/detail/:id', name: 'reconciliation-detail', component: ReconciliationDetail, meta: { ...reviewMeta, title: '差异详情' } },
      { path: 'anomaly', name: 'manage-anomaly', component: AnomalyReview, meta: { ...reviewMeta, title: '异常审核', canonical: '/manage/anomaly' } },
      { path: 'quality', name: 'review-quality-center', component: QualityCenter, meta: { ...reviewMeta, title: '质量与告警中心', centerNo: '09', canonical: '/manage/quality' } },
      { path: 'quality/detail/:id', name: 'quality-detail', component: QualityDetail, meta: { ...reviewMeta, title: '质量详情' } },
      { path: 'statistics', name: 'statistics-dashboard', component: Statistics, meta: { ...reviewMeta, title: '统计中心', canonical: '/manage/statistics' } },
      { path: 'cost', name: 'review-cost-accounting', component: CostAccountingCenter, meta: { ...reviewMeta, title: '成本核算与效益中心', centerNo: '10', canonical: '/manage/cost' } },
      { path: 'reports', name: 'review-report-center', component: ReportList, meta: { ...reviewMeta, title: '日报与交付中心', centerNo: '08', canonical: '/manage/reports' } },
      { path: 'reports/detail/:id', name: 'report-detail', component: ReportDetail, meta: { ...reviewMeta, title: '日报详情' } },
      { path: 'ingestion', name: 'admin-ingestion-center', component: IngestionCenter, meta: { ...adminMeta, title: '数据接入与字段映射中心', centerNo: '06', canonical: '/manage/ingestion' } },
      { path: 'master', name: 'admin-master-workshop', component: Workshop, meta: { ...adminMeta, title: '主数据与模板中心', centerNo: '14', canonical: '/manage/master' } },
      { path: 'alias', name: 'manage-alias', component: AliasMapping, meta: { ...adminMeta, title: '别名映射', canonical: '/manage/alias' } },
      { path: 'imports', name: 'manage-imports', component: ImportHistory, meta: { ...adminMeta, title: '导入历史', canonical: '/manage/imports' } },
      { path: 'ai', name: 'review-brain-center', component: AiWorkstation, meta: { ...reviewMeta, title: 'AI 工作台', centerNo: '11', canonical: '/manage/ai' } },
      { path: 'ai-assistant', name: 'factory-ai-assistant', component: AiWorkstation, meta: { ...reviewMeta, title: 'AI 助手', centerNo: '11', canonical: '/manage/ai-assistant' } },
      { path: 'admin', name: 'admin-overview', component: page('管理控制台', '14'), meta: { ...adminMeta, title: '管理控制台', centerNo: '14', canonical: '/manage/admin' } },
      { path: 'admin/settings', name: 'admin-ops-reliability', component: LiveDashboard, meta: { ...adminMeta, title: '系统设置', centerNo: '12', canonical: '/manage/admin/settings' } },
      { path: 'admin/users', name: 'admin-users', component: UserManagement, meta: { ...adminMeta, title: '用户管理', centerNo: '13', canonical: '/manage/admin/users' } },
      { path: 'admin/governance', name: 'admin-governance-center', component: GovernanceCenter, meta: { ...adminMeta, title: '权限与治理中心', centerNo: '13', canonical: '/manage/admin/governance' } },
      { path: 'admin/templates', name: 'admin-template-center', component: WorkshopTemplateConfig, meta: { ...adminMeta, title: '模板中心', centerNo: '14', canonical: '/manage/admin/templates' } },
      { path: 'admin/ops', redirect: { name: 'admin-ops-reliability' } },
      { path: 'admin/master', redirect: { name: 'admin-master-workshop' } },
      { path: 'admin/qr-print', name: 'admin-qr-print', component: QRCodePrint, meta: { ...adminMeta, title: 'QR 码打印', canonical: '/manage/admin/qr-print' } }
    ]
  },
  { path: '/review', redirect: '/manage/overview' },
  { path: '/review/overview', redirect: '/manage/overview' },
  { path: '/review/factory', redirect: '/manage/factory' },
  { path: '/review/workshop', redirect: '/manage/workshop' },
  { path: '/review/tasks', redirect: '/manage/entry-center' },
  { path: '/review/reports', redirect: '/manage/reports' },
  { path: '/review/quality', redirect: '/manage/quality' },
  { path: '/review/reconciliation', redirect: '/manage/reconciliation' },
  { path: '/review/ingestion', name: 'review-ingestion-center', redirect: '/manage/ingestion' },
  { path: '/review/ops', name: 'review-ops-reliability', redirect: '/manage/admin/settings' },
  { path: '/review/governance', name: 'review-governance-center', redirect: '/manage/admin/governance' },
  { path: '/review/templates', name: 'review-template-center', redirect: '/manage/admin/templates' },
  { path: '/review/cost-accounting', redirect: '/manage/cost' },
  { path: '/review/cost', redirect: '/manage/cost' },
  { path: '/review/roadmap', redirect: '/manage/overview' },
  { path: '/review/brain', redirect: '/manage/ai' },
  { path: '/review/:pathMatch(.*)*', redirect: '/manage/overview' },
  { path: '/admin', redirect: '/manage/admin' },
  { path: '/admin/overview', redirect: '/manage/admin' },
  { path: '/admin/ingestion', redirect: '/manage/ingestion' },
  { path: '/admin/master', redirect: '/manage/master' },
  { path: '/admin/master/workshop', redirect: '/manage/master' },
  { path: '/admin/master/templates', redirect: '/manage/admin/templates' },
  { path: '/admin/templates', redirect: '/manage/admin/templates' },
  { path: '/admin/users', redirect: '/manage/admin/users' },
  { path: '/admin/governance', redirect: '/manage/admin/governance' },
  { path: '/admin/ops', redirect: '/manage/admin/settings' },
  { path: '/admin/:pathMatch(.*)*', redirect: '/manage/admin/settings' },
  { path: '/mobile', redirect: (to) => ({ path: '/entry', query: to.query, hash: to.hash }) },
  { path: '/mobile/report/:businessDate/:shiftId', redirect: (to) => ({ path: `/entry/report/${to.params.businessDate}/${to.params.shiftId}`, query: to.query, hash: to.hash }) },
  { path: '/mobile/report-advanced/:businessDate/:shiftId', redirect: (to) => ({ path: `/entry/advanced/${to.params.businessDate}/${to.params.shiftId}`, query: to.query, hash: to.hash }) },
  { path: '/mobile/ocr/:businessDate/:shiftId', redirect: (to) => ({ path: `/entry/ocr/${to.params.businessDate}/${to.params.shiftId}`, query: to.query, hash: to.hash }) },
  { path: '/mobile/attendance', redirect: (to) => ({ path: '/entry/attendance', query: to.query, hash: to.hash }) },
  { path: '/mobile/history', redirect: (to) => ({ path: '/entry/history', query: to.query, hash: to.hash }) },
  { path: '/worker', redirect: (to) => ({ name: 'mobile-entry', query: to.query, hash: to.hash }) },
  { path: '/factory', redirect: '/manage/factory' },
  { path: '/workshop', redirect: '/manage/workshop' },
  { path: '/ingestion/mapping', redirect: '/manage/ingestion' },
  { path: '/reports/delivery', redirect: '/manage/reports' },
  { path: '/alerts/quality', redirect: '/manage/quality' },
  { path: '/ops/reliability', redirect: '/manage/admin/settings' },
  { path: '/governance', redirect: '/manage/admin/governance' },
  { path: '/cost/accounting', redirect: '/manage/cost' },
  { path: '/roadmap/next', redirect: '/manage/overview' },
  { path: '/dashboard', redirect: '/manage/overview' },
  { path: '/dashboard/factory', redirect: '/manage/factory' },
  { path: '/dashboard/workshop', redirect: '/manage/workshop' },
  { path: '/dashboard/statistics', redirect: '/manage/statistics' },
  { path: '/imports/files', name: 'file-import', component: FileImport, meta: { ...adminMeta, title: '文件上传' } },
  { path: '/imports/history', redirect: '/manage/imports' },
  { path: '/energy/center', name: 'energy-center', component: EnergyCenter, meta: { ...reviewMeta, title: '能源中心' } },
  { path: '/attendance/overview', name: 'attendance-overview', component: AttendanceOverview, meta: { ...reviewMeta, title: '考勤总览' } },
  { path: '/attendance/detail/:employeeId/:businessDate', name: 'attendance-detail', component: AttendanceDetail, meta: { ...reviewMeta, title: '考勤详情' } },
  { path: '/attendance/exceptions', name: 'attendance-exceptions', component: ExceptionList, meta: { ...reviewMeta, title: '异常列表' } },
  { path: '/shift/detail/:id', name: 'shift-detail', component: ShiftDetail, meta: { ...reviewMeta, title: '班次详情' } },
  { path: '/reports/list', redirect: '/manage/reports' },
  { path: '/reports/detail/:id', redirect: (to) => `/manage/reports/detail/${to.params.id}` },
  { path: '/quality/center', redirect: '/manage/quality' },
  { path: '/quality/detail/:id', redirect: (to) => `/manage/quality/detail/${to.params.id}` },
  { path: '/reconciliation/center', redirect: '/manage/reconciliation' },
  { path: '/reconciliation/detail/:id', redirect: (to) => `/manage/reconciliation/detail/${to.params.id}` },
  { path: '/master', redirect: '/manage/master' },
  { path: '/master/workshop', name: 'master-workshop', redirect: '/manage/master' },
  { path: '/master/team', name: 'master-team', redirect: '/manage/master' },
  { path: '/master/employee', name: 'master-employee', redirect: '/manage/master' },
  { path: '/master/equipment', name: 'master-equipment', redirect: '/manage/master' },
  { path: '/master/users', name: 'master-users', redirect: '/manage/admin/users' },
  { path: '/master/shift-config', name: 'master-shift-config', redirect: '/manage/master' },
  { path: '/master/alias', name: 'master-alias', redirect: '/manage/alias' },
  { path: '/master/yield-rate-map', name: 'master-yield-rate-map', redirect: '/manage/admin/templates' },
  { path: '/master/workshop-template', name: 'master-workshop-template', redirect: '/manage/admin/templates' },
  { path: '/master/workshop-templates', redirect: '/manage/admin/templates' },
  { path: '/', redirect: '/manage/overview' },
  { path: '/:pathMatch(.*)*', redirect: '/manage/overview' }
]

const routes = rawRoutes.map(withMeta)

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  }
})

export function installRouterGuards(routerInstance, authStore) {
  routerInstance.beforeEach(async (to) => {
    const auth = authStore || useAuthStore()
    const matchedAccess = [...to.matched].reverse().find((record) => record.meta?.access)?.meta.access
    const access = to.meta.access || matchedAccess
    const hasRuntimeAuthCode = to.name === 'mobile-entry' && Boolean(resolveRuntimeAuthCode(to.query))

    if (auth.token && to.name === 'login') {
      return defaultLanding(auth)
    }

    if (access === 'public') {
      document.title = to.meta.title ? `${to.meta.title} - ${appTitle}` : appTitle
      return true
    }

    if (to.meta.requiresAuth && !auth.token) {
      if (hasRuntimeAuthCode) {
        document.title = to.meta.title ? `${to.meta.title} - ${appTitle}` : appTitle
        return true
      }
      return { name: 'login', query: { redirect: to.fullPath } }
    }

    if (!auth.token) {
      document.title = to.meta.title ? `${to.meta.title} - ${appTitle}` : appTitle
      return true
    }

    if (!auth.user) {
      try {
        await auth.fetchProfile()
      } catch {
        return { name: 'login', query: { redirect: to.fullPath } }
      }
    }

    if (auth.isFillOnlyRole && to.meta.zone !== 'entry' && to.name !== 'login') {
      return { name: 'mobile-entry' }
    }

    if (prefersMobileSurface(auth, to)) {
      return { name: 'mobile-entry' }
    }

    if (to.meta.zone === 'entry' && !auth.canAccessFillSurface) {
      return auth.canAccessReviewSurface ? reviewLanding(auth) : { name: 'login' }
    }
    if ((to.meta.zone === 'review' || to.meta.zone === 'manage') && access !== 'admin' && !auth.canAccessReviewSurface) {
      return auth.canAccessFillSurface ? { name: 'mobile-entry' } : { name: 'login' }
    }
    if (access === 'admin' && !auth.adminSurface) {
      return defaultLanding(auth)
    }
    if (to.meta.zone === 'desktop' && !auth.adminSurface) {
      return defaultLanding(auth)
    }

    if (access === 'entry' && !auth.canAccessFillSurface) {
      return defaultLanding(auth)
    }
    if (access === 'review' && !auth.canAccessReviewSurface) {
      return defaultLanding(auth)
    }
    if (access === 'review' && !auth.canAccessReviewDesk) {
      return defaultLanding(auth)
    }
    if (access === 'review_surface' && !auth.canAccessReviewSurface) {
      return defaultLanding(auth)
    }
    if (access === 'desktop_config' && !auth.adminSurface) {
      return defaultLanding(auth)
    }
    if (access === 'manager' && !(auth.isAdmin || auth.isManager)) {
      return defaultLanding(auth)
    }
    if (access === 'admin_strict' && !auth.isAdmin) {
      return defaultLanding(auth)
    }
    if (access === 'factory_dashboard' && !auth.canAccessFactoryDashboard) {
      return defaultLanding(auth)
    }
    if (access === 'workshop_dashboard' && !auth.canAccessWorkshopDashboard) {
      return defaultLanding(auth)
    }
    if (access === 'statistics_dashboard' && !auth.canAccessStatisticsDashboard) {
      return defaultLanding(auth)
    }

    document.title = to.meta.title ? `${to.meta.title} - ${appTitle}` : appTitle
    return true
  })
}

export default router
