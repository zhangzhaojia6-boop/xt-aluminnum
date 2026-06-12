import test from 'node:test'
import assert from 'node:assert/strict'

import { manageNavGroups } from '../src/config/manage-navigation.js'

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

test('owner skeleton exposes current top-level labels', () => {
  const groups = manageNavGroups(reviewAuth)

  assert.deepEqual(groups.map((group) => group.label), ['实时调度', '昨日报表', '生产分析', '人员考勤'])
})

test('owner skeleton keeps one stable entry per core surface', () => {
  const groups = manageNavGroups(reviewAuth)

  assert.deepEqual(groups.map((group) => group.items.length), [1, 1, 6, 1])
})

test('owner skeleton paths point to current user-facing manage pages', () => {
  const groups = manageNavGroups(reviewAuth)
  const paths = groups.flatMap((group) => group.items.map((item) => item.path))

  assert.deepEqual(paths, [
    '/manage/live',
    '/manage/today',
    '/manage/production',
    '/manage/workshop-dashboard',
    '/manage/coils',
    '/manage/fill-details',
    '/manage/energy',
    '/manage/alerts',
    '/manage/attendance',
  ])
  assert.equal(paths.includes('/manage/daily-report'), false)
  assert.equal(paths.includes('/manage/ops-center'), false)
  assert.equal(paths.includes('/manage/settings-center'), false)
  assert.equal(paths.includes('/manage/reports'), false)
})

test('compact management navigation exposes the same review pages as the compact route guard', () => {
  const groups = manageNavGroups(reviewAuth, { compact: true })
  const paths = groups.flatMap((group) => group.items.map((item) => item.path))

  assert.deepEqual(groups.map((group) => group.label), ['实时调度', '昨日报表', '生产分析'])
  assert.deepEqual(paths, ['/manage/live', '/manage/today', '/manage/production', '/manage/coils', '/manage/fill-details', '/manage/energy'])
})

test('compact management navigation keeps admin users on the same review pages as compact review users', () => {
  const groups = manageNavGroups(adminAuth, { compact: true })
  const paths = groups.flatMap((group) => group.items.map((item) => item.path))

  assert.deepEqual(groups.map((group) => group.label), ['实时调度', '昨日报表', '生产分析'])
  assert.deepEqual(paths, ['/manage/live', '/manage/today', '/manage/production', '/manage/coils', '/manage/fill-details', '/manage/energy'])
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

test('admin core configuration paths are exposed in top-level navigation for admin auth', () => {
  const groups = manageNavGroups(adminAuth)
  const paths = groups.flatMap((group) => group.items.map((item) => item.path))

  for (const path of adminPaths) {
    assert.equal(paths.includes(path), true)
  }
})

test('admin skeleton exposes system settings in top-level navigation', () => {
  const groups = manageNavGroups(adminAuth)
  const items = groups.flatMap((group) => group.items)

  assert.equal(items.some((item) => item.path === '/manage/admin/settings'), true)
  assert.equal(items.some((item) => item.title === '系统设置'), true)
  assert.equal(items.some((item) => item.path === '/manage/admin/templates'), false)
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
