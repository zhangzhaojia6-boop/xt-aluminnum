import dayjs from 'dayjs'

const STATUS_LABELS = {
  draft: '草稿',
  locked: '已锁定',
  unreported: '未填报',
  pending: '待处理',
  pending_review: '待处理',
  reviewed: '兼容中间态',
  confirmed: '已确认',
  submitted: '已提交',
  approved: '已通过系统校验',
  auto_confirmed: '已通过系统校验',
  returned: '已退回',
  published: '已发布',
  partial_success: '部分成功',
  completed: '已完成',
  processing: '处理中',
  open: '待处理',
  resolved: '已解决',
  ignored: '已忽略',
  corrected: '已修正',
  rejected: '已驳回',
  voided: '已作废',
  warning: '预警',
  blocker: '阻断',
  success: '成功',
  normal: '正常',
  abnormal: '异常',
  absent: '缺勤',
  superseded: '已被替代',
  pending_check: '待质检',
  ready: '就绪',
  ok: '正常',
  sent: '已催报',
  acknowledged: '已知晓',
  closed: '已关闭'
}

const ENTITY_TYPE_LABELS = {
  workshop: '车间',
  team: '班组',
  shift: '班次',
  equipment: '设备',
  employee: '员工'
}

const ROLE_LABELS = {
  admin: '系统管理员',
  factory_director: '厂长',
  senior_manager: '高级管理',
  manager: '车间管理者',
  workshop_director: '车间观察者',
  statistician: '观察角色（兼容旧总统计）',
  reviewer: '观察/处置角色（兼容旧审核）',
  team_leader: '班长',
  shift_leader: '班长(移动端)',
  weigher: '过磅员',
  qc: '质检员',
  energy_stat: '能耗统计',
  maintenance_lead: '机修班长',
  hydraulic_lead: '液压班长',
  contracts: '合同管理',
  inventory_keeper: '成品库负责人',
  utility_manager: '水电气负责人',
  deputy_leader: '代班负责人',
  mobile_user: '移动端用户',
  stat: '观察角色（兼容旧统计）'
}

const SCOPE_LABELS = {
  self_team: '仅本班组',
  self_workshop: '仅本车间',
  assigned: '授权范围',
  all: '全局'
}

const REPORT_TYPE_LABELS = {
  production: '生产日报',
  attendance: '考勤日报',
  exception: '异常日报'
}

const REPORT_SCOPE_LABELS = {
  auto_confirmed: '仅统计自动确认可用数据',
  confirmed_only: '兼容口径（旧确认数据）',
  include_reviewed: '兼容口径（中间态+确认数据）'
}

const OUTPUT_MODE_LABELS = {
  both: '结构化数据 + 文本摘要',
  json: '结构化数据',
  text: '文本摘要'
}

const RECONCILIATION_TYPE_LABELS = {
  attendance_vs_production: '考勤与生产核对',
  production_vs_mes: '生产与 MES 核对',
  energy_vs_production: '能耗与生产核对'
}

const QUALITY_ISSUE_TYPE_LABELS = {
  master_mapping: '主数据映射异常',
  missing_data: '关键数据缺失',
  invalid_value: '数值异常',
  unreconciled: '差异未处理',
  publish_blocker: '发布阻断'
}

const EXCEPTION_TYPE_LABELS = {
  missing_checkin: '缺上班卡',
  missing_checkout: '缺下班卡',
  no_schedule: '无排班',
  no_clock_with_schedule: '有排班无打卡',
  late: '迟到',
  early_leave: '早退',
  shift_mismatch: '班次不匹配',
  duplicate_clock: '重复打卡',
  manual_report: '手机填报异常',
  duplicate_record: '重复记录',
  missing_data: '缺少关键数据',
  abnormal_value: '数值异常',
  inconsistent_headcount: '人数不一致',
  late_report: '迟报'
}

const IMPORT_TYPE_LABELS = {
  attendance_schedule: '排班数据',
  attendance_clock: '打卡数据',
  production_shift: '生产班次数据',
  mes_export: 'MES 导出数据',
  energy: '能耗数据'
}

const SOURCE_TYPE_LABELS = {
  ...IMPORT_TYPE_LABELS,
  reconciliation: '差异核对',
  quality: '质量检查',
  production: '生产系统',
  attendance: '考勤系统',
  mes: 'MES 系统',
  dashboard: '驾驶舱',
  mobile: '手机填报'
}

const DELIVERY_STEP_LABELS = {
  reconciliation_open: '仍有未处理差异',
  quality_blocker: '存在质量阻断问题',
  reports_not_generated: '日报尚未生成',
  reports_not_reviewed: '日报尚未形成可交付版本'
}

const REMINDER_TYPE_LABELS = {
  unreported: '未报提醒',
  late_report: '迟报提醒'
}

function formatByMap(value, mapping) {
  if (value === null || value === undefined || value === '') return '-'
  return mapping[value] || value
}

export function formatStatusLabel(value) {
  return formatByMap(value, STATUS_LABELS)
}

export function formatEntityTypeLabel(value) {
  return formatByMap(value, ENTITY_TYPE_LABELS)
}

export function formatRoleLabel(value) {
  return formatByMap(value, ROLE_LABELS)
}

export function formatScopeLabel(value) {
  return formatByMap(value, SCOPE_LABELS)
}

export function formatReportTypeLabel(value) {
  return formatByMap(value, REPORT_TYPE_LABELS)
}

export function formatReportScopeLabel(value) {
  return formatByMap(value, REPORT_SCOPE_LABELS)
}

export function formatOutputModeLabel(value) {
  return formatByMap(value, OUTPUT_MODE_LABELS)
}

export function formatReconciliationTypeLabel(value) {
  return formatByMap(value, RECONCILIATION_TYPE_LABELS)
}

export function formatQualityIssueTypeLabel(value) {
  return formatByMap(value, QUALITY_ISSUE_TYPE_LABELS)
}

export function formatExceptionTypeLabel(value) {
  return formatByMap(value, EXCEPTION_TYPE_LABELS)
}

export function formatImportTypeLabel(value) {
  return formatByMap(value, IMPORT_TYPE_LABELS)
}

export function formatSourceTypeLabel(value) {
  return formatByMap(value, SOURCE_TYPE_LABELS)
}

export function formatReminderTypeLabel(value) {
  return formatByMap(value, REMINDER_TYPE_LABELS)
}

export function formatBooleanLabel(value) {
  return value ? '是' : '否'
}

export function formatDeliveryMissingSteps(steps = []) {
  if (!steps || !steps.length) return ['无']

  return steps.map((item) => {
    if (item.startsWith('imports_missing:')) {
      const importTypes = item.replace('imports_missing:', '').split(',').filter(Boolean)
      const names = importTypes.map((code) => formatImportTypeLabel(code))
      return `缺少导入：${names.join('、')}`
    }
    return DELIVERY_STEP_LABELS[item] || item
  })
}

export function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || value === '') return '-'
  const num = Number(value)
  if (Number.isNaN(num)) return '-'
  return num.toFixed(digits)
}

export function formatDateTime(value) {
  if (!value) return '-'
  return dayjs(value).format('YYYY-MM-DD HH:mm')
}
