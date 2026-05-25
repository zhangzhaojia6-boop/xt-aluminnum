import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const SRC = readFileSync(new URL('../src/components/manage/EventTimeline.vue', import.meta.url), 'utf8')

test('EventTimeline shows summary line with totalCount and openCount', () => {
  assert.match(SRC, /totalCount/)
  assert.match(SRC, /openCount/)
  assert.match(SRC, /共/)
  assert.match(SRC, /未结/)
})

test('EventTimeline shows 全部已处理 when openCount is 0', () => {
  assert.match(SRC, /全部已处理/)
})

test('EventTimeline empty state copy is 当日无异常', () => {
  assert.match(SRC, /当日无异常/)
})

test('EventTimeline renders EventCard for each event with key=event.id', () => {
  assert.match(SRC, /<EventCard/)
  assert.match(SRC, /:key="event\.id"|:key="evt\.id"/)
})

test('EventTimeline forwards card click to router.push(event.detailRoute)', () => {
  assert.match(SRC, /router\.push|push\(/)
  assert.match(SRC, /detailRoute/)
})

test('EventTimeline style uses xt tokens, no hex', () => {
  const style = SRC.split('<style')[1] || ''
  assert.equal(/#[0-9a-fA-F]{3,6}/.test(style), false)
  assert.match(style, /var\(--xt-/)
})
