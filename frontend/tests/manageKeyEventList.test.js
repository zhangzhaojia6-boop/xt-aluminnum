import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { buildKeyEvents, hasAnyEvent, SLOTS } from '../src/components/manage/_keyEvents.js'

function source(rel) {
  return readFileSync(new URL(rel, import.meta.url), 'utf8')
}

test('SLOTS has 3 fixed slots in order: production, reconciliation, unreported', () => {
  assert.equal(SLOTS.length, 3)
  assert.deepEqual(SLOTS.map((s) => s.slot), ['production', 'reconciliation', 'unreported'])
  assert.deepEqual(SLOTS.map((s) => s.field), ['production_exception_count', 'reconciliation_open_count', 'unreported_shift_count'])
  assert.deepEqual(SLOTS.map((s) => s.surface), ['anomaly', 'reconciliation', 'anomaly'])
})

test('buildKeyEvents marks active=true for count>0, false for 0/missing', () => {
  const events = buildKeyEvents({
    production_exception_count: 2,
    reconciliation_open_count: 0,
    unreported_shift_count: 5
  })
  assert.equal(events.length, 3)
  assert.deepEqual(events.map((e) => e.active), [true, false, true])
  assert.deepEqual(events.map((e) => e.count), [2, 0, 5])
})

test('buildKeyEvents tolerates missing fields and null lane', () => {
  const a = buildKeyEvents({})
  assert.deepEqual(a.map((e) => e.count), [0, 0, 0])
  assert.deepEqual(a.map((e) => e.active), [false, false, false])
  const b = buildKeyEvents(null)
  assert.equal(b.length, 3)
})

test('hasAnyEvent returns true iff any slot count > 0', () => {
  assert.equal(hasAnyEvent({ production_exception_count: 0, reconciliation_open_count: 0, unreported_shift_count: 0 }), false)
  assert.equal(hasAnyEvent({ production_exception_count: 1 }), true)
  assert.equal(hasAnyEvent({ unreported_shift_count: 3 }), true)
  assert.equal(hasAnyEvent({}), false)
  assert.equal(hasAnyEvent(null), false)
})

test('KeyEventList renders 3 cards with active/muted variants and RouterLink', () => {
  const src = source('../src/components/manage/KeyEventList.vue')
  assert.match(src, /from\s+['"]\.\/_keyEvents\.js['"]/)
  assert.match(src, /data-testid="manage-key-events"/)
  assert.match(src, /data-testid="key-event-card"/)
  assert.match(src, /v-for="item in items"/)
  assert.match(src, /'is-muted':\s*!item\.active/)
  assert.match(src, /v-if="item\.active"/)
  assert.match(src, /RouterLink/)
})

test('KeyEventList active card links to /manage/alerts with surface query', () => {
  const src = source('../src/components/manage/KeyEventList.vue')
  assert.match(src, /path:\s*'\/manage\/alerts'/)
  assert.match(src, /surface:\s*item\.surface/)
})

test('KeyEventList muted card shows label + 无', () => {
  const src = source('../src/components/manage/KeyEventList.vue')
  assert.match(src, /\{\{\s*item\.label\s*\}\}\s*无/)
})

test('KeyEventList uses --xt-* tokens, not hardcoded colors', () => {
  const src = source('../src/components/manage/KeyEventList.vue')
  assert.match(src, /var\(--xt-bg-panel\)/)
  assert.match(src, /var\(--xt-border\)/)
  const styleBlock = src.split('<style')[1] || ''
  assert.equal(/#[0-9a-fA-F]{3,6}/.test(styleBlock), false, 'no hex colors allowed')
})
