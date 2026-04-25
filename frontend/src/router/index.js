import { createRouter, createWebHistory } from 'vue-router'

import { resolveRouteMeta } from '../config/navigation'
import { useAuthStore } from '../stores/auth'

const Layout = () => import('../views/Layout.vue')
const CommandLogin = () => import('../reference-command/pages/CommandLogin.vue')
const CommandEntryHome = () => import('../reference-command/pages/CommandEntryHome.vue')
const CommandEntryFlow = () => import('../reference-command/pages/CommandEntryFlow.vue')
const CommandOverview = () => import('../reference-command/pages/CommandOverview.vue')
const CommandModulePage = () => import('../reference-command/pages/CommandModulePage.vue')
const CommandReviewTasks = () => import('../reference-command/pages/CommandReviewTasks.vue')
const EntryShell = () => import('../layout/EntryShell.vue')
const ReviewShell = () => import('../layout/ReviewShell.vue')
const AdminShell = () => import('../layout/AdminShell.vue')
const WorkshopDirector = () => import('../views/dashboard/WorkshopDirector.vue')
const Statistics = () => import('../views/dashboard/Statistics.vue')
const FileImport = () => import('../views/imports/FileImport.vue')
const ImportHistory = () => import('../views/imports/ImportHistory.vue')
const EnergyCenter = () => import('../views/energy/EnergyCenter.vue')
const AttendanceOverview = () => import('../views/attendance/AttendanceOverview.vue')
const ExceptionList = () => import('../views/attendance/ExceptionList.vue')
const AttendanceDetail = () => import('../views/attendance/AttendanceDetail.vue')
const ShiftCenter = () => import('../views/shift/ShiftCenter.vue')
const ShiftDetail = () => import('../views/shift/ShiftDetail.vue')
const ReportList = () => import('../views/reports/ReportList.vue')
const ReportDetail = () => import('../views/reports/ReportDetail.vue')
const ReconciliationCenter = () => import('../views/reconciliation/ReconciliationCenter.vue')
const ReconciliationDetail = () => import('../views/reconciliation/ReconciliationDetail.vue')
const QualityCenter = () => import('../views/quality/QualityCenter.vue')
const QualityDetail = () => import('../views/quality/QualityDetail.vue')
const AttendanceConfirm = () => import('../views/mobile/AttendanceConfirm.vue')
const ShiftReportForm = () => import('../views/mobile/ShiftReportForm.vue')
const DynamicEntryForm = () => import('../views/mobile/DynamicEntryForm.vue')
const OCRCapture = () => import('../views/mobile/OCRCapture.vue')
const ShiftReportHistory = () => import('../views/mobile/ShiftReportHistory.vue')
const EntryDrafts = () => import('../views/entry/EntryDrafts.vue')
const AnomalyReview = () => import('../views/attendance/AnomalyReview.vue')

const appTitle = import.meta.env.VITE_APP_TITLE || '鑫泰铝业'

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
  return to.meta.zone === 'review' || to.meta.zone === 'desktop'
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

function withMeta(route) {
  const next = { ...route }
  if (next.name) {
    next.meta = resolveRouteMeta(next.name, next.meta || {})
  }
  if (Array.isArray(next.children) && next.children.length) {
    next.children = next.children.map(withMeta)
  }
  return next
}

