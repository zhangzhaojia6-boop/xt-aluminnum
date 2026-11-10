import test from 'node:test'
import assert from 'node:assert/strict'

import { manageNavGroups } from '../src/config/manage-navigation.js'
import { manageSearchGroups as settingsDrawerGroups } from '../src/config/manage-navigation.js'

const reviewAuth = {
  canAccessReviewSurface: true,
  reviewSurface: true,
  adminSurface: false,
  isAdmin: false
}

const adminAuth = {
  canAccessReviewSurface: true,
  reviewSurface: true,
  adminSurface: true,
  isAdmin: true
}

const adminPaths = [
  '/manage/master',
  '/manage/admin/users',
  '/manage/admin/rules'
]

test('review users get the primary group plus the feature groups they can open', () => {
  const groups = manageNavGroups(reviewAuth)

  assert.deepEqual(groups.map((group) => group.label), ['', '业务', '工具'])
  assert.equal(groups.slice(1).every((group) => group.collapsible), true)
})

test('owner skeleton keeps six primary entries', () => {
  const groups = manageNavGroups(reviewAuth)

  assert.equal(groups[0].items.length, 6)
})

test('owner skeleton paths point to current user-facing manage pages', () => {
  const groups = manageNavGroups(reviewAuth)
  const paths = groups[0].items.map((item) => item.path)

  assert.deepEqual(paths, ['/manage/today', '/manage/live', '/manage/production', '/manage/coils', '/manage/alerts', '/manage/factory-3d'])
  const allPaths = groups.flatMap((group) => group.items.map((item) => item.path))
  assert.equal(allPaths.includes('/manage/daily-report'), false)
  assert.equal(allPaths.includes('/manage/ops-center'), false)
  assert.equal(allPaths.includes('/manage/settings-center'), false)
  assert.equal(allPaths.includes('/manage/admin/settings'), false)
  assert.equal(allPaths.includes('/manage/master'), false)
})

test('compact management navigation exposes the same review pages as the compact route guard', () => {
  const groups = manageNavGroups(reviewAuth, { compact: true })
  const paths = groups.flatMap((group) => group.items.map((item) => item.path))

  assert.deepEqual(groups.map((group) => group.label), ['', '更多'])
  assert.deepEqual([...paths].sort(), ['/manage/coils', '/manage/energy', '/manage/fill-details', '/manage/live', '/manage/production', '/manage/today'])
})

test('compact management navigation keeps admin users on the same review pages as compact review users', () => {
  const groups = manageNavGroups(adminAuth, { compact: true })
  const paths = groups.flatMap((group) => group.items.map((item) => item.path))

  assert.deepEqual(groups.map((group) => group.label), ['', '更多'])
  assert.deepEqual([...paths].sort(), ['/manage/coils', '/manage/energy', '/manage/fill-details', '/manage/live', '/manage/production', '/manage/today'])
})

test('workshop director skeleton only exposes own workshop dashboard', () => {
  const groups = manageNavGroups({
    ...reviewAuth,
    isWorkshopDirector: true,
    canAccessWorkshopDashboard: true,
  })

  assert.deepEqual(groups.map((group) => group.label), ['本车间'])
  assert.deepEqual(groups.flatMap((group) => group.items.map((item) => item.path)), ['/manage/workshop-dashboard'])
})

test('admin core configuration paths are exposed in the settings drawer for admin auth', () => {
  const groups = settingsDrawerGroups(adminAuth)
  const paths = groups.flatMap((group) => group.items.map((item) => item.path))

  for (const path of adminPaths) {
    assert.equal(paths.includes(path), true)
  }
})

test('every former settings destination stays reachable from the nav or search', () => {
  const items = settingsDrawerGroups(adminAuth).flatMap((group) => group.items)
  const paths = new Set(items.map((item) => item.path))

  for (const path of [
    '/manage/workshop-dashboard', '/manage/fill-details', '/manage/energy', '/manage/procurement',
    '/manage/master', '/manage/alias', '/manage/admin/rules', '/manage/mes-terminal-bindings',
    '/manage/admin/users', '/manage/admin/agents', '/manage/channels',
    '/manage/reports', '/manage/ai-assistant', '/manage/rag', '/manage/mapping-reconciliation', '/manage/admin/qr-print',
  ]) {
    assert.equal(paths.has(path), true, path)
  }
  assert.equal(paths.has('/manage/admin/settings'), false)
  assert.equal(paths.has('/manage/admin/governance'), false)
  assert.equal(paths.has('/manage/attendance'), false)
  assert.equal(paths.has('/manage/admin/templates'), false)
})

test('management command labels do not duplicate group and item names', () => {
  const groups = manageNavGroups(adminAuth)
  const searchTexts = groups.flatMap((group) =>
    group.items.map((item) => `${item.shortLabel || item.title}${group.label}`)
  )

  assert.equal(searchTexts.some((text) => text.includes('生产生产')), false)
  assert.equal(searchTexts.some((text) => text.includes('实时实时')), false)
  assert.equal(searchTexts.some((text) => text.includes('考勤考勤')), false)
})
