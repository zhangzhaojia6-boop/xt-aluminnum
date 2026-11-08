import {
  Bell,
  DataBoard,
  Histogram,
  Monitor,
  Odometer,
  Tickets,
  DataLine,
  Sunny
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

const COMPACT_REVIEW_PATHS = new Set(['/manage/live', '/manage/today', '/manage/production', '/manage/coils', '/manage/fill-details', '/manage/energy'])

const NAV_GROUPS = [
  {
    label: '',
    commandGroup: '主线',
    items: [
      { title: '经营总览', shortLabel: '总览', path: '/manage/today', icon: DataBoard, access: 'review', commandGroup: '主线' },
      { title: '实时调度', shortLabel: '实时', path: '/manage/live', icon: Odometer, access: 'review', commandGroup: '主线' },
      { title: '生产分析', shortLabel: '生产', path: '/manage/production', icon: Histogram, access: 'review', commandGroup: '主线' },
      { title: '卷级线索', shortLabel: '卷材', path: '/manage/coils', icon: Tickets, access: 'review', commandGroup: '主线' },
      { title: '异常处理', shortLabel: '异常', path: '/manage/alerts', icon: Bell, access: 'review', commandGroup: '主线' }
    ]
  }
]

const COMPACT_MORE_GROUP = {
  label: '更多',
  commandGroup: '更多',
  items: [
    { title: '填报明细', shortLabel: '明细', path: '/manage/fill-details', icon: DataLine, access: 'review', commandGroup: '更多' },
    { title: '能耗中心', shortLabel: '能耗', path: '/manage/energy', icon: Sunny, access: 'review', commandGroup: '更多' },
    { title: '各车间看板', shortLabel: '车间', path: '/manage/workshop-dashboard', icon: Monitor, access: 'workshop_dashboard', commandGroup: '更多' }
  ]
}

function canAccess(auth, access) {
  if (access === 'workshop_dashboard') return Boolean(auth?.canAccessWorkshopDashboard || auth?.canAccessReviewSurface)
  if (access === 'review') return Boolean(auth?.canAccessReviewSurface || auth?.reviewSurface)
  if (access === 'admin') return Boolean(auth?.adminSurface || auth?.isAdmin)
  return true
}

export function manageNavGroups(auth, options = {}) {
  if (auth?.isWorkshopDirector) return WORKSHOP_DIRECTOR_GROUPS
  return (options.compact ? [...NAV_GROUPS, COMPACT_MORE_GROUP] : NAV_GROUPS)
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => canAccess(auth, item.access) && (!options.compact || COMPACT_REVIEW_PATHS.has(item.path)))
    }))
    .filter((group) => group.items.length > 0)
}
