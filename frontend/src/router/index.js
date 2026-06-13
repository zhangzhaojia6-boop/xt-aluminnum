import { createRouter, createWebHistory } from 'vue-router'

import { resolveRouteMeta } from '../config/navigation'
import { useAuthStore } from '../stores/auth'
import {
  isCompactClient,
  isDingTalkRuntimeClient,
  resolveGuardDecision,
  resolveRouteAccess,
  resolveRuntimeAuthCode,
} from './guardRules.js'

const Login = () => import('../views/Login.vue')
const EntryShell = () => import('../layout/EntryShell.vue')
const ManageShell = () => import('../layout/ManageShell.vue')
const MobileEntry = () => import('../views/mobile/MobileEntry.vue')
const AttendanceConfirm = () => import('../views/mobile/AttendanceConfirm.vue')
const ShiftReportForm = () => import('../views/mobile/ShiftReportForm.vue')
const CoilEntryWorkbench = () => import('../views/mobile/CoilEntryWorkbench.vue')
const UnifiedEntryForm = () => import('../views/mobile/UnifiedEntryForm.vue')
const ConsumableEntry = () => import('../views/mobile/ConsumableEntry.vue')
const OCRCapture = () => import('../views/mobile/OCRCapture.vue')
const ShiftReportHistory = () => import('../views/mobile/ShiftReportHistory.vue')
const EntryDrafts = () => import('../views/entry/EntryDrafts.vue')
const ShiftDetail = () => import('../views/shift/ShiftDetail.vue')
const ReconciliationDetail = () => import('../views/reconciliation/ReconciliationDetail.vue')
const QualityDetail = () => import('../views/quality/QualityDetail.vue')
const ReportList = () => import('../views/reports/ReportList.vue')
const GovernanceCenter = () => import('../views/review/GovernanceCenter.vue')
const AiWorkstation = () => import('../views/ai/AiWorkstation.vue')
const Workshop = () => import('../views/master/Workshop.vue')
const AliasMapping = () => import('../views/master/AliasMapping.vue')
const MesTerminalBinding = () => import('../views/master/MesTerminalBinding.vue')
const UserManagement = () => import('../views/master/UserManagement.vue')
const RuleConfigCenter = () => import('../views/master/RuleConfigCenter.vue')
const LiveDashboardPage = () => import('../views/manage/live/LiveDashboardPage.vue')
const EnergyCenter = () => import('../views/energy/EnergyCenter.vue')
const AttendanceOverview = () => import('../views/attendance/AttendanceOverview.vue')
const AttendanceDetail = () => import('../views/attendance/AttendanceDetail.vue')
const ExceptionList = () => import('../views/attendance/ExceptionList.vue')
const QRCodePrint = () => import('../views/master/QRCodePrint.vue')
const InventoryCenter = () => import('../views/inventory/InventoryCenter.vue')
const ContractsCenter = () => import('../views/contracts/ContractsCenter.vue')
const DestinationScreen = () => import('../views/factory-command/DestinationScreen.vue')
const TodayPage = () => import('../views/manage/today/TodayPage.vue')
const ProductionPage = () => import('../views/manage/production/ProductionPage.vue')
const CoilTracePage = () => import('../views/manage/coils/CoilTracePage.vue')
const AlertsPage = () => import('../views/manage/alerts/AlertsPage.vue')
const FillDetailsPage = () => import('../views/manage/fill-details/FillDetailsPage.vue')
const WorkshopDashboardPage = () => import('../views/manage/workshop-dashboard/WorkshopDashboardPage.vue')
const SystemSettingsPage = () => import('../views/manage/admin/SystemSettingsPage.vue')
const AgentManagementPage = () => import('../views/manage/admin/AgentManagementPage.vue')

const appTitle = import.meta.env.VITE_APP_TITLE || '鑫泰铝业'

function withMeta(route) {
  return {
    ...route,
    meta: resolveRouteMeta(route.name, route.meta),
    children: route.children?.map(withMeta)
  }
}

