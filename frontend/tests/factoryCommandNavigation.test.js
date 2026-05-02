import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import { manageNavGroups } from '../src/config/manage-navigation.js'

const routerSource = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')

test('factory command routes are wired under management shell', () => {
  for (const path of [
    "path: 'overview'",
    "path: 'factory/flow'",
    "path: 'factory/machine-lines'",
    "path: 'factory/coils'",
    "path: 'factory/cost'",
    "path: 'factory/destinations'",
    "path: 'factory/exceptions'",
    "path: 'ai-assistant'"
  ]) {
    assert.match(routerSource, new RegExp(path.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
  }
})

test('manager navigation exposes factory command branches and keeps ingestion admin only', () => {
  const managerGroups = manageNavGroups({
    canAccessReviewSurface: true,
    reviewSurface: true,
    canAccessDesktopConfig: false,
    adminSurface: false,
    isAdmin: false
  })
  const managerItems = managerGroups.flatMap((group) => group.items)

  assert.equal(managerItems.some((item) => item.path === '/manage/overview' && item.shortLabel === '工厂总览'), true)
  assert.equal(managerItems.some((item) => item.path === '/manage/factory/flow'), true)
  assert.equal(managerItems.some((item) => item.path === '/manage/factory/machine-lines'), true)
  assert.equal(managerItems.some((item) => item.path === '/manage/ai-assistant'), true)
  assert.equal(managerItems.some((item) => item.path === '/manage/ingestion'), false)
})
