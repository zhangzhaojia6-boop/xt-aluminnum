import {
  Bell,
  DataLine,
  Histogram,
  Monitor,
  Setting,
  Sunny,
  TrendCharts
} from '@element-plus/icons-vue'

const WORKSHOP_DIRECTOR_GROUPS = [
  {
    label: '本车间',
    commandGroup: '本车间',
    items: [
      { title: '各车间看板', shortLabel: '车间看板', path: '/manage/workshop-dashboard', icon: Monitor, access: 'workshop_dashboard', commandGroup: '本车间' }
    ]
  }
]

const NAV_GROUPS = [
  {
    label: '生产实时',
    commandGroup: '生产实时',
    items: [
      { title: '生产实时', shortLabel: '实时', path: '/manage/live', icon: TrendCharts, access: 'review', commandGroup: '生产实时' }
    ]
  },
  {
    label: '昨日日报',
    commandGroup: '昨日日报',
    items: [
      { title: '昨日日报', shortLabel: '昨日日报', path: '/manage/today', icon: Sunny, access: 'review', commandGroup: '昨日日报' }
    ]
  },
  {
    label: '生产',
    commandGroup: '生产',
    items: [
      { title: '生产', shortLabel: '生产', path: '/manage/production', icon: Histogram, access: 'review', commandGroup: '生产' },
      { title: '各车间看板', shortLabel: '车间看板', path: '/manage/workshop-dashboard', icon: Monitor, access: 'workshop_dashboard', commandGroup: '生产' },
      { title: '填报明细', shortLabel: '明细', path: '/manage/fill-details', icon: DataLine, access: 'review', commandGroup: '生产' },
      { title: '能耗', shortLabel: '能耗', path: '/manage/energy', icon: DataLine, access: 'review', commandGroup: '生产' },
      { title: '异常处理', shortLabel: '异常', path: '/manage/alerts', icon: Bell, access: 'review', commandGroup: '生产' }
    ]
  },
  {
    label: '考勤',
    commandGroup: '考勤',
    items: [
      { title: '考勤', shortLabel: '考勤', path: '/manage/attendance', icon: Sunny, access: 'review', commandGroup: '考勤' }
    ]
  },
  {
    label: '系统',
    commandGroup: '系统',
    items: [
      { title: '主数据', shortLabel: '主数', path: '/manage/master', icon: Histogram, access: 'admin', commandGroup: '系统' },
      { title: '用户管理', shortLabel: '用户', path: '/manage/admin/users', icon: Bell, access: 'admin', commandGroup: '系统' },
      { title: '规则配置', shortLabel: '规则', path: '/manage/admin/rules', icon: Histogram, access: 'admin', commandGroup: '系统' },
      { title: '系统设置', shortLabel: '设置', path: '/manage/admin/settings', icon: Setting, access: 'admin', commandGroup: '系统' }
    ]
  }
]

function canAccess(auth, access) {
  if (access === 'workshop_dashboard') return Boolean(auth?.canAccessWorkshopDashboard || auth?.canAccessReviewSurface)
  if (access === 'review') return Boolean(auth?.canAccessReviewSurface || auth?.reviewSurface)
  if (access === 'admin') return Boolean(auth?.adminSurface || auth?.isAdmin)
  return true
}

export function manageNavGroups(auth) {
  if (auth?.isWorkshopDirector) return WORKSHOP_DIRECTOR_GROUPS
  return NAV_GROUPS
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => canAccess(auth, item.access))
    }))
    .filter((group) => group.items.length > 0)
}

