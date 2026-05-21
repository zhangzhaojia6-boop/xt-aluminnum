# Owner Three-Tab Management Skeleton Implementation Plan (Phase A)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Collapse the management end from 30+ routes / 6 nav groups into a 3-tab skeleton (今日 / 生产 / 异常) plus a gear-drawer for admin items, redirect/freeze/delete legacy routes, and keep every existing page reachable through the new structure.

**Architecture:** Reuse existing `ManageShell.vue`, `router/index.js`, and `manage-navigation.js`. Replace the 6 nav groups with 3. Add 3 thin "shell" views that *embed* the most relevant existing dashboard for now — visual rebuilding of today/production/alerts content lives in Phase B (next round). Add a `SettingsDrawer` component that lists admin items previously buried in left nav. Redirect every legacy path to its new home or delete it.

**Tech Stack:** Vue 3 + Vue Router 4 + Pinia + Element Plus + ECharts. Tests via `node --test` for unit, Playwright for e2e.

**Out of scope (Phase B):** rebuilding the visual content of TodayPage / ProductionPage / AlertsPage. Editor (总统计) workstation. Operator (工人) entry consolidation. Other 4 user roles.

**Spec:** `docs/superpowers/specs/2026-05-21-owner-three-tab-management-skeleton-design.md`

---

## File Structure

### New files

| Path | Purpose |
|---|---|
| `frontend/src/views/manage/today/TodayPage.vue` | Thin shell that embeds `OverviewCenter` (Phase B will rebuild content) |
| `frontend/src/views/manage/production/ProductionPage.vue` | Thin shell that embeds `FactoryOverview` |
| `frontend/src/views/manage/alerts/AlertsPage.vue` | Thin shell that embeds the existing entry/anomaly center |
| `frontend/src/components/manage/SettingsDrawer.vue` | Right-side drawer listing admin / settings / 杂项 items |
| `frontend/src/config/manage-settings-drawer.js` | Static data for SettingsDrawer (groups + items) |
| `frontend/tests/manageNavigationSkeleton.test.js` | Unit test: nav has exactly 3 groups |
| `frontend/tests/manageRouteRedirects.test.js` | Unit test: every legacy path resolves to a redirect or new path |
| `frontend/tests/manageSettingsDrawer.test.js` | Unit test: SettingsDrawer items match config |
| `frontend/e2e/owner-three-tab-skeleton.spec.js` | e2e: walk 3 tabs + open drawer + visit one frozen page |

### Modified files

| Path | Change |
|---|---|
| `frontend/src/config/manage-navigation.js` | 6 NAV_GROUPS → 3 (今日 / 生产 / 异常) |
| `frontend/src/router/index.js` | Add 3 new routes; redirect legacy paths; delete 4 dead routes |
| `frontend/src/layout/ManageShell.vue` | Brand link `/manage/overview` → `/manage/today`; add gear button that opens SettingsDrawer |

### Deleted files

| Path | Reason |
|---|---|
| `frontend/src/views/dashboard/Statistics.vue` (route only — keep file if used elsewhere) | Replaced by 今日 tab |
| `frontend/src/views/reports/LiveDashboard.vue` (route only) | Out of Phase A scope |
| `frontend/src/views/reports/ReportDetail.vue` (route only) | 今日 tab supersedes |
| Manage data portal route | Duplicate of 今日 tab |

Note: keep .vue files on disk if they are imported elsewhere. Only remove their route entries. Final cleanup of orphaned files happens in Task 16.

---

## Test Strategy

- **Unit tests** for nav config and route table. Pure JS, no DOM. Use the existing `node --test` pattern (see `frontend/tests/factoryCommandNavigation.test.js` for shape).
- **Component test** for SettingsDrawer using the existing `manageShellHud.test.js` JSDOM pattern.
- **e2e** with Playwright that walks the 3 tabs, opens the drawer, visits one frozen path via the drawer, and visits one redirected legacy path to confirm 200 (not 404).

Each task produces a passing test, an implementation that makes it pass, and a commit.

