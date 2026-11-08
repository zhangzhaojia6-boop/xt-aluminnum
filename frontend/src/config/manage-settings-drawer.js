export const SETTINGS_GROUPS = [
  {
    label: '业务',
    items: [
      { title: '各车间看板', path: '/manage/workshop-dashboard', access: 'review' },
      { title: '填报明细', path: '/manage/fill-details', access: 'review' },
      { title: '能耗中心', path: '/manage/energy', access: 'review' },
      { title: '考勤', path: '/manage/attendance', access: 'review' },
      { title: '物资采购', path: '/manage/procurement', access: 'review' }
    ]
  },
  {
    label: '配置',
    items: [
      { title: '主数据', path: '/manage/master', access: 'admin' },
      { title: '别名映射', path: '/manage/alias', access: 'admin' },
      { title: '系统设置', path: '/manage/admin/settings', access: 'admin' },
      { title: '规则', path: '/manage/admin/rules', access: 'admin' }
    ]
  },
  {
    label: '权限',
    items: [
      { title: '用户', path: '/manage/admin/users', access: 'admin' },
      { title: '治理', path: '/manage/admin/governance', access: 'admin' },
      { title: '通讯治理', path: '/manage/admin/agents', access: 'admin' },
      { title: '通讯通道', path: '/manage/channels', access: 'admin' }
    ]
  },
  {
    label: '工具',
    items: [
      { title: '归档报表', path: '/manage/reports', access: 'review' },
      { title: 'AI', path: '/manage/ai-assistant', access: 'review' },
      { title: '知识库资料', path: '/manage/rag', access: 'admin' },
      { title: '输出skill对齐', path: '/manage/mapping-reconciliation', access: 'admin' }
    ]
  },
  {
    label: '杂项 (冻结)',
    items: [
      { title: 'QR 打印', path: '/manage/admin/qr-print', access: 'admin' },
      { title: '库存去向', path: '/manage/factory/destinations', access: 'review', frozen: true },
      { title: '库存', path: '/manage/inventory', access: 'review', frozen: true },
      { title: '合同', path: '/manage/contracts', access: 'review', frozen: true }
    ]
  }
]

function canAccess(auth, access) {
  if (access === 'review') return Boolean(auth?.canAccessReviewSurface || auth?.reviewSurface)
  if (access === 'admin') return Boolean(auth?.adminSurface || auth?.isAdmin)
  return true
}

export function settingsDrawerGroups(auth) {
  return SETTINGS_GROUPS
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => canAccess(auth, item.access))
    }))
    .filter((group) => group.items.length > 0)
}
