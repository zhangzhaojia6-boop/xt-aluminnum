import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import { manageNavGroups } from '../src/config/manage-navigation.js'

const moduleTileSource = readFileSync(
  new URL('../src/components/xt/XtModuleTile.vue', import.meta.url),
  'utf8',
)
const routerSource = readFileSync(
  new URL('../src/router/index.js', import.meta.url),
  'utf8',
)
const realtimeApiSource = readFileSync(
  new URL('../src/api/realtime.js', import.meta.url),
  'utf8',
)
const executiveApiSource = readFileSync(
  new URL('../src/api/executive.js', import.meta.url),
  'utf8',
)

test('manageNavGroups keeps the manager surface focused on daily factory work', () => {
  const groups = manageNavGroups({
    canAccessReviewSurface: true,
    reviewSurface: true,
    canAccessDesktopConfig: false,
    adminSurface: false,
    isAdmin: false,
  })
  const items = groups.flatMap((group) => group.items)

  assert.deepEqual(groups.map((group) => group.label), ['', '业务', '工具'])
  assert.deepEqual(groups[0].items.map((item) => item.path), ['/manage/today', '/manage/live', '/manage/production', '/manage/coils', '/manage/alerts', '/manage/factory-3d'])
  assert.equal(items.some((item) => item.access === 'admin'), false)
})

test('management shell components do not render numeric module badges', () => {
  assert.doesNotMatch(moduleTileSource, /xt-module-tile__number/)
  assert.doesNotMatch(routerSource, /xt-placeholder-page__number/)
})

test('realtime api exposes missing output weight correction endpoint', () => {
  assert.match(realtimeApiSource, /resolveMissingOutputWeight/)
  assert.match(realtimeApiSource, /api\.patch/)
  assert.match(realtimeApiSource, /\/aggregation\/live\/missing-output\/\$\{entryId\}/)
  assert.match(realtimeApiSource, /skipErrorToast:\s*true/)
})

test('realtime api exposes fill detail ledger endpoint', () => {
  assert.match(realtimeApiSource, /fetchLiveFillDetails/)
  assert.match(realtimeApiSource, /api\.get\('\/aggregation\/live\/fill-details'/)
})

test('retired CostAccountingCenter is absent from the active router', () => {
  assert.doesNotMatch(routerSource, /CostAccountingCenter/)
  assert.doesNotMatch(routerSource, /factory\/cost\/accounting/)
  assert.doesNotMatch(routerSource, /factory-command-cost-accounting/)
})

test('executive api keeps cost strategy snapshot endpoints available for backend compatibility', () => {
  assert.match(executiveApiSource, /saveCostStrategySnapshot/)
  assert.match(executiveApiSource, /api\.post\('\/executive\/cost-strategy-snapshots'/)
  assert.match(executiveApiSource, /tableModels/)
})

test('executive api keeps monthly review status endpoints available for backend compatibility', () => {
  assert.match(executiveApiSource, /fetchCostStrategyReviewStatus/)
  assert.match(executiveApiSource, /updateCostStrategyReviewStatus/)
  assert.match(executiveApiSource, /cost-strategy-snapshots\/review-status/)
  assert.match(executiveApiSource, /api\.get/)
  assert.match(executiveApiSource, /api\.post/)
})