---

## Task 1: Three-group navigation skeleton

**Files:**
- Create: `frontend/tests/manageNavigationSkeleton.test.js`
- Modify: `frontend/src/config/manage-navigation.js`

- [ ] **Step 1: Write the failing test**

```js
// frontend/tests/manageNavigationSkeleton.test.js
import test from 'node:test'
import assert from 'node:assert/strict'

import { manageNavGroups } from '../src/config/manage-navigation.js'

const ownerAuth = {
  canAccessReviewSurface: true,
  reviewSurface: true,
  adminSurface: false,
  isAdmin: false
}

test('owner skeleton has exactly 3 nav groups: 今日 / 生产 / 异常', () => {
  const groups = manageNavGroups(ownerAuth)
  assert.deepEqual(
    groups.map((g) => g.label),
    ['今日', '生产', '异常']
  )
})

test('each top-level group has exactly one item', () => {
  const groups = manageNavGroups(ownerAuth)
  for (const g of groups) {
    assert.equal(g.items.length, 1, `group ${g.label} should be single-item`)
  }
})

test('top-level paths are /manage/today, /manage/production, /manage/alerts', () => {
  const groups = manageNavGroups(ownerAuth)
  const paths = groups.flatMap((g) => g.items.map((i) => i.path))
  assert.deepEqual(paths, ['/manage/today', '/manage/production', '/manage/alerts'])
})

test('admin items are removed from the top-level nav for owner skeleton', () => {
  const adminAuth = { ...ownerAuth, adminSurface: true, isAdmin: true }
  const groups = manageNavGroups(adminAuth)
  const items = groups.flatMap((g) => g.items)
  for (const stale of ['/manage/ingestion', '/manage/master', '/manage/admin/users', '/manage/admin/templates', '/manage/admin/rules']) {
    assert.equal(items.some((i) => i.path === stale), false, `${stale} should not be in top-level nav`)
  }
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && node --test tests/manageNavigationSkeleton.test.js
```

Expected: FAIL — current `manage-navigation.js` returns 6 groups, not 3.

- [ ] **Step 3: Replace NAV_GROUPS in manage-navigation.js**

```js
// frontend/src/config/manage-navigation.js
import { Bell, Histogram, Sunny } from '@element-plus/icons-vue'

const NAV_GROUPS = [
  {
    label: '今日',
    commandGroup: '今日',
    items: [
      { title: '今日', shortLabel: '今日', path: '/manage/today', icon: Sunny, access: 'review', commandGroup: '今日' }
    ]
  },
  {
    label: '生产',
    commandGroup: '生产',
    items: [
      { title: '生产', shortLabel: '生产', path: '/manage/production', icon: Histogram, access: 'review', commandGroup: '生产' }
    ]
  },
  {
    label: '异常',
    commandGroup: '异常',
    items: [
      { title: '异常', shortLabel: '异常', path: '/manage/alerts', icon: Bell, access: 'review', commandGroup: '异常' }
    ]
  }
]

function canAccess(auth, access) {
  if (access === 'review') return Boolean(auth?.canAccessReviewSurface || auth?.reviewSurface)
  if (access === 'admin') return Boolean(auth?.adminSurface || auth?.isAdmin)
  return true
}

export function manageNavGroups(auth) {
  return NAV_GROUPS
    .map((group) => ({ ...group, items: group.items.filter((item) => canAccess(auth, item.access)) }))
    .filter((group) => group.items.length > 0)
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && node --test tests/manageNavigationSkeleton.test.js
```

Expected: PASS, 4 tests.

- [ ] **Step 5: Run pre-existing factoryCommandNavigation test to confirm we did not break it (it WILL fail — that is intentional, the legacy expectation is what we are removing)**

```bash
cd frontend && node --test tests/factoryCommandNavigation.test.js
```