function preserveRouteState(path, query = {}) {
  return (to) => ({
    path,
    query: { ...to.query, ...(typeof query === 'function' ? query(to) : query) },
    hash: to.hash
  })
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
      { path: 'consumables', name: 'mobile-consumable-entry', component: ConsumableEntry, meta: { ...entryMeta, title: '辅材填报', centerNo: '04', canonical: '/entry/consumables' } },
      { path: 'report', redirect: { name: 'mobile-entry' } },
      { path: 'report/:businessDate/:shiftId', name: 'mobile-report-form', component: ShiftReportForm, meta: { ...entryMeta, title: '快速填报', centerNo: '04', canonical: '/entry/report/:businessDate/:shiftId' } },
      { path: 'advanced/:businessDate/:shiftId', name: 'mobile-report-form-advanced', redirect: { name: 'mobile-unified-entry' } },
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
    path: '/team-lead',
    redirect: (to) => ({ path: '/entry', query: to.query, hash: to.hash })
  },
  {
    path: '/team-lead/worker/:employeeId/:businessDate',
    redirect: (to) => ({ path: '/entry', query: to.query, hash: to.hash })
  },
  {
    path: '/manage',
    component: ManageShell,
    meta: { ...reviewMeta, title: '管理工作台', canonical: '/manage' },
    children: [
      { path: '', redirect: '/manage/today' },
      { path: 'live', name: 'manage-live', component: LiveDashboardPage, meta: { ...reviewMeta, title: '生产实时', canonical: '/manage/live' } },
      { path: 'workshop', redirect: preserveRouteState('/manage/workshop-dashboard') },
      { path: 'workshop-dashboard', name: 'manage-workshop-dashboard', component: WorkshopDashboardPage, meta: { ...reviewMeta, access: 'workshop_dashboard', title: '各车间看板', canonical: '/manage/workshop-dashboard' } },
      { path: 'today', name: 'manage-today', component: TodayPage, meta: { ...reviewMeta, title: '昨日日报', canonical: '/manage/today' } },
      { path: 'production', name: 'manage-production', component: ProductionPage, meta: { ...reviewMeta, title: '生产', canonical: '/manage/production' } },
      { path: 'coils', name: 'manage-coils', component: CoilTracePage, meta: { ...reviewMeta, title: '卷级线索', canonical: '/manage/coils' } },
      { path: 'daily-report', name: 'manage-daily-report', redirect: preserveRouteState('/manage/today', { section: 'daily-report' }), meta: { ...reviewMeta, title: '日报总览', canonical: '/manage/today' } },
      { path: 'fill-details', name: 'manage-fill-details', component: FillDetailsPage, meta: { ...reviewMeta, title: '填报明细', canonical: '/manage/fill-details' } },
      { path: 'energy', name: 'energy-center', component: EnergyCenter, meta: { ...reviewMeta, title: '能源中心', canonical: '/manage/energy' } },
      { path: 'attendance', name: 'attendance-overview', component: AttendanceOverview, meta: { ...reviewMeta, title: '考勤总览', canonical: '/manage/attendance' } },
      { path: 'alerts', name: 'manage-alerts', component: AlertsPage, meta: { ...reviewMeta, title: '异常', canonical: '/manage/alerts' } },
      { path: 'anomalies', redirect: preserveRouteState('/manage/alerts', { surface: 'anomaly' }), meta: { ...reviewMeta, title: '异常处理', canonical: '/manage/alerts' } },
      { path: 'factory/destinations', name: 'factory-command-destinations', component: DestinationScreen, meta: { ...reviewMeta, title: '库存去向', centerNo: '05', canonical: '/manage/factory/destinations' } },
      { path: 'factory/exceptions', name: 'factory-command-exceptions', redirect: preserveRouteState('/manage/alerts', { surface: 'anomaly' }), meta: { ...reviewMeta, title: '异常地图', centerNo: '09', canonical: '/manage/alerts' } },
      { path: 'reconciliation', name: 'review-reconciliation-center', redirect: preserveRouteState('/manage/alerts', { surface: 'reconciliation' }), meta: { ...reviewMeta, title: '差异核对中心', centerNo: '09', canonical: '/manage/alerts' } },
      { path: 'reconciliation/detail/:id', name: 'reconciliation-detail', component: ReconciliationDetail, meta: { ...reviewMeta, title: '差异详情' } },
      { path: 'quality', name: 'review-quality-center', redirect: preserveRouteState('/manage/alerts', { surface: 'quality' }), meta: { ...reviewMeta, title: '质量与告警中心', centerNo: '09', canonical: '/manage/alerts' } },
      { path: 'quality/detail/:id', name: 'quality-detail', component: QualityDetail, meta: { ...reviewMeta, title: '质量详情', canonical: '/manage/quality/detail/:id' } },
      { path: 'reports', name: 'review-report-center', component: ReportList, meta: { ...reviewMeta, title: '日报与交付中心', centerNo: '08', canonical: '/manage/reports' } },
      { path: 'reports/detail/:id', name: 'report-detail', redirect: { name: 'manage-today' }, meta: { ...reviewMeta, title: '日报详情', canonical: '/manage/today' } },
      { path: 'ingestion', name: 'admin-ingestion-center', redirect: { name: 'admin-ops-reliability' }, meta: { ...adminMeta, title: '数据导入已停用', centerNo: '06', canonical: '/manage/admin/settings' } },
      { path: 'master', name: 'admin-master-workshop', component: Workshop, meta: { ...adminMeta, title: '主数据中心', centerNo: '14', canonical: '/manage/master' } },
      { path: 'alias', name: 'manage-alias', component: AliasMapping, meta: { ...adminMeta, title: '别名映射', canonical: '/manage/alias' } },
      { path: 'mes-terminal-bindings', name: 'manage-mes-terminal-bindings', component: MesTerminalBinding, meta: { ...adminMeta, title: 'MES 终端绑定', canonical: '/manage/mes-terminal-bindings' } },
      { path: 'imports', name: 'manage-imports', redirect: { name: 'admin-ops-reliability' }, meta: { ...adminMeta, title: '导入历史已停用', canonical: '/manage/admin/settings' } },
      { path: 'ai', name: 'review-brain-center', redirect: '/manage/ai-assistant', meta: { ...reviewMeta, title: 'AI 助手', centerNo: '11', canonical: '/manage/ai-assistant' } },
      { path: 'ai-assistant', name: 'factory-ai-assistant', component: AiWorkstation, meta: { ...reviewMeta, title: 'AI 助手', centerNo: '11', canonical: '/manage/ai-assistant' } },
      { path: 'inventory', name: 'manage-inventory', component: InventoryCenter, meta: { ...reviewMeta, title: '库存出入中心', canonical: '/manage/inventory' } },
      { path: 'contracts', name: 'manage-contracts', component: ContractsCenter, meta: { ...reviewMeta, title: '合同与订单中心', canonical: '/manage/contracts' } },
      { path: 'ops-center', name: 'manage-ops-center', redirect: preserveRouteState('/manage/admin/settings'), meta: { ...reviewMeta, title: '系统设置', canonical: '/manage/admin/settings' } },
      { path: 'settings-center', name: 'manage-settings-center', redirect: preserveRouteState('/manage/admin/settings'), meta: { ...adminMeta, title: '系统设置', canonical: '/manage/admin/settings' } },
      { path: 'admin', name: 'admin-overview', redirect: '/manage/admin/settings', meta: { ...adminMeta, title: '系统设置', centerNo: '12', canonical: '/manage/admin/settings' } },
      { path: 'admin/setting', redirect: { name: 'admin-ops-reliability' } },
      { path: 'admin/settings', name: 'admin-ops-reliability', component: SystemSettingsPage, meta: { ...adminMeta, title: '系统设置', centerNo: '12', canonical: '/manage/admin/settings' } },
      { path: 'admin/agents', name: 'admin-agent-management', component: AgentManagementPage, meta: { ...adminMeta, title: '通讯治理台', centerNo: '15', canonical: '/manage/admin/agents' } },
      { path: 'admin/users', name: 'admin-users', component: UserManagement, meta: { ...adminMeta, title: '用户管理', centerNo: '13', canonical: '/manage/admin/users' } },
      { path: 'admin/governance', name: 'admin-governance-center', component: GovernanceCenter, meta: { ...adminMeta, title: '权限与治理中心', centerNo: '13', canonical: '/manage/admin/governance' } },
      { path: 'admin/templates', redirect: { name: 'admin-ops-reliability' } },
      { path: 'admin/rules', name: 'admin-rule-config-center', component: RuleConfigCenter, meta: { ...adminMeta, title: '规则配置', centerNo: '14', canonical: '/manage/admin/rules' } },
      { path: 'admin/ops', redirect: { name: 'admin-ops-reliability' } },
      { path: 'admin/master', redirect: { name: 'admin-master-workshop' } },
      { path: 'admin/qr-print', name: 'admin-qr-print', component: QRCodePrint, meta: { ...adminMeta, title: 'QR 码打印', canonical: '/manage/admin/qr-print' } }
    ]
  },
  { path: '/review', redirect: preserveRouteState('/manage/today') },
  { path: '/review/overview', redirect: preserveRouteState('/manage/today') },
  { path: '/review/factory', redirect: preserveRouteState('/manage/production') },
  { path: '/review/workshop', redirect: preserveRouteState('/manage/workshop-dashboard') },
  { path: '/review/tasks', redirect: preserveRouteState('/manage/alerts') },
  { path: '/review/reports', redirect: preserveRouteState('/manage/reports') },
  { path: '/review/quality', redirect: preserveRouteState('/manage/alerts', { surface: 'quality' }) },
  { path: '/review/reconciliation', redirect: preserveRouteState('/manage/alerts', { surface: 'reconciliation' }) },
  { path: '/review/ingestion', name: 'review-ingestion-center', redirect: preserveRouteState('/manage/admin/settings') },
  { path: '/review/ops', name: 'review-ops-reliability', redirect: preserveRouteState('/manage/admin/settings') },
  { path: '/review/governance', name: 'review-governance-center', redirect: preserveRouteState('/manage/admin/governance') },
  { path: '/review/templates', name: 'review-template-center', redirect: preserveRouteState('/manage/admin/settings') },
  { path: '/review/cost-accounting', redirect: preserveRouteState('/manage/today') },
  { path: '/review/cost', redirect: preserveRouteState('/manage/today') },
  { path: '/review/roadmap', redirect: preserveRouteState('/manage/today') },
  { path: '/review/brain', redirect: preserveRouteState('/manage/ai-assistant') },
  { path: '/review/:pathMatch(.*)*', redirect: preserveRouteState('/manage/today') },
  { path: '/admin', redirect: preserveRouteState('/manage/admin/settings') },
  { path: '/admin/setting', redirect: preserveRouteState('/manage/admin/settings') },
  { path: '/setting', redirect: preserveRouteState('/manage/admin/settings') },
  { path: '/settings', redirect: preserveRouteState('/manage/admin/settings') },
  { path: '/admin/overview', redirect: preserveRouteState('/manage/admin/settings') },
  { path: '/admin/ingestion', redirect: preserveRouteState('/manage/admin/settings') },
  { path: '/admin/master', redirect: preserveRouteState('/manage/master') },
  { path: '/admin/master/workshop', redirect: preserveRouteState('/manage/master') },
  { path: '/admin/master/templates', redirect: preserveRouteState('/manage/admin/settings') },
  { path: '/admin/templates', redirect: preserveRouteState('/manage/admin/settings') },
  { path: '/admin/rules', redirect: preserveRouteState('/manage/admin/rules') },
  { path: '/admin/users', redirect: preserveRouteState('/manage/admin/users') },
  { path: '/admin/governance', redirect: preserveRouteState('/manage/admin/governance') },
  { path: '/admin/ops', redirect: preserveRouteState('/manage/admin/settings') },
  { path: '/admin/:pathMatch(.*)*', redirect: preserveRouteState('/manage/admin/settings') },
  { path: '/mobile', redirect: (to) => ({ path: '/entry', query: to.query, hash: to.hash }) },
  { path: '/mobile/report/:businessDate/:shiftId', redirect: (to) => ({ path: `/entry/report/${to.params.businessDate}/${to.params.shiftId}`, query: to.query, hash: to.hash }) },
  { path: '/mobile/report-advanced/:businessDate/:shiftId', redirect: (to) => ({ path: `/entry/advanced/${to.params.businessDate}/${to.params.shiftId}`, query: to.query, hash: to.hash }) },
  { path: '/mobile/ocr/:businessDate/:shiftId', redirect: (to) => ({ path: `/entry/ocr/${to.params.businessDate}/${to.params.shiftId}`, query: to.query, hash: to.hash }) },
  { path: '/mobile/attendance', redirect: (to) => ({ path: '/entry/attendance', query: to.query, hash: to.hash }) },
  { path: '/mobile/history', redirect: (to) => ({ path: '/entry/history', query: to.query, hash: to.hash }) },
  { path: '/worker', redirect: (to) => ({ name: 'mobile-entry', query: to.query, hash: to.hash }) },
  { path: '/factory', redirect: '/manage/production' },
  { path: '/workshop', redirect: '/manage/workshop-dashboard' },
  { path: '/ingestion/mapping', redirect: '/manage/admin/settings' },
  { path: '/reports/delivery', redirect: '/manage/reports' },
  { path: '/alerts/quality', redirect: preserveRouteState('/manage/alerts', { surface: 'quality' }) },
  { path: '/ops/reliability', redirect: '/manage/admin/settings' },
  { path: '/governance', redirect: '/manage/admin/governance' },
  { path: '/cost/accounting', redirect: '/manage/today' },
  { path: '/roadmap/next', redirect: '/manage/today' },
  { path: '/dashboard', redirect: '/manage/today' },
  { path: '/dashboard/executive', redirect: '/manage/today' },
  { path: '/dashboard/factory', redirect: '/manage/production' },
  { path: '/dashboard/workshop', redirect: '/manage/workshop-dashboard' },
  { path: '/dashboard/statistics', redirect: '/manage/today' },
  { path: '/imports/files', name: 'file-import', redirect: preserveRouteState('/manage/admin/settings'), meta: { ...adminMeta, title: '文件上传已停用' } },
  { path: '/imports/history', redirect: '/manage/admin/settings' },
  { path: '/energy/center', redirect: preserveRouteState('/manage/energy') },
  { path: '/attendance/overview', redirect: preserveRouteState('/manage/attendance') },
  { path: '/attendance/detail/:employeeId/:businessDate', name: 'attendance-detail', component: AttendanceDetail, meta: { ...reviewMeta, title: '考勤详情' } },
  { path: '/attendance/exceptions', name: 'attendance-exceptions', component: ExceptionList, meta: { ...reviewMeta, title: '异常列表' } },
  { path: '/shift/detail/:id', name: 'shift-detail', component: ShiftDetail, meta: { ...reviewMeta, title: '班次详情' } },
  { path: '/reports/list', redirect: '/manage/reports' },
  { path: '/reports/detail/:id', redirect: '/manage/today' },
  { path: '/quality/center', redirect: preserveRouteState('/manage/alerts', { surface: 'quality' }) },
  { path: '/quality/detail/:id', redirect: (to) => ({ path: `/manage/quality/detail/${to.params.id}`, query: to.query, hash: to.hash }) },
  { path: '/reconciliation/center', redirect: preserveRouteState('/manage/alerts', { surface: 'reconciliation' }) },
  { path: '/reconciliation/detail/:id', redirect: (to) => `/manage/reconciliation/detail/${to.params.id}` },
  { path: '/master', redirect: '/manage/master' },
  { path: '/master/workshop', name: 'master-workshop', redirect: '/manage/master' },
  { path: '/master/team', name: 'master-team', redirect: '/manage/master' },
  { path: '/master/employee', name: 'master-employee', redirect: '/manage/master' },
  { path: '/master/equipment', name: 'master-equipment', redirect: '/manage/master' },
  { path: '/master/users', name: 'master-users', redirect: '/manage/admin/users' },
  { path: '/master/shift-config', name: 'master-shift-config', redirect: '/manage/master' },
  { path: '/master/alias', name: 'master-alias', redirect: '/manage/alias' },
  { path: '/master/yield-rate-map', name: 'master-yield-rate-map', redirect: '/manage/admin/rules' },
  { path: '/master/workshop-template', name: 'master-workshop-template', redirect: '/manage/admin/settings' },
  { path: '/master/workshop-templates', redirect: '/manage/admin/settings' },
  { path: '/master/rules', redirect: '/manage/admin/rules' },
  { path: '/', redirect: '/manage/today' },
  { path: '/:pathMatch(.*)*', redirect: '/manage/today' }
]

