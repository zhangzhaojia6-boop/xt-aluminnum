import {
  ChatDotRound,
  Coin,
  Connection,
  DataAnalysis,
  Document,
  Grid,
  List,
  Monitor,
  Printer,
  Setting,
  Tickets,
  TrendCharts,
  Upload,
  Warning
} from '@element-plus/icons-vue'

const NAV_GROUPS = [
  {
    label: '总览',
    items: [{ title: '总览', path: '/manage/overview', icon: Monitor, access: 'review' }]
  },
  {
    label: '生产管理',
    items: [
      { title: '录入中心', path: '/manage/entry-center', icon: List, access: 'review' },
      { title: '班次中心', path: '/manage/shift', icon: Document, access: 'review' },
      { title: '对账中心', path: '/manage/reconciliation', icon: Tickets, access: 'review' }
    ]
  },
  {
    label: '质量管控',
    items: [
      { title: '异常审核', path: '/manage/anomaly', icon: Warning, access: 'review' },
      { title: '质量预警', path: '/manage/quality', icon: TrendCharts, access: 'review' }
    ]
  },
  {
    label: '数据分析',
    items: [
      { title: '统计中心', path: '/manage/statistics', icon: DataAnalysis, access: 'review' },
      { title: '成本效益', path: '/manage/cost', icon: Coin, access: 'review' },
      { title: '报表交付', path: '/manage/reports', icon: Printer, access: 'review' }
    ]
  },
  {
    label: '基础数据',
    items: [
      { title: '主数据', path: '/manage/master', icon: Grid, access: 'admin' },
      { title: '别名映射', path: '/manage/alias', icon: Connection, access: 'admin' },
      { title: '导入历史', path: '/manage/imports', icon: Upload, access: 'admin' }
    ]
  },
  {
    label: 'AI',
    items: [{ title: 'AI 工作台', path: '/manage/ai', icon: ChatDotRound, access: 'review' }]
  },
  {
    label: '系统管理',
    items: [{ title: '系统设置', path: '/manage/admin/settings', icon: Setting, access: 'admin' }]
  }
]

function canAccess(auth, access) {
  if (access === 'review') return Boolean(auth?.canAccessReviewSurface || auth?.reviewSurface)
  if (access === 'admin') return Boolean(auth?.canAccessDesktopConfig || auth?.adminSurface || auth?.isAdmin)
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