Expected: FAIL on the legacy assertion `assert.deepEqual(managerGroups.map((group) => group.label), ['工厂状态', '经营效益', '异常质量', 'AI 助手'])`. This confirms we changed the contract on purpose. Delete the `factoryCommandNavigation.test.js` file in Task 16 once the rest of the plan is in place; do **not** delete it now or its absence will hide regressions on intermediate tasks.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/config/manage-navigation.js frontend/tests/manageNavigationSkeleton.test.js
git commit -m "feat(manage-nav): collapse 6 nav groups into 3 owner tabs"
```

---

## Task 2: TodayPage shell

**Files:**
- Create: `frontend/src/views/manage/today/TodayPage.vue`
- Modify: `frontend/tests/manageNavigationSkeleton.test.js` (add a render-existence test? — no, do that in Task 5 e2e. Pure unit test for component existence is too weak.)

- [ ] **Step 1: Write the page**

```vue
<!-- frontend/src/views/manage/today/TodayPage.vue -->
<template>
  <section class="xt-today" data-testid="manage-today">
    <header class="xt-today__header">
      <h1>今日</h1>
      <p class="xt-today__date">{{ today }}</p>
    </header>
    <OverviewCenter />
  </section>
</template>

<script setup>
import { computed } from 'vue'
import OverviewCenter from '../../review/OverviewCenter.vue'

const today = computed(() => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
})
</script>

