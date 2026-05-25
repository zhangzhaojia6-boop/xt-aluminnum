import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { findCenterByRouteName, resolveRouteMeta } from '../src/config/navigation.js'

const src = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
const manageBlock = src.slice(src.indexOf("path: '/manage'"), src.indexOf("path: '/review'"))
const factoryCommandShellSrc = readFileSync(new URL('../src/views/factory-command/FactoryCommandShell.vue', import.meta.url), 'utf8')
const reportListSrc = readFileSync(new URL('../src/views/reports/ReportList.vue', import.meta.url), 'utf8')
const reconciliationDetailSrc = readFileSync(new URL('../src/views/reconciliation/ReconciliationDetail.vue', import.meta.url), 'utf8')
const reviewTaskCenterSrc = readFileSync(new URL('../src/views/review/ReviewTaskCenter.vue', import.meta.url), 'utf8')
const overviewCenterSrc = readFileSync(new URL('../src/views/review/OverviewCenter.vue', import.meta.url), 'utf8')
const alertsPageSrc = readFileSync(new URL('../src/views/manage/alerts/AlertsPage.legacy.vue', import.meta.url), 'utf8')
const manageShellSrc = readFileSync(new URL('../src/layout/ManageShell.vue', import.meta.url), 'utf8')
const loginSrc = readFileSync(new URL('../src/views/Login.vue', import.meta.url), 'utf8')
const commandLoginSrc = readFileSync(new URL('../src/reference-command/pages/CommandLogin.vue', import.meta.url), 'utf8')
const guardRulesSrc = readFileSync(new URL('../src/router/guardRules.js', import.meta.url), 'utf8')
const appShellSrc = readFileSync(new URL('../src/layout/AppShell.vue', import.meta.url), 'utf8')
const navigationSrc = readFileSync(new URL('../src/config/navigation.js', import.meta.url), 'utf8')
const moduleCatalogSrc = readFileSync(new URL('../src/reference-command/data/moduleCatalog.js', import.meta.url), 'utf8')
const overviewQuickEntriesBlock = overviewCenterSrc.slice(
  overviewCenterSrc.indexOf('const quickEntries = ['),
  overviewCenterSrc.indexOf('const referenceModules = [')
)
const overviewReferenceModulesBlock = overviewCenterSrc.slice(
  overviewCenterSrc.indexOf('const referenceModules = ['),
  overviewCenterSrc.indexOf('const overviewCards = computed')
)
const overviewAiActionsBlock = overviewCenterSrc.slice(
  overviewCenterSrc.indexOf('const aiManagerActions = computed(() => ['),
  overviewCenterSrc.indexOf('const aiTodaySummary = computed')
)

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function routeLine(path) {
  return manageBlock
    .split(/\r?\n/)
    .find((line) => new RegExp(`path:\\s*'${escapeRegExp(path)}'`).test(line))
}

function assertRedirect(path, targetName) {
  const line = routeLine(path)

  assert.ok(line, `route '${path}' should exist`)
  assert.match(line, /\bredirect\b/, `route '${path}' should redirect`)
  assert.doesNotMatch(line, /\bcomponent\s*:/, `route '${path}' should not keep a component`)

  const redirectSource = line.slice(line.indexOf('redirect'))
  assert.match(
    redirectSource,
    new RegExp(`['"](?:manage-${targetName}|/manage/${targetName})['"]`),
    `route '${path}' should redirect to manage-${targetName}`
  )
}

test('three new top-level manage routes are wired', () => {
  for (const path of ['today', 'production', 'alerts']) {
    assert.ok(routeLine(path), `route '${path}' should exist`)
  }
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
  assert.deepEqual(
    {
      title: resolveRouteMeta('manage-alerts', {}).title,
      centerNo: resolveRouteMeta('manage-alerts', {}).centerNo,
      canonical: resolveRouteMeta('manage-alerts', {}).canonical,
      centerNoFromMap: findCenterByRouteName('manage-alerts')?.no
    },
    {
      title: '异常与补录',
      centerNo: '07',
      canonical: '/manage/alerts',
      centerNoFromMap: '07'
    }
  )
})

test('legacy today routes redirect to manage-today', () => {
  for (const path of [
    'overview',
    'executive',
    'executive/processing-fees',
    'factory/cost',
    'factory/cost/accounting',
    'cost-center'
  ]) {
    assertRedirect(path, 'today')
  }
})

test('legacy production routes redirect to manage-production', () => {
  for (const path of [
    'factory',
    'workshop',
    'factory/flow',
    'factory/machine-lines',
    'factory/coils'
  ]) {
    assertRedirect(path, 'production')
  }
})

test('legacy alerts routes redirect to manage-alerts', () => {
  for (const path of [
    'entry-center',
    'reconciliation',
    'quality',
    'anomaly',
    'factory/exceptions'
  ]) {
    assertRedirect(path, 'alerts')
  }
})

