import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '../stores/auth'

const Layout = () => import('../views/Layout.vue')
const Login = () => import('../views/Login.vue')
const FactoryDirector = () => import('../views/dashboard/FactoryDirector.vue')
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
const Workshop = () => import('../views/master/Workshop.vue')
const Team = () => import('../views/master/Team.vue')
const Employee = () => import('../views/master/Employee.vue')
const Equipment = () => import('../views/master/Equipment.vue')
const UserManagement = () => import('../views/master/UserManagement.vue')
const ShiftConfig = () => import('../views/master/ShiftConfig.vue')
const AliasMapping = () => import('../views/master/AliasMapping.vue')
const WorkshopTemplateConfig = () => import('../views/master/WorkshopTemplateConfig.vue')
const YieldRateDeprecationMap = () => import('../views/master/YieldRateDeprecationMap.vue')
const MobileEntry = () => import('../views/mobile/MobileEntry.vue')
const AttendanceConfirm = () => import('../views/mobile/AttendanceConfirm.vue')
const ShiftReportForm = () => import('../views/mobile/ShiftReportForm.vue')
const DynamicEntryForm = () => import('../views/mobile/DynamicEntryForm.vue')
const OCRCapture = () => import('../views/mobile/OCRCapture.vue')
const ShiftReportHistory = () => import('../views/mobile/ShiftReportHistory.vue')
const AnomalyReview = () => import('../views/attendance/AnomalyReview.vue')

const appTitle = import.meta.env.VITE_APP_TITLE || '鑫泰铝业'

function desktopLanding(authStore) {
  if (authStore.canAccessFactoryDashboard) return { name: 'factory-dashboard' }
  if (authStore.canAccessWorkshopDashboard) return { name: 'workshop-dashboard' }
  if (authStore.isAdmin || authStore.isManager) return { name: 'master-workshop' }
  return { name: 'login' }
}

function defaultLanding(authStore) {
  if (authStore.canAccessMobile && !authStore.canAccessDesktop) return { name: 'mobile-entry' }
  const desktop = desktopLanding(authStore)
  if (desktop.name !== 'login') return desktop
  if (authStore.canAccessMobile) return { name: 'mobile-entry' }
  return { name: 'login' }
}

const routes = [
  { path: '/login', name: 'login', component: Login, meta: { title: '登录' } },
  {
    path: '/mobile',
    name: 'mobile-entry',
    component: MobileEntry,
    meta: { requiresAuth: true, title: '企业微信填报入口', zone: 'mobile' }
  },
  {
    path: '/mobile/report/:businessDate/:shiftId',
    name: 'mobile-report-form',
    component: ShiftReportForm,
    meta: { requiresAuth: true, title: '班次填报', zone: 'mobile' }
  },
  {
    path: '/mobile/report-advanced/:businessDate/:shiftId',
    name: 'mobile-report-form-advanced',
    component: DynamicEntryForm,
    meta: { requiresAuth: true, title: '高级班次填报', zone: 'mobile' }
  },
  {
    path: '/mobile/ocr/:businessDate/:shiftId',
    name: 'mobile-ocr-capture',
    component: OCRCapture,
    meta: { requiresAuth: true, title: '拍照识别', zone: 'mobile' }
  },
  {
    path: '/mobile/attendance',
    name: 'mobile-attendance-confirm',
    component: AttendanceConfirm,
    meta: { requiresAuth: true, title: '考勤确认', zone: 'mobile' }
  },
  {
    path: '/mobile/history',
    name: 'mobile-report-history',
    component: ShiftReportHistory,
    meta: { requiresAuth: true, title: '历史填报', zone: 'mobile' }
  },
  {
    path: '/worker',
    redirect: (to) => ({
      name: 'mobile-entry',
      query: to.query,
      hash: to.hash
    })
  },
  {
    path: '/',
    component: Layout,
    meta: { requiresAuth: true, zone: 'desktop' },
    redirect: '/dashboard/factory',
    children: [
      {
        path: 'dashboard/factory',
        name: 'factory-dashboard',
        component: FactoryDirector,
        meta: { title: '厂长驾驶舱', zone: 'desktop', access: 'factory_dashboard' }
      },
      {
        path: 'dashboard/workshop',
        name: 'workshop-dashboard',
        component: WorkshopDirector,
        meta: { title: '车间主任看板', zone: 'desktop', access: 'workshop_dashboard' }
      },
      {
        path: 'dashboard/statistics',
        name: 'statistics-dashboard',
        component: Statistics,
        meta: { title: '统计观察看板', zone: 'desktop', access: 'statistics_dashboard' }
      },
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
        component: Workshop,
        meta: { title: '车间管理', zone: 'desktop', access: 'manager' }
      },
      {
        path: 'master/team',
        name: 'master-team',
        component: Team,
        meta: { title: '班组管理', zone: 'desktop', access: 'manager' }
      },
      {
        path: 'master/employee',
        name: 'master-employee',
        component: Employee,
        meta: { title: '员工管理', zone: 'desktop', access: 'manager' }
      },
      {
        path: 'master/equipment',
        name: 'master-equipment',
        component: Equipment,
        meta: { title: '机台管理', zone: 'desktop', access: 'manager' }
      },
      {
        path: 'master/users',
        name: 'master-users',
        component: UserManagement,
        meta: { title: '\u7528\u6237\u7ba1\u7406', zone: 'desktop', access: 'admin' }
      },
      {
        path: 'master/shift-config',
        name: 'master-shift-config',
        component: ShiftConfig,
        meta: { title: '班次配置', zone: 'desktop', access: 'manager' }
      },
      {
        path: 'master/alias',
        name: 'master-alias',
        component: AliasMapping,
        meta: { title: '别名映射', zone: 'desktop', access: 'manager' }
      },
      {
        path: 'master/yield-rate-map',
        name: 'master-yield-rate-map',
        component: YieldRateDeprecationMap,
        meta: { title: '成品率口径收敛图', zone: 'desktop', access: 'manager' }
      },
      {
        path: 'master/workshop-template',
        name: 'master-workshop-template',
        component: WorkshopTemplateConfig,
        meta: { title: '\u8f66\u95f4\u6a21\u677f', zone: 'desktop', access: 'admin' }
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  }
})

router.beforeEach((to) => {
  const authStore = useAuthStore()
  const hasWecomCode = (
    to.name === 'mobile-entry' &&
    typeof to.query.code === 'string' &&
    to.query.code.trim()
  )
  if (authStore.token && to.name === 'login') {
    return defaultLanding(authStore)
  }
  if (to.meta.requiresAuth && !authStore.token) {
    if (hasWecomCode) {
      document.title = to.meta.title ? `${to.meta.title} - ${appTitle}` : appTitle
      return true
    }
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  if (!authStore.token) {
    document.title = to.meta.title ? `${to.meta.title} - ${appTitle}` : appTitle
    return true
  }

  if (to.meta.zone === 'mobile' && !authStore.canAccessMobile) {
    return authStore.canAccessDesktop ? desktopLanding(authStore) : { name: 'login' }
  }
  if (to.meta.zone === 'desktop' && !authStore.canAccessDesktop) {
    return authStore.canAccessMobile ? { name: 'mobile-entry' } : { name: 'login' }
  }

  if (to.meta.access === 'review' && !authStore.canAccessReviewDesk) {
    return defaultLanding(authStore)
  }
  if (to.meta.access === 'manager' && !(authStore.isAdmin || authStore.isManager)) {
    return defaultLanding(authStore)
  }
  if (to.meta.access === 'admin' && !authStore.isAdmin) {
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