<style scoped>
.xt-today { display: flex; flex-direction: column; gap: 16px; }
.xt-today__header { display: flex; align-items: baseline; gap: 12px; }
.xt-today__header h1 { font-size: 22px; font-weight: 600; margin: 0; }
.xt-today__date { color: var(--xt-text-muted, #888); margin: 0; }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/manage/today/TodayPage.vue
git commit -m "feat(today): thin TodayPage shell embedding OverviewCenter"
```

Phase B will replace the embedded `OverviewCenter` with the 5-数概览 + 车间条 + 要紧事 + 成本 + folded-prose layout. Keeping the embed for now means the route is fully usable from day one.

---

## Task 3: ProductionPage shell

**Files:**
- Create: `frontend/src/views/manage/production/ProductionPage.vue`

- [ ] **Step 1: Write the page**

```vue
<!-- frontend/src/views/manage/production/ProductionPage.vue -->
<template>
  <section class="xt-production" data-testid="manage-production">
    <header class="xt-production__header">
      <h1>生产</h1>
    </header>
    <FactoryOverview />
  </section>
</template>

<script setup>
import FactoryOverview from '../../factory-command/FactoryOverview.vue'
</script>

<style scoped>
.xt-production { display: flex; flex-direction: column; gap: 16px; }
.xt-production__header h1 { font-size: 22px; font-weight: 600; margin: 0; }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/manage/production/ProductionPage.vue
git commit -m "feat(production): thin ProductionPage shell embedding FactoryOverview"
```

---

## Task 4: AlertsPage shell

**Files:**
- Create: `frontend/src/views/manage/alerts/AlertsPage.vue`

- [ ] **Step 1: Write the page**

```vue
<!-- frontend/src/views/manage/alerts/AlertsPage.vue -->
<template>
  <section class="xt-alerts" data-testid="manage-alerts">
    <header class="xt-alerts__header">
      <h1>异常</h1>
    </header>
    <AnomalyReview />
  </section>
</template>

<script setup>
import AnomalyReview from '../../attendance/AnomalyReview.vue'
</script>

<style scoped>
.xt-alerts { display: flex; flex-direction: column; gap: 16px; }
.xt-alerts__header h1 { font-size: 22px; font-weight: 600; margin: 0; }
</style>
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/views/manage/alerts/AlertsPage.vue
git commit -m "feat(alerts): thin AlertsPage shell embedding AnomalyReview"
```

---

## Task 5: Wire 3 new routes + redirect legacy paths

**Files:**
- Create: `frontend/tests/manageRouteRedirects.test.js`
- Modify: `frontend/src/router/index.js` (add 3 new children under `/manage`, redirect legacy paths, delete dead routes)

- [ ] **Step 1: Write the failing test**

```js
// frontend/tests/manageRouteRedirects.test.js
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const src = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')

test('three new top-level manage routes are wired', () => {
  for (const path of ["path: 'today'", "path: 'production'", "path: 'alerts'"]) {
    assert.match(src, new RegExp(path.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
  }
})

test('legacy paths redirect to new homes', () => {
  const expected = [
    { from: 'overview', to: 'today' },
    { from: 'executive', to: 'today' },
    { from: 'factory/cost', to: 'today' },
    { from: 'factory', to: 'production' },
    { from: 'factory/flow', to: 'production' },
    { from: 'factory/machine-lines', to: 'production' },
    { from: 'factory/coils', to: 'production' },
    { from: 'entry-center', to: 'alerts' },
    { from: 'reconciliation', to: 'alerts' },
    { from: 'quality', to: 'alerts' },
    { from: 'anomaly', to: 'alerts' },
    { from: 'factory/exceptions', to: 'alerts' }
  ]
  for (const { from, to } of expected) {
    const re = new RegExp(`path:\\s*'${from.replace(/\\/g, '\\\\')}'[^}]*redirect[^}]*'${to}'`)
    assert.match(src, re, `legacy path '${from}' should redirect to '${to}'`)
  }
})

test('dead routes are removed from router source', () => {
  for (const dead of ['live-dashboard', 'manage-data-portal']) {
    assert.equal(
      src.includes(`path: '${dead}'`),
      false,
      `dead route '${dead}' should be removed`
    )
  }
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && node --test tests/manageRouteRedirects.test.js
```

Expected: FAIL — none of `today`, `production`, `alerts` are wired yet, none of the redirects exist.

- [ ] **Step 3: Modify router/index.js**

Find the `/manage` route block (around the existing `path: 'overview'` child) and update it:

```js
// add imports near other lazy components
const TodayPage = () => import('../views/manage/today/TodayPage.vue')
const ProductionPage = () => import('../views/manage/production/ProductionPage.vue')
const AlertsPage = () => import('../views/manage/alerts/AlertsPage.vue')
```

Inside the `/manage` route's `children` array, add three new routes near the top:

```js
{ path: 'today', name: 'manage-today', component: TodayPage,
  meta: { ...reviewMeta, title: '今日', canonical: '/manage/today' } },
{ path: 'production', name: 'manage-production', component: ProductionPage,
  meta: { ...reviewMeta, title: '生产', canonical: '/manage/production' } },
{ path: 'alerts', name: 'manage-alerts', component: AlertsPage,
  meta: { ...reviewMeta, title: '异常', canonical: '/manage/alerts' } },
```

Replace each legacy child route's body with a redirect (KEEP the `path:` and `name:` so old links still resolve):

```js
{ path: 'overview', name: 'manage-overview', redirect: { name: 'manage-today' } },
{ path: 'executive', name: 'executive-dashboard', redirect: { name: 'manage-today' } },
{ path: 'factory/cost', name: 'cost-benefit', redirect: { name: 'manage-today' } },
{ path: 'factory', name: 'factory-overview', redirect: { name: 'manage-production' } },
{ path: 'factory/flow', name: 'production-flow', redirect: { name: 'manage-production' } },
{ path: 'factory/machine-lines', name: 'machine-lines', redirect: { name: 'manage-production' } },
{ path: 'factory/coils', name: 'coil-trace', redirect: { name: 'manage-production' } },
{ path: 'entry-center', name: 'entry-center', redirect: { name: 'manage-alerts' } },
{ path: 'reconciliation', name: 'reconciliation', redirect: { name: 'manage-alerts' } },
{ path: 'quality', name: 'quality-center', redirect: { name: 'manage-alerts' } },
{ path: 'anomaly', name: 'anomaly-review', redirect: { name: 'manage-alerts' } },
{ path: 'factory/exceptions', name: 'exception-map', redirect: { name: 'manage-alerts' } },
```

Remove these dead routes entirely:

```
- path: 'live-dashboard'
- path: 'manage-data-portal'
- any duplicate executive-v2 or report-detail entries that exist
```

Also remove the now-unused lazy imports for `LiveDashboard`, `ReportDetail`, `Statistics` if they are not referenced anywhere else in this file.

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && node --test tests/manageRouteRedirects.test.js
```

Expected: PASS, 3 tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/router/index.js frontend/tests/manageRouteRedirects.test.js
git commit -m "feat(manage-router): wire 3 new tabs, redirect legacy paths, remove dead routes"
```

---

## Task 9: e2e walkthrough

**Files:**
- Create: `frontend/e2e/owner-three-tab-skeleton.spec.js`

- [ ] **Step 1: Write the e2e**

```js
// frontend/e2e/owner-three-tab-skeleton.spec.js
import { test, expect } from '@playwright/test'

test.describe('owner three-tab skeleton', () => {
  test.beforeEach(async ({ page }) => {
    // Reuse whatever auth helper the existing manage-shell.spec.js uses.
    // If that helper is not yet exported, copy its setup verbatim here.
    await page.goto('/manage/today')
  })

  test('today tab renders', async ({ page }) => {
    await expect(page.getByTestId('manage-today')).toBeVisible()
    await expect(page.getByRole('heading', { name: '今日' })).toBeVisible()
  })

  test('side nav has exactly 3 top-level groups', async ({ page }) => {
    const labels = await page.locator('.xt-manage__nav-group-label').allTextContents()
    expect(labels).toEqual(['今日', '生产', '异常'])
  })

  test('navigates 3 tabs without 404', async ({ page }) => {
    await page.getByRole('link', { name: '生产' }).click()
    await expect(page.getByTestId('manage-production')).toBeVisible()
    await page.getByRole('link', { name: '异常' }).click()
    await expect(page.getByTestId('manage-alerts')).toBeVisible()
    await page.getByRole('link', { name: '今日' }).click()
    await expect(page.getByTestId('manage-today')).toBeVisible()
  })

  test('legacy /manage/overview redirects to /manage/today', async ({ page }) => {
    await page.goto('/manage/overview')
    await expect(page).toHaveURL(/\/manage\/today$/)
  })

  test('legacy /manage/factory redirects to /manage/production', async ({ page }) => {
    await page.goto('/manage/factory')
    await expect(page).toHaveURL(/\/manage\/production$/)
  })

  test('legacy /manage/quality redirects to /manage/alerts', async ({ page }) => {
    await page.goto('/manage/quality')
    await expect(page).toHaveURL(/\/manage\/alerts$/)
  })

  test('gear button opens settings drawer with frozen items', async ({ page }) => {
    await page.getByRole('button', { name: '设置' }).click()
    await expect(page.getByText('杂项 (冻结)')).toBeVisible()
    await expect(page.getByRole('link', { name: /库存去向/ })).toBeVisible()
  })

  test('frozen page is reachable from drawer', async ({ page }) => {
    await page.getByRole('button', { name: '设置' }).click()
    await page.getByRole('link', { name: /库存去向/ }).click()
    await expect(page).toHaveURL(/\/manage\/factory\/destinations$/)
  })
})
```

- [ ] **Step 2: Run the e2e**

```bash
cd frontend && npx playwright test e2e/owner-three-tab-skeleton.spec.js
```

Expected: PASS, 8 tests. If auth setup differs, adapt the `beforeEach` to match `e2e/manage-shell.spec.js`.

- [ ] **Step 3: Commit**

```bash
git add frontend/e2e/owner-three-tab-skeleton.spec.js
git commit -m "test(e2e): owner three-tab skeleton walkthrough"
```

---

## Task 10: Update existing tests broken by the contract change

**Files:**
- Modify (or delete): `frontend/tests/factoryCommandNavigation.test.js`
- Modify: `frontend/tests/managementCommandCenter.test.js` if it asserts the 6-group label list
- Modify: `frontend/tests/manageShellHud.test.js` if it asserts brand `to="/manage/overview"`

- [ ] **Step 1: Run the full unit suite to find casualties**

```bash
cd frontend && node --test tests/*.test.js 2>&1 | grep -E "(fail|FAIL)"
```

- [ ] **Step 2: For each failing test, decide one of two paths**

**Path A — the test asserts the old 6-group / 14-center contract.** Delete the test file. The new `manageNavigationSkeleton.test.js` and `manageRouteRedirects.test.js` cover the new contract.

**Path B — the test happens to use `/manage/overview` or a legacy path as fixture data.** Replace the fixture with the new path. Do not weaken the assertion.

For `factoryCommandNavigation.test.js` specifically: delete it. Its entire premise is the old contract.

- [ ] **Step 3: Re-run the suite**

```bash
cd frontend && node --test tests/*.test.js
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add -A frontend/tests
git commit -m "test: update unit tests for 3-tab skeleton contract"
```

---

## Task 11: Run full verification

- [ ] **Step 1: Lint / typecheck (if configured)**

```bash
cd frontend && npm run audit
```

If the project has a typecheck script, run it. (No `tsc` is configured per `package.json`; skip if so.)

- [ ] **Step 2: Full unit suite**

```bash
cd frontend && npm run test
```

Expected: all green.

- [ ] **Step 3: Smoke e2e**

```bash
cd frontend && npm run e2e:smoke
```

Expected: pass.

- [ ] **Step 4: Build**

```bash
cd frontend && npm run build
```

Expected: build succeeds. Watch for unresolved imports (a deleted route might still reference a deleted component).

- [ ] **Step 5: Manual smoke (Phase A acceptance)**

Run `npm run dev`, open in both desktop and mobile (DevTools responsive). Confirm:
- Default `/manage` lands on `/manage/today`
- Side nav (desktop) and drawer (mobile) show only 3 groups
- Gear opens drawer; drawer items navigate
- One legacy URL pasted into the address bar redirects

- [ ] **Step 6: Commit only if any leftover fixes were made**

```bash
git status
# if anything is dirty after manual fixes:
git add -A && git commit -m "chore: skeleton verification fixes"
```

---

## Task 12: Final cleanup

**Files:**
- Modify: `frontend/src/router/index.js` (drop unused lazy imports)
- Delete: any orphaned page files only-referenced by deleted routes (verify with grep before deleting)

- [ ] **Step 1: Find orphans**

```bash
cd frontend && node --test tests/manageRouteRedirects.test.js && \
  for f in LiveDashboard ReportDetail Statistics; do \
    grep -rn "$f" src/ tests/ e2e/ || echo "$f: orphan"; done
```

- [ ] **Step 2: Delete confirmed orphans only**

If a `$f: orphan` line appears for a file, delete the corresponding `.vue` and any test that references only it.

- [ ] **Step 3: Re-run full verification**

```bash
cd frontend && npm run test && npm run build
```

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "chore: drop orphaned components after skeleton flatten"
```

---

## Verification Checklist (Phase A done)

- [ ] `/manage` defaults to `/manage/today`
- [ ] Sidebar shows exactly 3 nav groups: 今日 / 生产 / 异常
- [ ] All 12 legacy paths from spec section 6.1 redirect (no 404)
- [ ] All 12 settings/admin/frozen items reachable via gear drawer (per spec 6.2)
- [ ] `live-dashboard`, `manage-data-portal`, `report-detail`, duplicate `executive/v2` routes are gone
- [ ] Mobile drawer (hamburger) and desktop sidebar both render the same 3 groups
- [ ] Brand link → `/manage/today`
- [ ] `npm run test` and `npm run build` green
- [ ] `npm run e2e:smoke` and `e2e/owner-three-tab-skeleton.spec.js` green

---

## What Phase B will do (next round, separate plan)

- Replace `TodayPage` embed with the 5 数概览 + 车间分布条形图 + 要紧事 top 3 + 成本一行 + 折叠 prose layout (spec section 5.1)
- Replace `ProductionPage` embed with厂级今日卡片 + 班次进度 + 车间排名 (spec section 5.2)
- Replace `AlertsPage` embed with single-column severity-sorted timeline (spec section 5.3)
- Add global Cmd-K search覆盖追踪问题
- 数据 hookup: prose / 5 数 / 车间条 wired to the same source-of-truth as钉钉 daily report

---

## Self-Review

Spec coverage:

- spec §3 4 类问题 → Tasks 2/3/4 thin shells provide entry points (full content = Phase B)
- spec §4 顶层骨架 (3 tab + 搜索 + 齿轮) → Tasks 1, 5, 6 (search lives in existing topbar, gear added in Task 6)
- spec §5 各 tab 内部 → Tasks 2/3/4 keep existing embed; full layout deferred to Phase B (called out explicitly)
- spec §6.1 合并 → Task 5 redirects
- spec §6.2 设置抽屉 + 冻结 → Tasks 7, 8
- spec §6.3 删除 → Task 5 (route removal) + Task 12 (orphan file cleanup)
- spec §9 验收 → Task 11 manual smoke + verification checklist above

Placeholder scan: no TBD/TODO. Every step has runnable code or commands.

Type/name consistency: `settingsDrawerGroups`, `SETTINGS_GROUPS`, `manage-today` / `manage-production` / `manage-alerts` route names used consistently across Tasks 5, 7, 8, 9.

Scope: focused on骨架. 三屏内部内容明确推到 Phase B. 不混入 operator entry / editor workstation / 其他角色 — those are spec §10 后续轮次.


## Task 7: Settings drawer config

**Files:**
- Create: `frontend/src/config/manage-settings-drawer.js`

- [ ] **Step 1: Write the config**

```js
// frontend/src/config/manage-settings-drawer.js
export const SETTINGS_GROUPS = [
  {
    label: '配置',
    items: [
      { title: '接入', path: '/manage/ingestion', access: 'admin' },
      { title: '主数据', path: '/manage/master', access: 'admin' },
      { title: '模板', path: '/manage/admin/templates', access: 'admin' },
      { title: '规则', path: '/manage/admin/rules', access: 'admin' }
    ]
  },
  {
    label: '权限',
    items: [
      { title: '用户', path: '/manage/admin/users', access: 'admin' },
      { title: '治理', path: '/manage/governance', access: 'admin' }
    ]
  },
  {
    label: '运维',
    items: [
      { title: '运维', path: '/manage/ops', access: 'admin' },
      { title: '系统', path: '/manage/settings', access: 'admin' },
      { title: 'AI', path: '/manage/ai-assistant', access: 'review' }
    ]
  },
  {
    label: '杂项 (冻结)',
    items: [
      { title: '库存去向', path: '/manage/factory/destinations', access: 'review', frozen: true },
      { title: '库存', path: '/manage/inventory', access: 'review', frozen: true },
      { title: '合同', path: '/manage/contracts', access: 'review', frozen: true }
    ]
  }
]

function canAccess(auth, access) {
  if (access === 'review') return Boolean(auth?.canAccessReviewSurface || auth?.reviewSurface)
  if (access === 'admin') return Boolean(auth?.adminSurface || auth?.isAdmin)
  return true
}

export function settingsDrawerGroups(auth) {
  return SETTINGS_GROUPS
    .map((g) => ({ ...g, items: g.items.filter((i) => canAccess(auth, i.access)) }))
    .filter((g) => g.items.length > 0)
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/config/manage-settings-drawer.js
git commit -m "feat(manage-drawer): config for SettingsDrawer groups + items"
```

---

## Task 8: SettingsDrawer component + test

**Files:**
- Create: `frontend/src/components/manage/SettingsDrawer.vue`
- Create: `frontend/tests/manageSettingsDrawer.test.js`

- [ ] **Step 1: Write the failing test**

```js
// frontend/tests/manageSettingsDrawer.test.js
import test from 'node:test'
import assert from 'node:assert/strict'

import { settingsDrawerGroups, SETTINGS_GROUPS } from '../src/config/manage-settings-drawer.js'

test('drawer hides admin items from review-only owner', () => {
  const groups = settingsDrawerGroups({ canAccessReviewSurface: true, reviewSurface: true })
  const items = groups.flatMap((g) => g.items)
  assert.equal(items.some((i) => i.path === '/manage/ingestion'), false)
  assert.equal(items.some((i) => i.path === '/manage/admin/users'), false)
})

test('drawer exposes admin items to admin', () => {
  const groups = settingsDrawerGroups({
    canAccessReviewSurface: true, reviewSurface: true, adminSurface: true, isAdmin: true
  })
  const items = groups.flatMap((g) => g.items)
  for (const path of ['/manage/ingestion', '/manage/master', '/manage/admin/users', '/manage/admin/templates', '/manage/admin/rules']) {
    assert.equal(items.some((i) => i.path === path), true, `admin should see ${path}`)
  }
})

test('frozen items are flagged', () => {
  const frozen = SETTINGS_GROUPS.flatMap((g) => g.items).filter((i) => i.frozen)
  const paths = frozen.map((i) => i.path).sort()
  assert.deepEqual(paths, [
    '/manage/contracts',
    '/manage/factory/destinations',
    '/manage/inventory'
  ])
})
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && node --test tests/manageSettingsDrawer.test.js
```

Expected: FAIL — `settingsDrawerGroups` exists (Task 7) but tests cover behavior that has not been validated yet. They may pass already; if so, this becomes a regression net rather than a TDD step. Either outcome is fine.

- [ ] **Step 3: Write the component**

```vue
<!-- frontend/src/components/manage/SettingsDrawer.vue -->
<template>
  <el-drawer
    :model-value="open"
    direction="rtl"
    size="360px"
    title="设置"
    @update:model-value="$emit('update:open', $event)"
  >
    <nav class="xt-settings-drawer" aria-label="管理端设置">
      <section v-for="group in groups" :key="group.label" class="xt-settings-drawer__group">
        <h3 class="xt-settings-drawer__group-label">{{ group.label }}</h3>
        <RouterLink
          v-for="item in group.items"
          :key="item.path"
          :to="item.path"
          class="xt-settings-drawer__item"
          :class="{ 'is-frozen': item.frozen }"
          @click="$emit('update:open', false)"
        >
          <span>{{ item.title }}</span>
          <small v-if="item.frozen">冻结</small>
        </RouterLink>
      </section>
    </nav>
  </el-drawer>
</template>

<script setup>
import { computed } from 'vue'
import { useAuthStore } from '../../stores/auth'
import { settingsDrawerGroups } from '../../config/manage-settings-drawer.js'

defineProps({ open: { type: Boolean, default: false } })
defineEmits(['update:open'])

const auth = useAuthStore()
const groups = computed(() => settingsDrawerGroups(auth))
</script>

<style scoped>
.xt-settings-drawer { display: flex; flex-direction: column; gap: 24px; padding: 8px 16px; }
.xt-settings-drawer__group-label {
  font-size: 12px; color: var(--xt-text-muted, #888);
  text-transform: uppercase; letter-spacing: 0.05em; margin: 0 0 8px;
}
.xt-settings-drawer__item {
  display: flex; justify-content: space-between; align-items: center;
  padding: 10px 12px; border-radius: 8px; color: inherit; text-decoration: none;
}
.xt-settings-drawer__item:hover { background: var(--xt-surface-hover, rgba(0,0,0,0.04)); }
.xt-settings-drawer__item.is-frozen { opacity: 0.6; }
.xt-settings-drawer__item small { font-size: 11px; color: var(--xt-text-muted, #888); }
</style>
```

- [ ] **Step 4: Run test**

```bash
cd frontend && node --test tests/manageSettingsDrawer.test.js
```

Expected: PASS, 3 tests.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/manage/SettingsDrawer.vue frontend/tests/manageSettingsDrawer.test.js
git commit -m "feat(manage-drawer): SettingsDrawer component with auth filtering"
```

---