const rawRoutes = [
  {
    path: '/login',
    name: 'login',
    component: CommandLogin,
    meta: { zone: 'public', access: 'public', title: '登录与角色入口', centerNo: '02', canonical: '/login' }
  },
  {
    path: '/entry',
    component: EntryShell,
    meta: { requiresAuth: true, title: '独立填报端首页', zone: 'entry', access: 'entry', centerNo: '03', canonical: '/entry' },
    children: [
      {
        path: '',
        name: 'mobile-entry',
        component: CommandEntryHome,
        meta: { requiresAuth: true, title: '独立填报端首页', zone: 'entry', access: 'entry', centerNo: '03', canonical: '/entry' }
      },
      {
        path: 'dynamic-entry-form',
        name: 'dynamic-entry-form',
        component: CommandEntryFlow,
        meta: { requiresAuth: true, title: '填报流程', zone: 'entry', access: 'entry', centerNo: '04', canonical: '/entry/report', legacy: true }
      },
      {
        path: 'report/:businessDate/:shiftId',
        name: 'mobile-report-form',
        component: ShiftReportForm,
        meta: { requiresAuth: true, title: '快速填报', zone: 'entry', access: 'entry', centerNo: '04', canonical: '/entry/report/:businessDate/:shiftId' }
      },
      {
        path: 'advanced/:businessDate/:shiftId',
        name: 'mobile-report-form-advanced',
        component: DynamicEntryForm,
        meta: { requiresAuth: true, title: '高项填报', zone: 'entry', access: 'entry', centerNo: '04', canonical: '/entry/advanced/:businessDate/:shiftId' }
      },
      {
        path: 'ocr/:businessDate/:shiftId',
        name: 'mobile-ocr-capture',
        component: OCRCapture,
        meta: { requiresAuth: true, title: 'OCR 试验录入', zone: 'entry', access: 'entry', centerNo: '04', canonical: '/entry/ocr/:businessDate/:shiftId' }
      },
      {
        path: 'attendance',
        name: 'mobile-attendance-confirm',
        component: AttendanceConfirm,
        meta: { requiresAuth: true, title: '异常补录', zone: 'entry', access: 'entry', centerNo: '03', canonical: '/entry/attendance' }
      },
      {
        path: 'anomaly',
        name: 'entry-anomaly',
        redirect: { name: 'mobile-attendance-confirm' }
      },
      {
        path: 'history',
        name: 'mobile-report-history',
        component: ShiftReportHistory,
        meta: { requiresAuth: true, title: '历史记录', zone: 'entry', access: 'entry', centerNo: '03', canonical: '/entry/history' }
      },
      {
        path: 'drafts',
        name: 'entry-drafts',
        component: EntryDrafts,
        meta: { requiresAuth: true, title: '草稿箱', zone: 'entry', access: 'entry', centerNo: '03', canonical: '/entry/drafts' }
      }
    ]
  },
  {
    path: '/mobile',
    redirect: (to) => ({ path: '/entry', query: to.query, hash: to.hash }),
    meta: { zone: 'legacy', access: 'entry', title: '移动填报兼容入口', canonical: '/entry' }
  },
  {
    path: '/mobile/report/:businessDate/:shiftId',
    redirect: (to) => ({ path: `/entry/report/${to.params.businessDate}/${to.params.shiftId}`, query: to.query, hash: to.hash })
  },
  {
    path: '/mobile/report-advanced/:businessDate/:shiftId',
    redirect: (to) => ({ path: `/entry/advanced/${to.params.businessDate}/${to.params.shiftId}`, query: to.query, hash: to.hash })
  },
  {
    path: '/mobile/ocr/:businessDate/:shiftId',
    redirect: (to) => ({ path: `/entry/ocr/${to.params.businessDate}/${to.params.shiftId}`, query: to.query, hash: to.hash })
  },
  {
    path: '/mobile/attendance',
    redirect: (to) => ({ path: '/entry/attendance', query: to.query, hash: to.hash })
  },
  {
    path: '/mobile/history',
    redirect: (to) => ({ path: '/entry/history', query: to.query, hash: to.hash })
  },
  {
    path: '/worker',
    redirect: (to) => ({ name: 'mobile-entry', query: to.query, hash: to.hash })
  },
  {
    path: '/admin',
    component: AdminShell,
    meta: { requiresAuth: true, title: '管理控制台', zone: 'admin', access: 'admin', canonical: '/admin' },
    children: [
      {
        path: '',
        name: 'admin-overview',
        component: CommandModulePage,
        props: { moduleId: '14' },
        meta: { title: '主数据与模板中心', zone: 'admin', access: 'admin', centerNo: '14', moduleId: '14', canonical: '/admin' }
      },
      {
        path: 'overview',
        redirect: { name: 'admin-overview' },
        meta: { title: '管理总览', zone: 'admin', access: 'admin', centerNo: '14', legacy: true, canonical: '/admin' }
      },
      {
        path: 'ingestion',
        name: 'admin-ingestion-center',
        component: CommandModulePage,
        props: { moduleId: '06' },
        meta: { title: '数据接入与字段映射中心', zone: 'admin', access: 'admin', centerNo: '06', moduleId: '06', canonical: '/admin/ingestion' }
      },
      {
        path: 'ingestion-center',
        name: 'ingestion-center',
        redirect: { name: 'admin-ingestion-center' },
        meta: { title: '数据接入中心兼容入口', zone: 'admin', access: 'admin', centerNo: '06', legacy: true, canonical: '/admin/ingestion' }
      },
      {
        path: 'field-mapping',
        redirect: { name: 'admin-ingestion-center' },
        meta: { title: '字段映射', zone: 'admin', access: 'admin', centerNo: '06', legacy: true, canonical: '/admin/ingestion' }
      },
      {
        path: 'ops',
        name: 'admin-ops-reliability',
        component: CommandModulePage,
        props: { moduleId: '12' },
        meta: { title: '系统运维与观测', zone: 'admin', access: 'admin', centerNo: '12', moduleId: '12', canonical: '/admin/ops' }
      },
      {
        path: 'ops-reliability',
        redirect: { name: 'admin-ops-reliability' },
        meta: { title: '系统运维兼容入口', zone: 'admin', access: 'admin', centerNo: '12', legacy: true, canonical: '/admin/ops' }
      },
      {
        path: 'ops-center',
        name: 'ops-reliability',
        redirect: { name: 'admin-ops-reliability' },
        meta: { title: '系统运维兼容入口', zone: 'admin', access: 'admin', centerNo: '12', legacy: true, canonical: '/admin/ops' }
      },
      {
        path: 'governance',
        name: 'admin-governance-center',
        component: CommandModulePage,
        props: { moduleId: '13' },
        meta: { title: '权限与治理中心', zone: 'admin', access: 'admin', centerNo: '13', moduleId: '13', canonical: '/admin/governance' }
      },
      {
        path: 'governance-center',
        name: 'governance-center',
        redirect: { name: 'admin-governance-center' },
        meta: { title: '权限治理兼容入口', zone: 'admin', access: 'admin', centerNo: '13', legacy: true, canonical: '/admin/governance' }
      },
      {
        path: 'master',
        name: 'admin-master-workshop',
        component: CommandModulePage,
        props: { moduleId: '14' },
        meta: { title: '主数据与模板中心', zone: 'admin', access: 'admin', centerNo: '14', moduleId: '14', canonical: '/admin/master' }
      },
      {
        path: 'master/workshop',
        redirect: { name: 'admin-master-workshop' },
        meta: { title: '主数据中心', zone: 'admin', access: 'admin', centerNo: '14', legacy: true, canonical: '/admin/master' }
      },
      {
        path: 'master/templates',
        name: 'admin-template-center',
        component: CommandModulePage,
        props: { moduleId: '14' },
        meta: { title: '主数据与模板中心', zone: 'admin', access: 'admin', centerNo: '14', moduleId: '14', canonical: '/admin/master/templates' }
      },
      {
        path: 'workshop-template-config',
        name: 'workshop-template-config',
        redirect: { name: 'admin-template-center' },
        meta: { title: '主数据与模板中心', zone: 'admin', access: 'admin', centerNo: '14', legacy: true, canonical: '/admin/master/templates' }
      },
      {
        path: 'templates',
        redirect: { name: 'admin-template-center' },
        meta: { title: '模板配置', zone: 'admin', access: 'admin', centerNo: '14', legacy: true, canonical: '/admin/master/templates' }
      },
      {
        path: 'users',
        name: 'admin-users',
        component: CommandModulePage,
        props: { moduleId: '13' },
        meta: { title: '用户与角色', zone: 'admin', access: 'admin', centerNo: '13', moduleId: '13', canonical: '/admin/users' }
      },
      {
        path: 'master/users',
        redirect: { name: 'admin-users' },
        meta: { title: '用户与角色', zone: 'admin', access: 'admin', centerNo: '13', legacy: true, canonical: '/admin/users' }
      },
      {
        path: 'roadmap',
        redirect: { name: 'admin-overview' },
        meta: { title: '路线图兼容入口', zone: 'legacy', access: 'admin', legacy: true, canonical: '/admin' }
      }
    ]
  },
  {
    path: '/review',
    component: ReviewShell,
    meta: { requiresAuth: true, zone: 'review', access: 'review', title: '审阅端', canonical: '/review/overview' },
    redirect: '/review/overview',
    children: [
      {
        path: 'overview',
        name: 'review-overview-home',
        component: CommandOverview,
        meta: { title: '系统总览主视图', zone: 'review', access: 'review', centerNo: '01', moduleId: '01', canonical: '/review/overview' }
      },
      {
        path: 'tasks',
        name: 'review-task-center',
        component: CommandReviewTasks,
        meta: { title: '审阅中心', zone: 'review', access: 'review', centerNo: '07', moduleId: '07', canonical: '/review/tasks' }
      },
      {
        path: 'factory',
        name: 'factory-dashboard',
        component: CommandModulePage,
        props: { moduleId: '05' },
        meta: { title: '工厂作业看板', zone: 'review', access: 'review', centerNo: '05', moduleId: '05', canonical: '/review/factory' }
      },
      {
        path: 'workshop',
        name: 'workshop-dashboard',
        component: WorkshopDirector,
        meta: { title: '车间审阅端', zone: 'review', access: 'review', centerNo: '05', canonical: '/review/workshop' }
      },
      {
        path: 'ingestion',
        name: 'review-ingestion-center',
        redirect: { name: 'admin-ingestion-center' },
        meta: { title: '数据接入中心兼容入口', zone: 'legacy', access: 'admin', centerNo: '06', legacy: true, canonical: '/admin/ingestion' }
      },
      {
        path: 'reports',
        name: 'review-report-center',
        component: CommandModulePage,
        props: { moduleId: '08' },
        meta: { title: '日报与交付中心', zone: 'review', access: 'review', centerNo: '08', moduleId: '08', canonical: '/review/reports' }
      },
      {
        path: 'quality',
        name: 'review-quality-center',
        component: CommandModulePage,
        props: { moduleId: '09' },
        meta: { title: '质量与告警中心', zone: 'review', access: 'review', centerNo: '09', moduleId: '09', canonical: '/review/quality' }
      },
      {
        path: 'reconciliation',
        name: 'review-reconciliation-center',
        component: ReconciliationCenter,
        meta: { title: '质量与告警中心', zone: 'review', access: 'review', centerNo: '09', canonical: '/review/reconciliation' }
      },
      {
        path: 'ops-reliability',
        name: 'review-ops-reliability',
        redirect: { name: 'admin-ops-reliability' },
        meta: { title: '系统运维兼容入口', zone: 'legacy', access: 'admin', centerNo: '12', legacy: true, canonical: '/admin/ops' }
      },
      {
        path: 'cost-accounting',
        name: 'review-cost-accounting',
        component: CommandModulePage,
        props: { moduleId: '10' },
        meta: { title: '成本核算与效益中心', zone: 'review', access: 'review', centerNo: '10', moduleId: '10', canonical: '/review/cost-accounting' }
      },
      {
        path: 'cost-accounting-center',
        name: 'cost-accounting-center',
        redirect: { name: 'review-cost-accounting' },
        meta: { title: '成本核算与效益中心', zone: 'legacy', access: 'review', centerNo: '10', legacy: true, canonical: '/review/cost-accounting' }
      },
      {
        path: 'brain',
        name: 'review-brain-center',
        component: CommandModulePage,
        props: { moduleId: '11' },
        meta: { title: 'AI 总控中心', zone: 'review', access: 'review', centerNo: '11', moduleId: '11', canonical: '/review/brain' }
      },
      {
        path: 'brain-center',
        name: 'brain-center',
        redirect: { name: 'review-brain-center' },
        meta: { title: 'AI 总控中心', zone: 'legacy', access: 'review', centerNo: '11', legacy: true, canonical: '/review/brain' }
      },
      {
        path: 'governance',
        name: 'review-governance-center',
        redirect: { name: 'admin-governance-center' },
        meta: { title: '权限治理兼容入口', zone: 'legacy', access: 'admin', centerNo: '13', legacy: true, canonical: '/admin/governance' }
      },
      {
        path: 'roadmap',
        redirect: { name: 'review-overview-home' },
        meta: { title: '路线图兼容入口', zone: 'legacy', access: 'review', legacy: true, canonical: '/review/overview' }
      },
      {
        path: 'template-center',
        name: 'review-template-center',
        redirect: { name: 'admin-template-center' },
        meta: { title: '模板中心兼容入口', zone: 'legacy', access: 'admin', centerNo: '14', legacy: true, canonical: '/admin/master/templates' }
      }
    ]
  },
  { path: '/factory', redirect: '/review/factory' },
  { path: '/workshop', redirect: '/review/workshop' },
  { path: '/ingestion/mapping', redirect: '/admin/ingestion' },
  { path: '/reports/delivery', redirect: '/review/reports' },
  { path: '/alerts/quality', redirect: '/review/quality' },
  { path: '/ops/reliability', redirect: '/admin/ops' },
  { path: '/governance', redirect: '/admin/governance' },
  { path: '/cost/accounting', redirect: '/review/cost-accounting' },
  { path: '/roadmap/next', redirect: '/review/overview' },
  { path: '/dashboard', redirect: { path: '/review/overview' }, meta: { zone: 'legacy', access: 'review', canonical: '/review/overview' } },
  { path: '/dashboard/factory', redirect: '/review/factory' },
  { path: '/dashboard/workshop', redirect: '/review/workshop' },
  { path: '/dashboard/statistics', redirect: '/review/factory' },
  { path: '/master', redirect: { path: '/admin/master' }, meta: { zone: 'legacy', access: 'admin', canonical: '/admin/master' } },
  {
    path: '/',
    component: Layout,
    meta: { requiresAuth: true, zone: 'legacy', access: 'admin', canonical: '/admin/master' },
    redirect: '/admin/master/workshop',
    children: [
      { path: 'dashboard/factory', redirect: '/review/factory' },
      { path: 'dashboard/workshop', redirect: '/review/workshop' },
      { path: 'dashboard/statistics', redirect: '/review/factory' },
      { path: 'dashboard/statistics-review', redirect: '/dashboard/statistics' },
      {
        path: 'imports/files',
        name: 'file-import',
        component: FileImport,
        meta: { title: '文件上传', zone: 'desktop', access: 'review' }
      },
      {
        path: 'imports/history',
        name: 'import-history',
        component: ImportHistory,
        meta: { title: '导入历史', zone: 'desktop', access: 'review' }
      },
      {
        path: 'energy/center',
        name: 'energy-center',
        component: EnergyCenter,
        meta: { title: '能耗中心', zone: 'desktop', access: 'review' }
      },
      {
        path: 'attendance/overview',
        name: 'attendance-overview',
        component: AttendanceOverview,
        meta: { title: '考勤总览', zone: 'desktop', access: 'review' }
      },
      {
        path: 'attendance/exceptions',
        name: 'attendance-exceptions',
        component: ExceptionList,
        meta: { title: '异常清单', zone: 'desktop', access: 'review' }
      },
      {
        path: 'attendance/anomalies',
        name: 'attendance-anomaly-review',
        component: AnomalyReview,
        meta: { title: '考勤异常处置', zone: 'desktop', access: 'review' }
      },
      {
        path: 'attendance/detail/:employeeId/:businessDate',
        name: 'attendance-detail',
        component: AttendanceDetail,
        meta: { title: '考勤详情', zone: 'desktop', access: 'review' }
      },
      {
        path: 'shift/center',
        name: 'shift-center',
        component: ShiftCenter,
        meta: { title: '班次观察台', zone: 'desktop', access: 'review' }
      },
      {
        path: 'shift/detail/:id',
        name: 'shift-detail',
        component: ShiftDetail,
        meta: { title: '班次详情', zone: 'desktop', access: 'review' }
      },
      {
        path: 'reports/list',
        name: 'report-list',
        component: ReportList,
        meta: { title: '日报看板', zone: 'desktop', access: 'review' }
      },
      {
        path: 'reports/detail/:id',
        name: 'report-detail',
        component: ReportDetail,
        meta: { title: '日报详情', zone: 'desktop', access: 'review' }
      },
      {
        path: 'reconciliation/center',
        name: 'reconciliation-center',
        component: ReconciliationCenter,
        meta: { title: '差异处置中心', zone: 'desktop', access: 'review' }
      },
      {
        path: 'reconciliation/detail/:id',
        name: 'reconciliation-detail',
        component: ReconciliationDetail,
        meta: { title: '差异详情', zone: 'desktop', access: 'review' }
      },
      {
        path: 'quality/center',
        name: 'quality-center',
        component: QualityCenter,
        meta: { title: '质量处置中心', zone: 'desktop', access: 'review' }
      },
      {
        path: 'quality/detail/:id',
        name: 'quality-detail',
        component: QualityDetail,
        meta: { title: '质量详情', zone: 'desktop', access: 'review' }
      },
      {
        path: 'master/workshop',
        name: 'master-workshop',
        redirect: { name: 'admin-master-workshop' },
        meta: { title: '车间管理', zone: 'desktop', access: 'desktop_config', legacy: true }
      },
      {
        path: 'master/team',
        name: 'master-team',
        redirect: { name: 'admin-master-workshop' },
        meta: { title: '班组管理', zone: 'desktop', access: 'desktop_config', legacy: true }
      },
      {
        path: 'master/employee',
        name: 'master-employee',
        redirect: { name: 'admin-master-workshop' },
        meta: { title: '员工管理', zone: 'desktop', access: 'desktop_config', legacy: true }
      },
      {
        path: 'master/equipment',
        name: 'master-equipment',
        redirect: { name: 'admin-master-workshop' },
        meta: { title: '机台管理', zone: 'desktop', access: 'desktop_config', legacy: true }
      },
      {
        path: 'master/users',
        name: 'master-users',
        redirect: { name: 'admin-users' },
        meta: { title: '用户管理', zone: 'desktop', access: 'admin', legacy: true }
      },
      {
        path: 'master/shift-config',
        name: 'master-shift-config',
        redirect: { name: 'admin-master-workshop' },
        meta: { title: '班次配置', zone: 'desktop', access: 'desktop_config', legacy: true }
      },
      {
        path: 'master/alias',
        name: 'master-alias',
        redirect: { name: 'admin-master-workshop' },
        meta: { title: '别名映射', zone: 'desktop', access: 'desktop_config', legacy: true }
      },
      {
        path: 'master/yield-rate-map',
        name: 'master-yield-rate-map',
        redirect: { name: 'admin-template-center' },
        meta: { title: '成品率口径收敛图', zone: 'desktop', access: 'desktop_config', legacy: true }
      },
      {
        path: 'master/workshop-template',
        name: 'master-workshop-template',
        redirect: { name: 'admin-template-center' },
        meta: { title: '车间模板', zone: 'desktop', access: 'admin', legacy: true }
      },
      {
        path: 'master/workshop-templates',
        redirect: '/master/workshop-template'
      },
      {
        path: 'dashboard/statistics-legacy',
        name: 'statistics-dashboard-legacy',
        component: Statistics,
        meta: { title: '统计看板(兼容)', zone: 'desktop', access: 'review', legacy: true }
      }
    ]
  }
]