const routes = rawRoutes.map(withMeta)

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to) {
    if (to.hash) {
      return { el: to.hash, top: 12 }
    }
    return { top: 0 }
  }
})

export function installRouterGuards(routerInstance, authStore) {
  routerInstance.beforeEach(async (to) => {
    const auth = authStore || useAuthStore()
    const access = resolveRouteAccess(to)
    const compactClient = isCompactClient()
    const hasRuntimeAuthCode = to.name === 'mobile-entry' && (
      Boolean(resolveRuntimeAuthCode(to.query)) || isDingTalkRuntimeClient()
    )

    const earlyDecision = resolveGuardDecision({
      to,
      auth,
      access,
      hasRuntimeAuthCode,
      compactClient,
      profileReady: Boolean(auth.user),
    })
    if (earlyDecision === true) {
      document.title = to.meta.title ? `${to.meta.title} - ${appTitle}` : appTitle
      return true
    }
    if (earlyDecision) return earlyDecision

    if (!auth.user) {
      try {
        await auth.fetchProfile()
      } catch {
        return { name: 'login', query: { redirect: to.fullPath } }
      }
    }

    const decision = resolveGuardDecision({ to, auth, access, hasRuntimeAuthCode, compactClient })
    if (decision !== true) return decision

    document.title = to.meta.title ? `${to.meta.title} - ${appTitle}` : appTitle
    return true
  })
}

export default router