test('quality detail remains a preserved component route', () => {
  const line = routeLine('quality/detail/:id')

  assert.ok(line, "route 'quality/detail/:id' should exist")
  assert.match(src, /const\s+QualityDetail\s*=\s*\(\)\s*=>\s*import\(['"]\.\.\/views\/quality\/QualityDetail\.vue['"]\)/)
  assert.match(line, /\bcomponent:\s*QualityDetail\b/)
  assert.doesNotMatch(line, /\bredirect\b/, "route 'quality/detail/:id' should not redirect")
})

test('legacy alerts routes preserve alert surface', () => {
  for (const [path, surface] of [
    ['reconciliation', 'reconciliation'],
    ['quality', 'quality'],
    ['anomaly', 'anomaly'],
    ['entry-center', 'anomaly'],
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
  assert.match(src, /path:\s*['"]\/quality\/detail\/:id['"],\s*redirect:\s*\(to\)\s*=>\s*\(\{\s*path:\s*`\/manage\/quality\/detail\/\$\{to\.params\.id\}`,\s*query:\s*to\.query,\s*hash:\s*to\.hash\s*\}\)/)
  assert.match(src, /path:\s*['"]\/reconciliation\/center['"],\s*redirect:\s*preserveRouteState\(['"]\/manage\/alerts['"],\s*\{\s*surface:\s*['"]reconciliation['"]\s*\}\)/)
})

test('alerts legacy page switches centers by surface query', () => {
  assert.match(alertsPageSrc, /import\s+\{\s*computed\s*\}\s+from\s+['"]vue['"]/)
  assert.match(alertsPageSrc, /useRoute\(\)/)
  assert.match(alertsPageSrc, /route\.query\.surface\s*===\s*['"]reconciliation['"]/)
  assert.match(alertsPageSrc, /route\.query\.surface\s*===\s*['"]quality['"]/)
  assert.match(alertsPageSrc, /import\s+ReconciliationCenter\s+from\s+['"]\.\.\/\.\.\/reconciliation\/ReconciliationCenter\.vue['"]/)
  assert.match(alertsPageSrc, /import\s+QualityCenter\s+from\s+['"]\.\.\/\.\.\/quality\/QualityCenter\.vue['"]/)
  assert.match(alertsPageSrc, /import\s+AnomalyReview\s+from\s+['"]\.\.\/\.\.\/attendance\/AnomalyReview\.vue['"]/)
  assert.match(alertsPageSrc, /<component\s+:is="activeSurfaceComponent"\s*\/>/)
})

test('dead component routes are redirects only if retained', () => {
  for (const path of ['statistics', 'reports/detail/:id']) {
    const line = routeLine(path)

    if (!line) continue

    assert.match(line, /\bredirect\b/, `route '${path}' should redirect if retained`)
    assert.doesNotMatch(line, /\bcomponent\s*:/, `route '${path}' should not keep a component`)
  }
})

test('deleted route paths stay absent', () => {
  for (const path of ['live-dashboard', 'manage-data-portal']) {
    assert.equal(src.includes(`path: '${path}'`), false, `route '${path}' should not exist`)
  }
})

test('legacy route callers use the owner skeleton tabs', () => {
  assert.match(manageShellSrc, /class="xt-manage__brand"\s+to=["']\/manage\/today["']/, 'manage shell brand should open today tab')
  assert.match(manageShellSrc, /key:\s*route\.path\s*\|\|\s*['"]\/manage\/today['"]/, 'manage shell assistant fallback should use today tab')
  assert.doesNotMatch(manageShellSrc, /\/manage\/overview/, 'manage shell should not call old overview path')
  assert.match(loginSrc, /return\s+['"]\/manage\/today['"]/, 'login review landing should use today tab')
  assert.doesNotMatch(loginSrc, /\/manage\/overview/, 'login should not call old overview path')
  assert.match(commandLoginSrc, /return\s+['"]\/manage\/today['"]/, 'command login review landing should use today tab')
  assert.doesNotMatch(commandLoginSrc, /\/manage\/overview/, 'command login should not call old overview path')
  assert.match(guardRulesSrc, /canAccessReviewSurface\)\s*return\s*\{\s*name:\s*['"]manage-today['"]\s*\}/, 'review guard should land on today')
  assert.match(guardRulesSrc, /canAccessFactoryDashboard\)\s*return\s*\{\s*name:\s*['"]manage-production['"]\s*\}/, 'factory guard should land on production')
  assert.match(guardRulesSrc, /canAccessWorkshopDashboard\)\s*return\s*\{\s*name:\s*['"]manage-production['"]\s*\}/, 'workshop guard should land on production')
  assert.match(appShellSrc, /router\.push\(\{\s*name:\s*['"]manage-today['"]\s*\}\)/, 'app shell review switch should land on today')
  assert.doesNotMatch(reportListSrc, /name:\s*['"]report-detail['"]/, 'report list should not open removed report detail route')
  assert.doesNotMatch(
    reconciliationDetailSrc,
    /name:\s*['"]review-reconciliation-center['"]/,
    'reconciliation detail should return to manage alerts'
  )
  assert.doesNotMatch(
    reviewTaskCenterSrc,
    /name:\s*['"]review-reconciliation-center['"]/,
    'review task center should open manage alerts for reconciliation center'
  )
  assert.match(reconciliationDetailSrc, /surface:\s*['"]reconciliation['"]/, 'reconciliation detail should keep reconciliation surface')
  assert.match(reviewTaskCenterSrc, /surface:\s*['"]reconciliation['"]/, 'review task center should keep reconciliation surface')
  assert.match(reviewTaskCenterSrc, /name:\s*['"]manage-production['"]/, 'review task center should open production tab')
  assert.match(reviewTaskCenterSrc, /workshop_id:\s*String\(workshopId\)/, 'review task center should keep workshop id query')
  assert.doesNotMatch(reviewTaskCenterSrc, /name:\s*['"](?:factory-dashboard|workshop-dashboard)['"]/, 'review task center should not open legacy production routes')
  assert.match(overviewCenterSrc, /surface:\s*['"]quality['"]/, 'overview quality entry should keep quality surface')
  assert.match(overviewCenterSrc, /@click=["']go\(item\.route\s*\|\|\s*item\.routeName\)["']/, 'overview AI actions should support route objects')
  assert.match(overviewAiActionsBlock, /key:\s*['"]predict['"][\s\S]*route:\s*\{\s*name:\s*['"]manage-alerts['"],\s*query:\s*\{\s*surface:\s*['"]quality['"]\s*\}\s*\}/, 'overview AI predict should land on quality surface')
  assert.match(overviewReferenceModulesBlock, /variant:\s*['"]overview['"][\s\S]*routeName:\s*['"]manage-today['"]/, 'overview module should land on today')
  assert.match(overviewReferenceModulesBlock, /variant:\s*['"]factory['"][\s\S]*routeName:\s*['"]manage-production['"]/, 'factory module should land on production')
  assert.match(overviewReferenceModulesBlock, /variant:\s*['"]review['"][\s\S]*routeName:\s*['"]manage-alerts['"]/, 'review module should land on alerts')
  assert.match(overviewReferenceModulesBlock, /variant:\s*['"]quality['"][\s\S]*route:\s*\{\s*name:\s*['"]manage-alerts['"],\s*query:\s*\{\s*surface:\s*['"]quality['"]\s*\}\s*\}/, 'quality module should land on quality surface')
  assert.match(overviewReferenceModulesBlock, /variant:\s*['"]cost['"][\s\S]*routeName:\s*['"]manage-today['"]/, 'cost module should land on today')

  for (const routeName of ['factory-dashboard', 'review-task-center', 'review-quality-center', 'review-cost-accounting']) {
    assert.doesNotMatch(
      overviewQuickEntriesBlock,
      new RegExp(`name:\\s*['"]${routeName}['"]`),
      `overview quick entries should not point to ${routeName}`
    )
  }
  for (const routeName of ['factory-dashboard', 'review-quality-center']) {
    assert.doesNotMatch(
      overviewAiActionsBlock,
      new RegExp(`routeName:\\s*['"]${routeName}['"]`),
      `overview AI actions should not point to ${routeName}`
    )
  }
  assert.match(navigationSrc, /routeName:\s*['"]manage-today['"][\s\S]*routeName:\s*['"]manage-production['"][\s\S]*routeName:\s*['"]manage-alerts['"]/, 'navigation catalog should expose skeleton routes')
  assert.match(moduleCatalogSrc, /moduleId:\s*['"]01['"][\s\S]*routeName:\s*['"]manage-today['"][\s\S]*routePath:\s*['"]\/manage\/today['"]/, 'module catalog overview should land on today')
  assert.match(moduleCatalogSrc, /moduleId:\s*['"]05['"][\s\S]*routeName:\s*['"]manage-production['"][\s\S]*routePath:\s*['"]\/manage\/production['"]/, 'module catalog factory should land on production')
  assert.match(moduleCatalogSrc, /moduleId:\s*['"]09['"][\s\S]*routeName:\s*['"]manage-alerts['"][\s\S]*routePath:\s*['"]\/manage\/alerts\?domain=quality['"]/, 'module catalog quality should land on quality surface')
})

test('factory command shell supports embedded production mounting', () => {
  assert.match(factoryCommandShellSrc, /embedded:\s*\{\s*type:\s*Boolean/, 'shell should expose embedded Boolean prop')
  assert.match(factoryCommandShellSrc, /fc-shell--embedded/, 'shell should add embedded class')
  assert.match(factoryCommandShellSrc, /<header\s+v-if="!embedded"\s+class="fc-shell__head"/, 'shell header should be hidden when embedded')
  assert.match(factoryCommandShellSrc, /<div\s+v-if="!embedded"\s+class="fc-shell__grid"/, 'shell grid should be hidden when embedded')
})
