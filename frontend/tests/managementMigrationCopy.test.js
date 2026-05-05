import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import { buildShellNavigation, NAV_ROUTE_META } from '../src/config/navigation.js'

const routerSource = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
const overviewSource = readFileSync(new URL('../src/views/review/OverviewCenter.vue', import.meta.url), 'utf8')
const appShellSource = readFileSync(new URL('../src/layout/AppShell.vue', import.meta.url), 'utf8')

test('management routes no longer expose migration placeholders', () => {
  assert.doesNotMatch(routerSource, /功能正在迁移中/)
  assert.doesNotMatch(routerSource, /component: page\(/)
  assert.match(routerSource, /path: 'admin'[^}]+redirect: '\/manage\/admin\/settings'/s)
  assert.match(routerSource, /path: '\/admin', redirect: '\/manage\/admin\/settings'/)
  assert.match(routerSource, /path: '\/admin\/overview', redirect: '\/manage\/admin\/settings'/)
})

test('management overview does not label active admin modules as migrating', () => {
  assert.doesNotMatch(overviewSource, /改造中/)
  assert.doesNotMatch(overviewSource, /待迁移/)
})

test('admin shell navigation does not expose retired overview route', () => {
  const groups = buildShellNavigation('admin', { isAdmin: true })
  const items = groups.flatMap((group) => group.items)

  assert.equal(items.some((item) => item.routeName === 'admin-overview'), false)
  assert.equal(items.filter((item) => item.routeName === 'admin-ops-reliability').length, 1)
  assert.equal(NAV_ROUTE_META['admin-overview'].legacy, true)
  assert.match(appShellSource, /router\.push\(\{ name: 'admin-ops-reliability' \}\)/)
})
