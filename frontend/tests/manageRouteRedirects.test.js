import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { findCenterByRouteName, resolveRouteMeta } from '../src/config/navigation.js'

const src = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
const manageBlock = src.slice(src.indexOf("path: '/manage'"), src.indexOf("path: '/review'"))
const factoryCommandShellSrc = readFileSync(new URL('../src/views/factory-command/FactoryCommandShell.vue', import.meta.url), 'utf8')
const reportListSrc = readFileSync(new URL('../src/views/reports/ReportList.vue', import.meta.url), 'utf8')
const reconciliationDetailSrc = readFileSync(new URL('../src/views/reconciliation/ReconciliationDetail.vue', import.meta.url), 'utf8')
const manageShellSrc = readFileSync(new URL('../src/layout/ManageShell.vue', import.meta.url), 'utf8')
const loginSrc = readFileSync(new URL('../src/views/Login.vue', import.meta.url), 'utf8')
const guardRulesSrc = readFileSync(new URL('../src/router/guardRules.js', import.meta.url), 'utf8')
const appShellSrc = readFileSync(new URL('../src/layout/AppShell.vue', import.meta.url), 'utf8')
const navigationSrc = readFileSync(new URL('../src/config/navigation.js', import.meta.url), 'utf8')
const manageNavigationSrc = readFileSync(new URL('../src/config/manage-navigation.js', import.meta.url), 'utf8')

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function routeLine(path) {
  return manageBlock
    .split(/\r?\n/)
    .find((line) => new RegExp(`path:\\s*'${escapeRegExp(path)}'`).test(line))
}

test('core top-level manage routes are wired', () => {
  for (const path of ['live', 'today', 'production']) {
    assert.ok(routeLine(path), `route '${path}' should exist`)
  }
})

test('compact management navigation keeps production and fill details entries', () => {
  const compactPathsLine = manageNavigationSrc
    .split(/\r?\n/)
    .find((line) => line.includes('COMPACT_REVIEW_PATHS'))
  assert.match(compactPathsLine, /\/manage\/live/)
  assert.match(compactPathsLine, /\/manage\/today/)
  assert.match(compactPathsLine, /\/manage\/production/)
  assert.match(compactPathsLine, /\/manage\/fill-details/)
})

