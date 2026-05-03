import {
  Coin,
  Connection,
  Grid,
  List,
  Monitor,
  Setting,
  Tickets,
  TrendCharts,
  Warning
} from '@element-plus/icons-vue'

const NAV_GROUPS = [
  {
    label: '工厂状态',
    commandGroup: '工厂状态',
    items: [
      { title: '工厂总览', shortLabel: '工厂总览', path: '/manage/overview', icon: Monitor, access: 'review', commandGroup: '工厂状态', secondaryGroup: '全局' },
      { title: '生产流转', shortLabel: '流转', path: '/manage/factory/flow', icon: Connection, access: 'review', commandGroup: '工厂状态', secondaryGroup: '卷流' },
      { title: '车间机列', shortLabel: '机列', path: '/manage/factory/machine-lines', icon: Grid, access: 'review', commandGroup: '工厂状态', secondaryGroup: '作业' },
      { title: '卷级追踪', shortLabel: '卷追踪', path: '/manage/factory/coils', icon: Tickets, access: 'review', commandGroup: '工厂状态', secondaryGroup: '追踪' },
      { title: '库存去向', shortLabel: '去向', path: '/manage/factory/destinations', icon: List, access: 'review', commandGroup: '工厂状态', secondaryGroup: '库存' },
      { title: '异常地图', shortLabel: '异常图', path: '/manage/factory/exceptions', icon: Warning, access: 'review', commandGroup: '工厂状态', secondaryGroup: '风险' }
    ]
  },
  {
    label: '经营效益',
    commandGroup: '经营效益',
    items: [
      { title: '经营效益', shortLabel: '经营效益', path: '/manage/factory/cost', icon: Coin, access: 'review', commandGroup: '经营效益', secondaryGroup: '估算' }
    ]
  },
  {
    label: '异常质量',
    commandGroup: '异常质量',
    items: [
      { title: '异常与补录', shortLabel: '补录', path: '/manage/entry-center', icon: List, access: 'review', commandGroup: '异常质量', secondaryGroup: '补录' },
      { title: '差异核对中心', shortLabel: '核对', path: '/manage/reconciliation', icon: Tickets, access: 'review', commandGroup: '异常质量', secondaryGroup: '核对' },
      { title: '质量与告警中心', shortLabel: '质量', path: '/manage/quality', icon: TrendCharts, access: 'review', commandGroup: '异常质量', secondaryGroup: '质量' },
      { title: '异常处置', shortLabel: '异常', path: '/manage/anomaly', icon: Warning, access: 'review', commandGroup: '异常质量', secondaryGroup: '处置' }
    ]
  },
  {
    label: 'AI 助手',
    commandGroup: 'AI 助手',
    items: [
      { title: 'AI 助手', shortLabel: 'AI 助手', path: '/manage/ai-assistant', icon: TrendCharts, access: 'review', commandGroup: 'AI 助手', secondaryGroup: '站内' }
    ]
  },
  {
    label: '主数据',
    commandGroup: '主数据',
    items: [
      { title: '主数据与模板中心', shortLabel: '主数据', path: '/manage/master', icon: Grid, access: 'admin', commandGroup: '主数据', secondaryGroup: '模板' },
      { title: '用户管理', shortLabel: '用户', path: '/manage/admin/users', icon: Grid, access: 'admin', commandGroup: '主数据', secondaryGroup: '权限' },
      { title: '模板中心', shortLabel: '模板', path: '/manage/admin/templates', icon: Setting, access: 'admin', commandGroup: '主数据', secondaryGroup: '模板' }
    ]
  },
  {
    label: '数据接入',
    commandGroup: '数据接入',
    items: [
      { title: '数据接入与字段映射中心', shortLabel: '数据接入', path: '/manage/ingestion', icon: Connection, access: 'admin', commandGroup: '数据接入', secondaryGroup: '接入' }
    ]
  }
]

function canAccess(auth, access) {
  if (access === 'review') return Boolean(auth?.canAccessReviewSurface || auth?.reviewSurface)
  if (access === 'admin') return Boolean(auth?.adminSurface || auth?.isAdmin)
  return true
}

export function manageNavGroups(auth) {
  return NAV_GROUPS
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => canAccess(auth, item.access))
    }))
    .filter((group) => group.items.length > 0)
}

