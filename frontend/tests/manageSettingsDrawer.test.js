import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import { SETTINGS_GROUPS, settingsDrawerGroups } from '../src/config/manage-settings-drawer.js'

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

const requiredPaths = [
  '/manage/ingestion',
  '/manage/master',
  '/manage/alias',
  '/manage/imports',
  '/manage/admin/templates',
  '/manage/admin/rules',
  '/manage/admin/users',
  '/manage/admin/governance',
  '/manage/ops-center',
  '/manage/settings-center',
  '/manage/ai-assistant',
  '/manage/admin/qr-print',
  '/manage/factory/destinations',
  '/manage/inventory',
  '/manage/contracts'
]

const adminPaths = [
  '/manage/ingestion',
  '/manage/master',
  '/manage/alias',
  '/manage/imports',
  '/manage/admin/templates',
  '/manage/admin/rules',
  '/manage/admin/users',
  '/manage/admin/governance',
  '/manage/settings-center',
  '/manage/admin/qr-print'
]

const reviewPaths = [
  '/manage/ops-center',
  '/manage/ai-assistant',
  '/manage/factory/destinations',
  '/manage/inventory',
  '/manage/contracts'
]

const frozenPaths = [
  '/manage/contracts',
  '/manage/factory/destinations',
  '/manage/inventory'
]

function itemPaths(groups) {
  return groups.flatMap((group) => group.items.map((item) => item.path))
}

function routeChildPath(path) {
  return path.replace('/manage/', '')
}

test('review-only owner sees review and frozen items but not admin items', () => {
  const paths = itemPaths(settingsDrawerGroups(reviewAuth))

  for (const path of reviewPaths) {
    assert.equal(paths.includes(path), true, `review owner should see ${path}`)
  }

  for (const path of adminPaths) {
    assert.equal(paths.includes(path), false, `review owner should not see ${path}`)
  }
})

test('admin sees admin items', () => {
  const paths = itemPaths(settingsDrawerGroups(adminAuth))

  for (const path of adminPaths) {
    assert.equal(paths.includes(path), true, `admin should see ${path}`)
  }
})

test('frozen item paths are exact', () => {
  const frozen = SETTINGS_GROUPS.flatMap((group) => group.items).filter((item) => item.frozen)

  assert.deepEqual(frozen.map((item) => item.path).sort(), frozenPaths)
})

test('config includes the required settings paths', () => {
  const paths = itemPaths(SETTINGS_GROUPS)

  assert.deepEqual(paths.sort(), [...requiredPaths].sort())
})

test('config uses current real manage paths only', () => {
  const paths = itemPaths(SETTINGS_GROUPS)
  const routerSrc = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
  const manageBlock = routerSrc.slice(routerSrc.indexOf("path: '/manage'"), routerSrc.indexOf("path: '/review'"))

  for (const stale of ['/manage/governance', '/manage/ops', '/manage/settings']) {
    assert.equal(paths.includes(stale), false, `${stale} should not be in settings drawer`)
  }

  for (const path of paths) {
    assert.match(manageBlock, new RegExp(`path:\\s*'${routeChildPath(path).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}'`), `${path} should be a current manage route`)
  }
})

test('SettingsDrawer component imports config, auth store, RouterLink, and emits update', () => {
  const src = readFileSync(new URL('../src/components/manage/SettingsDrawer.vue', import.meta.url), 'utf8')

  assert.match(src, /from ['"]\.\.\/\.\.\/config\/manage-settings-drawer\.js['"]/)
  assert.match(src, /from ['"]\.\.\/\.\.\/stores\/auth['"]/)
  assert.match(src, /import\s+\{\s*RouterLink\s*\}\s+from ['"]vue-router['"]/)
  assert.match(src, /defineEmits\(\[['"]update:open['"]\]\)/)
  assert.match(src, /emit\(['"]update:open['"],\s*false\)/)
})

test('ManageShell wires the settings drawer gear', () => {
  const src = readFileSync(new URL('../src/layout/ManageShell.vue', import.meta.url), 'utf8')

  assert.match(src, /import\s+SettingsDrawer\s+from ['"]\.\.\/components\/manage\/SettingsDrawer\.vue['"]/)
  assert.match(src, /import\s+\{[^}]*Setting[^}]*\}\s+from ['"]@element-plus\/icons-vue['"]/)
  assert.match(src, /aria-label=["']设置["']/)
  assert.match(src, /settingsDrawerOpen\s*=\s*ref\(false\)/)
  assert.match(src, /<SettingsDrawer\s+v-model:open=["']settingsDrawerOpen["']\s*\/>/)
})
