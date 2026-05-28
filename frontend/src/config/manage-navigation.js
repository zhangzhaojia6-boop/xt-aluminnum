import {
  Bell,
  DataLine,
  Histogram,
  Sunny
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
      { title: '生产', shortLabel: '生产', path: '/manage/production', icon: Histogram, access: 'review', commandGroup: '生产' }
    ]
  },
  {
    label: '异常',
    commandGroup: '异常',
    items: [
      { title: '异常', shortLabel: '异常', path: '/manage/alerts', icon: Bell, access: 'review', commandGroup: '异常' }
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

