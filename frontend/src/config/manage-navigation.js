import {
  Bell,
  DataLine,
  Histogram,
  Setting,
  Sunny,
  TrendCharts
} from '@element-plus/icons-vue'

const NAV_GROUPS = [
  {
    label: '今日',
    commandGroup: '今日',
    items: [
      { title: '今日', shortLabel: '今日', path: '/manage/today', icon: Sunny, access: 'review', commandGroup: '今日' },
      { title: '日报总览', shortLabel: '日报', path: '/manage/daily-report', icon: DataLine, access: 'review', commandGroup: '今日' }
    ]
  },
  {
    label: '生产',
    commandGroup: '生产',
    items: [
      { title: '生产', shortLabel: '生产', path: '/manage/production', icon: Histogram, access: 'review', commandGroup: '生产' },
      { title: '能耗', shortLabel: '能耗', path: '/energy/center', icon: DataLine, access: 'review', commandGroup: '生产' }
    ]
  },
  {
    label: '考勤',
    commandGroup: '考勤',
    items: [
      { title: '考勤', shortLabel: '考勤', path: '/attendance/overview', icon: Sunny, access: 'review', commandGroup: '考勤' }
    ]
  },
  {
    label: '交付',
    commandGroup: '交付',
    items: [
      { title: '报表', shortLabel: '报表', path: '/manage/reports', icon: TrendCharts, access: 'review', commandGroup: '交付' }
    ]
  },
  {
    label: '系统',
    commandGroup: '系统',
    items: [
      { title: '主数据', shortLabel: '主数', path: '/manage/master', icon: Histogram, access: 'admin', commandGroup: '系统' },
      { title: '用户管理', shortLabel: '用户', path: '/manage/admin/users', icon: Bell, access: 'admin', commandGroup: '系统' },
      { title: '模板中心', shortLabel: '模板', path: '/manage/admin/templates', icon: DataLine, access: 'admin', commandGroup: '系统' },
      { title: '规则配置', shortLabel: '规则', path: '/manage/admin/rules', icon: Histogram, access: 'admin', commandGroup: '系统' },
      { title: '系统设置', shortLabel: '设置', path: '/manage/admin/settings', icon: Setting, access: 'admin', commandGroup: '系统' }
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