const routes = rawRoutes.map(withMeta)

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  }
})

router.beforeEach((to) => {
  const authStore = useAuthStore()
  const hasRuntimeAuthCode = (
    to.name === 'mobile-entry' &&
    Boolean(resolveRuntimeAuthCode(to.query))
  )
  if (authStore.token && to.name === 'login') {
    return defaultLanding(authStore)
  }
  if (to.meta.requiresAuth && !authStore.token) {
    if (hasRuntimeAuthCode) {
      document.title = to.meta.title ? `${to.meta.title} - ${appTitle}` : appTitle
      return true
    }
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (!authStore.token) {
    document.title = to.meta.title ? `${to.meta.title} - ${appTitle}` : appTitle
    return true
  }

  if (authStore.isFillOnlyRole && to.meta.zone !== 'entry' && to.name !== 'login') {
    return { name: 'mobile-entry' }
  }

  if (prefersMobileSurface(authStore, to)) {
    return { name: 'mobile-entry' }
  }

  if (to.meta.zone === 'entry' && !authStore.canAccessFillSurface) {
    return authStore.canAccessReviewSurface ? reviewLanding(authStore) : { name: 'login' }
  }
  if (to.meta.zone === 'review' && !authStore.canAccessReviewSurface) {
    return authStore.canAccessFillSurface ? { name: 'mobile-entry' } : { name: 'login' }
  }
  if (to.meta.zone === 'admin' && !authStore.adminSurface) {
    return defaultLanding(authStore)
  }
  if (to.meta.zone === 'desktop' && !authStore.adminSurface) {
    return defaultLanding(authStore)
  }

  if (to.meta.access === 'public') {
    document.title = to.meta.title ? `${to.meta.title} - ${appTitle}` : appTitle
    return true
  }
  if (to.meta.access === 'entry' && !authStore.canAccessFillSurface) {
    return defaultLanding(authStore)
  }
  if (to.meta.access === 'review' && !authStore.canAccessReviewSurface) {
    return defaultLanding(authStore)
  }
  if (to.meta.access === 'admin' && !authStore.adminSurface) {
    return defaultLanding(authStore)
  }

  if (to.meta.access === 'review' && !authStore.canAccessReviewDesk) {
    return defaultLanding(authStore)
  }
  if (to.meta.access === 'review_surface' && !authStore.canAccessReviewSurface) {
    return defaultLanding(authStore)
  }
  if (to.meta.access === 'desktop_config' && !authStore.adminSurface) {
    return defaultLanding(authStore)
  }
  if (to.meta.access === 'manager' && !(authStore.isAdmin || authStore.isManager)) {
    return defaultLanding(authStore)
  }
  if (to.meta.access === 'admin_strict' && !authStore.isAdmin) {
    return defaultLanding(authStore)
  }
  if (to.meta.access === 'factory_dashboard' && !authStore.canAccessFactoryDashboard) {
    return defaultLanding(authStore)
  }
  if (to.meta.access === 'workshop_dashboard' && !authStore.canAccessWorkshopDashboard) {
    return defaultLanding(authStore)
  }
  if (to.meta.access === 'statistics_dashboard' && !authStore.canAccessStatisticsDashboard) {
    return defaultLanding(authStore)
  }

  document.title = to.meta.title ? `${to.meta.title} - ${appTitle}` : appTitle
  return true
})

export default router
