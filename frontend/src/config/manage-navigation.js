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

const COMPACT_REVIEW_PATHS = new Set(['/manage/live', '/manage/today', '/manage/production', '/manage/fill-details', '/manage/energy'])

const NAV_GROUPS = [
  {
    label: '实时调度',
    commandGroup: '实时调度',
    items: [
      { title: '实时调度墙', shortLabel: '调度', path: '/manage/live', icon: TrendCharts, access: 'review', commandGroup: '实时调度' }
    ]
  },
  {
    label: '昨日报表',
    commandGroup: '昨日报表',
    items: [
      { title: '昨日报表', shortLabel: '日报', path: '/manage/today', icon: Sunny, access: 'review', commandGroup: '昨日报表' }
    ]
  },
  {
    label: '生产分析',
    commandGroup: '生产分析',
    items: [
      { title: '生产分析', shortLabel: '作业', path: '/manage/production', icon: Histogram, access: 'review', commandGroup: '生产分析' },
      { title: '各车间看板', shortLabel: '车间', path: '/manage/workshop-dashboard', icon: Monitor, access: 'workshop_dashboard', commandGroup: '生产分析' },
      { title: '填报明细', shortLabel: '明细', path: '/manage/fill-details', icon: DataLine, access: 'review', commandGroup: '生产分析' },
      { title: '能耗中心', shortLabel: '能耗', path: '/manage/energy', icon: DataLine, access: 'review', commandGroup: '生产分析' },
      { title: '异常处理', shortLabel: '异常', path: '/manage/alerts', icon: Bell, access: 'review', commandGroup: '生产分析' }
    ]
  },
  {
    label: '人员考勤',
    commandGroup: '人员考勤',
    items: [
      { title: '考勤预留', shortLabel: '考勤', path: '/manage/attendance', icon: Sunny, access: 'review', commandGroup: '人员考勤' }
    ]
  },
  {
    label: '系统',
    commandGroup: '系统',
    items: [
      { title: '基础资料', shortLabel: '资料', path: '/manage/master', icon: Histogram, access: 'admin', commandGroup: '系统' },
      { title: '账号权限', shortLabel: '账号', path: '/manage/admin/users', icon: Bell, access: 'admin', commandGroup: '系统' },
      { title: '业务规则', shortLabel: '规则', path: '/manage/admin/rules', icon: Histogram, access: 'admin', commandGroup: '系统' },
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

export function manageNavGroups(auth, options = {}) {
  if (auth?.isWorkshopDirector) return WORKSHOP_DIRECTOR_GROUPS
  return NAV_GROUPS
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => canAccess(auth, item.access) && (!options.compact || COMPACT_REVIEW_PATHS.has(item.path)))
    }))
    .filter((group) => group.items.length > 0)
}

