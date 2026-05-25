export const SETTINGS_GROUPS = [
  {
    label: '配置',
    items: [
      { title: '接入', path: '/manage/ingestion', access: 'admin' },
      { title: '主数据', path: '/manage/master', access: 'admin' },
      { title: '模板', path: '/manage/admin/templates', access: 'admin' },
      { title: '规则', path: '/manage/admin/rules', access: 'admin' }
    ]
  },
  {
    label: '权限',
    items: [
      { title: '用户', path: '/manage/admin/users', access: 'admin' },
      { title: '治理', path: '/manage/admin/governance', access: 'admin' }
    ]
  },
  {
    label: '运维',
    items: [
      { title: '运维', path: '/manage/ops-center', access: 'review' },
      { title: '系统', path: '/manage/settings-center', access: 'admin' },
      { title: 'AI', path: '/manage/ai-assistant', access: 'review' }
    ]
  },
  {
    label: '杂项 (冻结)',
    items: [
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
