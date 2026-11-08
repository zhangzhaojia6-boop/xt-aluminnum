import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/components/xt/XtMetric.vue', import.meta.url), 'utf8')

test('XtMetric shows missing facts as text, never zero', () => {
  assert.match(source, /暂无可信数据/)
  assert.match(source, /value === null \|\| value === undefined \|\| value === ''/)
})

test('XtMetric exposes the fact states', () => {
  for (const state of ['confirmed', 'candidate', 'conflict']) {
    assert.match(source, new RegExp(state))
  }
})

test('XtMetric does not introduce forbidden props', () => {
  assert.doesNotMatch(source, /description|explanation|helperText|tooltip|rationale/)
})
