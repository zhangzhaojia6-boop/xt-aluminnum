import { createPinia } from 'pinia'

import { manageSearchGroups } from '../config/manage-navigation.js'
import { normalizeUser, useAuthStore } from '../stores/auth.js'

// 用登录后同一个权限 store 推算账号能进哪些页面，避免另写一套规则。
// admin_surface / entry_surface 与后端 User 模型的同名属性一致。
export function accessForUser(user) {
  const auth = useAuthStore(createPinia())
  const isAdmin = user.role === 'admin'
  auth.user = normalizeUser({
    ...user,
    admin_surface: isAdmin,
    entry_surface: isAdmin || Boolean(user.is_mobile_user)
  })
  // 采购办理人登录后只进单独的物资采购工作台（路由守卫 isProcurementOnly）。
  const groups = auth.isProcurementOnly
    ? [{ label: '采购', titles: ['物资采购'] }]
    : auth.canAccessDesktop
      ? manageSearchGroups(auth).map((group) => ({
        label: group.label || '主线',
        titles: group.items.map((item) => item.title)
      }))
      : []
  return {
    fill: !auth.isProcurementOnly && auth.canAccessFillSurface,
    groups,
    pageCount: groups.reduce((sum, group) => sum + group.titles.length, 0)
  }
}

function accessKey(access) {
  return JSON.stringify([access.fill, access.groups])
}

export function summarizeRoles(users) {
  const byRole = new Map()
  for (const user of users) {
    const row = byRole.get(user.role) || { role: user.role, total: 0, active: 0, users: [] }
    row.total += 1
    if (user.is_active) row.active += 1
    row.users.push(user)
    byRole.set(user.role, row)
  }

  return [...byRole.values()]
    .map(({ users: roleUsers, ...row }) => {
      const counted = roleUsers.some((user) => user.is_active) ? roleUsers.filter((user) => user.is_active) : roleUsers
      const variants = new Map()
      for (const user of counted) {
        const access = accessForUser(user)
        const key = accessKey(access)
        const variant = variants.get(key) || { ...access, count: 0 }
        variant.count += 1
        variants.set(key, variant)
      }
      const list = [...variants.values()].sort((a, b) => b.count - a.count)
      return {
        ...row,
        variants: list,
        fill: new Set(list.map((item) => item.fill)).size > 1 ? 'mixed' : list[0].fill,
        pageCount: new Set(list.map((item) => JSON.stringify(item.groups))).size > 1 ? 'mixed' : list[0].pageCount
      }
    })
    .sort((a, b) => b.total - a.total)
}
