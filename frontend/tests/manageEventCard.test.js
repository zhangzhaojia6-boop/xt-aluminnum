import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const SRC = readFileSync(new URL('../src/components/manage/EventCard.vue', import.meta.url), 'utf8')

test('EventCard renders time, domain pill, summary, arrow', () => {
  for (const slot of ['xt-event-card__time', 'xt-event-card__pill', 'xt-event-card__summary', 'xt-event-card__arrow']) {
    assert.match(SRC, new RegExp(slot), `missing ${slot}`)
  }
})

test('EventCard maps 4 domains to xt color tokens via color-mix', () => {
  for (const token of ['--xt-color-warning', '--xt-color-danger', '--xt-color-accent', '--xt-text-muted']) {
    assert.match(SRC, new RegExp(token.replace(/-/g, '\\-')))
  }
  assert.match(SRC, /color-mix/)
})

test('EventCard uses no hex or rgba color literals', () => {
  const style = SRC.split('<style')[1] || ''
  assert.equal(/#[0-9a-fA-F]{3,6}/.test(style), false)
  assert.equal(/rgba?\(\s*\d/.test(style), false)
})

test('EventCard root is a native button for a11y', () => {
  assert.match(SRC, /@click/)
  assert.match(SRC, /<button[\s\S]*type="button"/)
  assert.equal(/<el-button/.test(SRC), false)
})

test('EventCard renders fallback card style when event.isFallback', () => {
  assert.match(SRC, /isFallback/)
  assert.match(SRC, /is-fallback/)
})

test('EventCard domain pill labels are 中文', () => {
  for (const label of ['生产', '质检', '对账', '填报']) {
    assert.match(SRC, new RegExp(label))
  }
})
