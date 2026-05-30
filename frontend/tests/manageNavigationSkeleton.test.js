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
  '/manage/admin/templates',
  '/manage/admin/rules'
]

test('owner skeleton exposes current top-level labels', () => {
  const groups = manageNavGroups(reviewAuth)

  assert.deepEqual(groups.map((group) => group.label), ['今日', '生产', '考勤', '交付'])
})

test('owner skeleton keeps daily report under today and report under delivery', () => {
  const groups = manageNavGroups(reviewAuth)

  assert.deepEqual(groups.map((group) => group.items.length), [2, 2, 1, 1])
})

test('owner skeleton paths point to current user-facing manage pages', () => {
  const groups = manageNavGroups(reviewAuth)
  const paths = groups.flatMap((group) => group.items.map((item) => item.path))

  assert.deepEqual(paths, [
    '/manage/today',
    '/manage/daily-report',
    '/manage/production',
    '/energy/center',
    '/attendance/overview',
    '/manage/reports',
  ])
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
})
