import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const SRC = readFileSync(new URL('../src/views/manage/alerts/AlertsPage.vue', import.meta.url), 'utf8')

test('AlertsPage uses useAlertsTimeline composable', () => {
  assert.match(SRC, /useAlertsTimeline/)
})

test('AlertsPage imports DateSwitcher, DomainFilterChips, EventTimeline', () => {
  assert.match(SRC, /DateSwitcher/)
  assert.match(SRC, /DomainFilterChips/)
  assert.match(SRC, /EventTimeline/)
})

test('AlertsPage initial domains[] driven from route ?domain= query', () => {
  assert.match(SRC, /route\.query\.domain|query\.domain/)
})

test('AlertsPage maps legacy ?surface= to domains on mount', () => {
  for (const s of ['anomaly', 'quality', 'reconciliation']) {
    assert.match(SRC, new RegExp(s))
  }
  assert.match(SRC, /surface/)
})

test('AlertsPage h1 is 异常', () => {
  assert.match(SRC, /<h1>异常<\/h1>/)
})

test('AlertsPage style uses xt tokens, no hex', () => {
  const style = SRC.split('<style')[1] || ''
  assert.equal(/#[0-9a-fA-F]{3,6}/.test(style), false)
  assert.match(style, /var\(--xt-/)
})

test('AlertsPage forbids placeholder copy', () => {
  for (const bad of ['TODO', '暂未', '敬请期待', 'Coming soon']) {
    assert.equal(new RegExp(bad).test(SRC), false, `forbidden copy: ${bad}`)
  }
})

test('AlertsPage uses computed openCount filtering by status open', () => {
  assert.match(SRC, /openCount/)
  assert.match(SRC, /status === 'open'|=== 'open'/)
})
