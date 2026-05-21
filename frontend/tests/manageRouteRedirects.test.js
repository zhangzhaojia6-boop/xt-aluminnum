import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const src = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
const manageBlock = src.slice(src.indexOf("path: '/manage'"), src.indexOf("path: '/review'"))
const factoryCommandShellSrc = readFileSync(new URL('../src/views/factory-command/FactoryCommandShell.vue', import.meta.url), 'utf8')
const reportListSrc = readFileSync(new URL('../src/views/reports/ReportList.vue', import.meta.url), 'utf8')
const reconciliationDetailSrc = readFileSync(new URL('../src/views/reconciliation/ReconciliationDetail.vue', import.meta.url), 'utf8')
const reviewTaskCenterSrc = readFileSync(new URL('../src/views/review/ReviewTaskCenter.vue', import.meta.url), 'utf8')
const overviewCenterSrc = readFileSync(new URL('../src/views/review/OverviewCenter.vue', import.meta.url), 'utf8')
const overviewQuickEntriesBlock = overviewCenterSrc.slice(
  overviewCenterSrc.indexOf('const quickEntries = ['),
  overviewCenterSrc.indexOf('const referenceModules = [')
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
    'quality/detail/:id',
    'anomaly',
    'factory/exceptions'
  ]) {
    assertRedirect(path, 'alerts')
  }
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
})

test('factory command shell supports embedded production mounting', () => {
  assert.match(factoryCommandShellSrc, /embedded:\s*\{\s*type:\s*Boolean/, 'shell should expose embedded Boolean prop')
  assert.match(factoryCommandShellSrc, /fc-shell--embedded/, 'shell should add embedded class')
  assert.match(factoryCommandShellSrc, /<header\s+v-if="!embedded"\s+class="fc-shell__head"/, 'shell header should be hidden when embedded')
  assert.match(factoryCommandShellSrc, /<div\s+v-if="!embedded"\s+class="fc-shell__grid"/, 'shell grid should be hidden when embedded')
})
