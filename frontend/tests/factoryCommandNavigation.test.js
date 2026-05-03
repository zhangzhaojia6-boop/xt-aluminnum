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
  assert.equal(managerItems.some((item) => item.path === '/manage/factory/coils'), true)
  assert.equal(managerItems.some((item) => item.path === '/manage/factory/destinations'), true)
  assert.equal(managerItems.some((item) => item.path === '/manage/factory/exceptions'), true)
  assert.equal(managerItems.some((item) => item.path === '/manage/ai-assistant'), true)
  assert.equal(managerItems.some((item) => item.path === '/manage/ingestion'), false)

  for (const retiredLabel of ['班次中心', '填报审核', '导入历史', '别名映射', '系统设置', '权限治理', '成本核算与效益中心']) {
    assert.equal(managerGroups.some((group) => group.label === retiredLabel || group.commandGroup === retiredLabel), false)
    assert.equal(managerItems.some((item) => item.title === retiredLabel || item.shortLabel === retiredLabel), false)
  }
})

test('admin navigation keeps necessary configuration without exposing low frequency fragments', () => {
  const adminGroups = manageNavGroups({
    canAccessReviewSurface: true,
    reviewSurface: true,
    canAccessDesktopConfig: true,
    adminSurface: true,
    isAdmin: true
  })
  const adminItems = adminGroups.flatMap((group) => group.items)

  assert.equal(adminItems.some((item) => item.title === '主数据与模板中心'), true)
  assert.equal(adminItems.some((item) => item.title === '用户管理'), true)
  assert.equal(adminItems.some((item) => item.title.includes('数据接入')), true)
  assert.equal(adminItems.some((item) => item.title === '导入历史'), false)
  assert.equal(adminItems.some((item) => item.title === '别名映射'), false)
  assert.equal(adminItems.some((item) => item.title === '系统设置'), false)
  assert.equal(adminItems.some((item) => item.title.includes('权限与治理')), false)
})

test('legacy shift management path redirects into master data', () => {
  assert.match(routerSource, /path: 'shift', redirect: '\/manage\/master'/)
})

test('legacy cost and ai paths redirect to the slim management surfaces', () => {
  assert.match(routerSource, /path: 'cost', name: 'review-cost-accounting', redirect: '\/manage\/factory\/cost'/)
  assert.match(routerSource, /path: 'ai', name: 'review-brain-center', redirect: '\/manage\/ai-assistant'/)
  assert.match(routerSource, /path: '\/review\/cost-accounting', redirect: '\/manage\/factory\/cost'/)
  assert.match(routerSource, /path: '\/review\/brain', redirect: '\/manage\/ai-assistant'/)
})
