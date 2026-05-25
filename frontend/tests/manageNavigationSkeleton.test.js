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
  '/manage/ingestion',
  '/manage/master',
  '/manage/admin/users',
  '/manage/admin/templates',
  '/manage/admin/rules'
]

test('owner skeleton exposes exactly the three top-level labels', () => {
  const groups = manageNavGroups(reviewAuth)

  assert.deepEqual(groups.map((group) => group.label), ['今日', '生产', '异常'])
})

test('owner skeleton keeps one item per top-level group', () => {
  const groups = manageNavGroups(reviewAuth)

  assert.deepEqual(groups.map((group) => group.items.length), [1, 1, 1])
})

test('owner skeleton paths point to today, production, and alerts', () => {
  const groups = manageNavGroups(reviewAuth)
  const paths = groups.flatMap((group) => group.items.map((item) => item.path))

  assert.deepEqual(paths, ['/manage/today', '/manage/production', '/manage/alerts'])
})

test('admin configuration paths stay out of top-level navigation for admin auth', () => {
  const groups = manageNavGroups(adminAuth)
  const paths = groups.flatMap((group) => group.items.map((item) => item.path))

  for (const path of adminPaths) {
    assert.equal(paths.includes(path), false)
  }
})
