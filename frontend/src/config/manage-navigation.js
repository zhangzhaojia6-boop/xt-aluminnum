import {
  Bell,
  ChatLineSquare,
  Collection,
  Connection,
  Cpu,
  DataBoard,
  DataLine,
  Document,
  Histogram,
  Message,
  Monitor,
  Odometer,
  OfficeBuilding,
  Operation,
  Postcard,
  ShoppingCart,
  Sunny,
  Tickets,
  User
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

// 原来藏在右上角齿轮里的功能，按组放进左栏；主线常开，其余可折叠
const FEATURE_GROUPS = [
  {
    label: '业务',
    commandGroup: '业务',
    collapsible: true,
    items: [
      { title: '各车间看板', shortLabel: '车间看板', path: '/manage/workshop-dashboard', icon: Monitor, access: 'review', commandGroup: '业务' },
      { title: '填报明细', shortLabel: '填报明细', path: '/manage/fill-details', icon: DataLine, access: 'review', commandGroup: '业务' },
      { title: '能耗中心', shortLabel: '能耗', path: '/manage/energy', icon: Sunny, access: 'review', commandGroup: '业务' },
      { title: '物资采购', shortLabel: '物资采购', path: '/manage/procurement', icon: ShoppingCart, access: 'review', commandGroup: '业务' }
    ]
  },
  {
    label: '配置',
    commandGroup: '配置',
    collapsible: true,
    items: [
      { title: '主数据', shortLabel: '主数据', path: '/manage/master', icon: OfficeBuilding, access: 'admin', commandGroup: '配置' },
      { title: '别名映射', shortLabel: '别名映射', path: '/manage/alias', icon: Connection, access: 'admin', commandGroup: '配置' },
      { title: '规则', shortLabel: '规则', path: '/manage/admin/rules', icon: Operation, access: 'admin', commandGroup: '配置' },
      { title: 'PC 工艺映射', shortLabel: 'PC 工艺映射', path: '/manage/mes-terminal-bindings', icon: Cpu, access: 'admin', commandGroup: '配置' }
    ]
  },
  {
    label: '权限',
    commandGroup: '权限',
    collapsible: true,
    items: [
      { title: '用户与角色', shortLabel: '用户与角色', path: '/manage/admin/users', icon: User, access: 'admin', commandGroup: '权限' },
      { title: '通讯治理', shortLabel: '通讯治理', path: '/manage/admin/agents', icon: ChatLineSquare, access: 'admin', commandGroup: '权限' },
      { title: '通讯通道', shortLabel: '通讯通道', path: '/manage/channels', icon: Message, access: 'admin', commandGroup: '权限' }
    ]
  },
  {
    label: '工具',
    commandGroup: '工具',
    collapsible: true,
    items: [
      { title: '归档报表', shortLabel: '归档报表', path: '/manage/reports', icon: Document, access: 'review', commandGroup: '工具' },
      { title: '知识库资料', shortLabel: '知识库', path: '/manage/rag', icon: Collection, access: 'admin', commandGroup: '工具' },
      { title: 'QR 打印', shortLabel: 'QR 打印', path: '/manage/admin/qr-print', icon: Postcard, access: 'admin', commandGroup: '工具' }
    ]
  }
]

// 不放左栏、只能搜到的入口
const SEARCH_ONLY_GROUP = {
  label: '其他',
  items: [
    { title: 'AI 工作台', path: '/manage/ai-assistant', access: 'review' },
    { title: '输出skill对齐', path: '/manage/mapping-reconciliation', access: 'admin' }
  ]
}

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
  return (options.compact ? [...NAV_GROUPS, COMPACT_MORE_GROUP] : [...NAV_GROUPS, ...FEATURE_GROUPS])
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => canAccess(auth, item.access) && (!options.compact || COMPACT_REVIEW_PATHS.has(item.path)))
    }))
    .filter((group) => group.items.length > 0)
}

export function manageSearchGroups(auth) {
  if (auth?.isWorkshopDirector) return WORKSHOP_DIRECTOR_GROUPS
  return [...NAV_GROUPS, ...FEATURE_GROUPS, SEARCH_ONLY_GROUP]
    .map((group) => ({ ...group, items: group.items.filter((item) => canAccess(auth, item.access)) }))
    .filter((group) => group.items.length > 0)
}