test('live route is the realtime command surface', () => {
  const line = routeLine('live')

  assert.ok(line, "route 'live' should exist")
  assert.match(src, /const\s+LiveDashboardPage\s*=\s*\(\)\s*=>\s*import\(['"]\.\.\/views\/manage\/live\/LiveDashboardPage\.vue['"]\)/)
  assert.match(line, /\bname:\s*['"]manage-live['"]/)
  assert.match(line, /\bcomponent:\s*LiveDashboardPage\b/)
  assert.match(line, /canonical:\s*['"]\/manage\/live['"]/)
  assert.doesNotMatch(line, /\bcomponent:\s*LiveDashboard\b/)
})

test('daily report and incomplete operation pages redirect to stable destinations', () => {
  const redirects = [
    ['daily-report', /redirect:\s*preserveRouteState\(['"]\/manage\/today['"],\s*\{\s*section:\s*['"]daily-report['"]\s*\}\)/],
    ['ops-center', /redirect:\s*preserveRouteState\(['"]\/manage\/admin\/settings['"]\)/],
    ['settings-center', /redirect:\s*preserveRouteState\(['"]\/manage\/admin\/settings['"]\)/],
  ]

  for (const [path, redirectPattern] of redirects) {
    const line = routeLine(path)

    assert.ok(line, `route '${path}' should exist`)
    assert.match(line, redirectPattern, `route '${path}' should redirect to its stable page`)
    assert.doesNotMatch(line, /\bcomponent:\s*(DailyProductionOverview|OpsCenter|SettingsCenter)\b/)
  }
})

test('redirected legacy pages do not leave unused frontend modules behind', () => {
  for (const page of [
    '../src/views/manage/daily-report/DailyProductionOverview.vue',
    '../src/views/ops/OpsCenter.vue',
    '../src/views/settings/SettingsCenter.vue',
  ]) {
    assert.equal(existsSync(new URL(page, import.meta.url)), false, `${page} should stay removed`)
  }
})

test('system settings route is a lightweight settings page, not the realtime dashboard', () => {
  const line = routeLine('admin/settings')

  assert.ok(line, "route 'admin/settings' should exist")
  assert.match(src, /const\s+SystemSettingsPage\s*=\s*\(\)\s*=>\s*import\(['"]\.\.\/views\/manage\/admin\/SystemSettingsPage\.vue['"]\)/)
  assert.match(line, /\bname:\s*['"]admin-ops-reliability['"]/)
  assert.match(line, /\bcomponent:\s*SystemSettingsPage\b/)
  assert.doesNotMatch(line, /\bcomponent:\s*LiveDashboard\b/)
})

test('owner skeleton route metadata stays unique', () => {
  assert.deepEqual(
    {
      title: resolveRouteMeta('manage-today', {}).title,
      centerNo: resolveRouteMeta('manage-today', {}).centerNo,
      canonical: resolveRouteMeta('manage-today', {}).canonical,
      centerNoFromMap: findCenterByRouteName('manage-today')?.no
    },
    {
      title: '系统总览主视图',
      centerNo: '01',
      canonical: '/manage/today',
      centerNoFromMap: '01'
    }
  )
  assert.equal(findCenterByRouteName('manage-alerts'), null)
  assert.equal(resolveRouteMeta('manage-alerts', {}).legacy, true)
  assert.equal(findCenterByRouteName('review-report-center'), null)
  assert.equal(resolveRouteMeta('review-report-center', {}).legacy, true)
})

test('quality detail remains a preserved component route', () => {
  const line = routeLine('quality/detail/:id')

  assert.ok(line, "route 'quality/detail/:id' should exist")
  assert.match(src, /const\s+QualityDetail\s*=\s*\(\)\s*=>\s*import\(['"]\.\.\/views\/quality\/QualityDetail\.vue['"]\)/)
  assert.match(line, /\bcomponent:\s*QualityDetail\b/)
  assert.doesNotMatch(line, /\bredirect\b/, "route 'quality/detail/:id' should not redirect")
})

test('surface redirects preserve alert surface query', () => {
  for (const [path, surface] of [
    ['anomalies', 'anomaly'],
    ['reconciliation', 'reconciliation'],
    ['quality', 'quality'],
    ['factory/exceptions', 'anomaly']
  ]) {
    const line = routeLine(path)

    assert.ok(line, `route '${path}' should exist`)
    assert.match(
      line,
      new RegExp(`preserveRouteState\\(['"]\\/manage\\/alerts['"],\\s*\\{\\s*surface:\\s*['"]${surface}['"]\\s*\\}\\)`),
      `route '${path}' should redirect via preserveRouteState with ${surface}`
    )
  }

  assert.match(src, /path:\s*['"]\/review\/quality['"],\s*redirect:\s*preserveRouteState\(['"]\/manage\/alerts['"],\s*\{\s*surface:\s*['"]quality['"]\s*\}\)/)
  assert.match(src, /path:\s*['"]\/review\/reconciliation['"],\s*redirect:\s*preserveRouteState\(['"]\/manage\/alerts['"],\s*\{\s*surface:\s*['"]reconciliation['"]\s*\}\)/)
  assert.match(src, /path:\s*['"]\/quality\/center['"],\s*redirect:\s*preserveRouteState\(['"]\/manage\/alerts['"],\s*\{\s*surface:\s*['"]quality['"]\s*\}\)/)
  assert.match(src, /path:\s*['"]\/reconciliation\/center['"],\s*redirect:\s*preserveRouteState\(['"]\/manage\/alerts['"],\s*\{\s*surface:\s*['"]reconciliation['"]\s*\}\)/)
})

test('legacy workshop manage path redirects to current workshop dashboard', () => {
  const line = routeLine('workshop')

  assert.ok(line, "route 'workshop' should exist under /manage")
  assert.match(line, /redirect:\s*preserveRouteState\(['"]\/manage\/workshop-dashboard['"]\)/)
})

test('misspelled workshop dashboard path redirects to current workshop dashboard', () => {
  const line = routeLine('workshop-dashborad')

  assert.ok(line, "route 'workshop-dashborad' should exist under /manage")
  assert.match(line, /redirect:\s*preserveRouteState\(['"]\/manage\/workshop-dashboard['"]\)/)
})

test('deleted route paths stay absent', () => {
  for (const path of ['live-dashboard', 'manage-data-portal']) {
    assert.equal(src.includes(`path: '${path}'`), false, `route '${path}' should not exist`)
  }
})

test('legacy route callers use the owner skeleton tabs', () => {
  assert.match(manageShellSrc, /const\s+manageHomePath\s*=\s*computed\(\(\)\s*=>\s*auth\.isWorkshopDirector\s*\?\s*['"]\/manage\/workshop-dashboard['"]\s*:\s*['"]\/manage\/today['"]\)/, 'manage shell brand should send workshop directors to their dashboard and reviewers to today')
  assert.match(manageShellSrc, /class="xt-manage__brand"\s+:to="navTo\(manageHomePath\)"/, 'manage shell brand should use the role-aware home path')
  assert.match(manageShellSrc, /key:\s*route\.path\s*\|\|\s*['"]\/manage\/today['"]/, 'manage shell assistant fallback should use today tab')
  assert.doesNotMatch(manageShellSrc, /\/manage\/overview/, 'manage shell should not call old overview path')
  assert.match(loginSrc, /if\s*\(\s*auth\.adminSurface\s*\)\s*return\s+['"]\/admin['"]/, 'login landing should preserve admin entry')
  assert.match(loginSrc, /if\s*\(\s*auth\.isWorkshopDirector\s*\)\s*return\s+['"]\/manage\/workshop-dashboard['"]/, 'workshop directors should land on their dashboard')
  assert.match(loginSrc, /auth\.reviewSurface\s*\?\s*['"]\/manage\/today['"]\s*:\s*['"]\/login['"]/, 'review users should reach management instead of being blocked')
  assert.match(loginSrc, /if\s*\(\s*!\s*auth\.canAccessDesktop\s*\)/, 'login should only reject accounts without desktop access')
  assert.doesNotMatch(loginSrc, /仅管理员可登录管理端/, 'login should not reject workshop directors with admin-only wording')
  assert.doesNotMatch(loginSrc, /\/manage\/overview/, 'login should not call old overview path')
  assert.match(guardRulesSrc, /canAccessReviewSurface\)\s*return\s*\{\s*name:\s*['"]manage-today['"]\s*\}/, 'review guard should land on today')
  assert.match(guardRulesSrc, /canAccessFactoryDashboard\)\s*return\s*\{\s*name:\s*['"]manage-production['"]\s*\}/, 'factory guard should land on production')
  assert.match(guardRulesSrc, /canAccessWorkshopDashboard\)\s*return\s*\{\s*name:\s*['"]manage-workshop-dashboard['"]\s*\}/, 'workshop guard should land on workshop dashboard')
  assert.match(appShellSrc, /router\.push\(\{\s*name:\s*['"]manage-today['"]\s*\}\)/, 'app shell review switch should land on today')
  assert.doesNotMatch(reportListSrc, /name:\s*['"]report-detail['"]/, 'report list should not open removed report detail route')
  assert.doesNotMatch(
    reconciliationDetailSrc,
    /name:\s*['"]review-reconciliation-center['"]/,
    'reconciliation detail should return to manage alerts'
  )
  assert.match(reconciliationDetailSrc, /surface:\s*['"]reconciliation['"]/, 'reconciliation detail should keep reconciliation surface')
  assert.match(navigationSrc, /routeName:\s*['"]manage-live['"][\s\S]*routeName:\s*['"]manage-today['"][\s\S]*routeName:\s*['"]manage-production['"]/, 'navigation catalog should expose active skeleton routes')
  const centerNavigationBlock = navigationSrc.slice(0, navigationSrc.indexOf('const centerByRouteName'))
  assert.doesNotMatch(centerNavigationBlock, /routeName:\s*['"]manage-alerts['"]/, 'navigation catalog should not surface alerts as an active center')
  assert.doesNotMatch(centerNavigationBlock, /routeName:\s*['"]review-report-center['"]/, 'navigation catalog should not surface reports as an active center')
})

test('report archive route stays readable but is not a generation console', () => {
  const line = routeLine('reports')
  const reportsApiSrc = readFileSync(new URL('../src/api/reports.js', import.meta.url), 'utf8')

  assert.ok(line, "route 'reports' should exist as an archive")
  assert.match(line, /\bcomponent:\s*ReportList\b/)
  assert.match(line, /canonical:\s*['"]\/manage\/reports['"]/)
  assert.match(reportsApiSrc, /export\s+async\s+function\s+fetchReports/)
  for (const mutation of ['generateReport', 'reviewReport', 'publishReport', 'runDailyPipeline', 'finalizeReport', 'exportReport']) {
    assert.equal(reportsApiSrc.includes(`function ${mutation}`), false, `${mutation} should not stay as an unused frontend API wrapper`)
  }
})

test('factory command shell supports embedded production mounting', () => {
  assert.match(factoryCommandShellSrc, /embedded:\s*\{\s*type:\s*Boolean/, 'shell should expose embedded Boolean prop')
  assert.match(factoryCommandShellSrc, /fc-shell--embedded/, 'shell should add embedded class')
  assert.match(factoryCommandShellSrc, /<header\s+v-if="!embedded"\s+class="fc-shell__head"/, 'shell header should be hidden when embedded')
  assert.match(factoryCommandShellSrc, /<div\s+v-if="!embedded"\s+class="fc-shell__grid"/, 'shell grid should be hidden when embedded')
})
