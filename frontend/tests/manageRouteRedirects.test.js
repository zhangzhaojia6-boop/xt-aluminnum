import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const src = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
const manageBlock = src.slice(src.indexOf("path: '/manage'"), src.indexOf("path: '/review'"))

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
