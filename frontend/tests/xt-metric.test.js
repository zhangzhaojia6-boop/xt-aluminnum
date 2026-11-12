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

test('XtMetric shows a loading placeholder instead of "no trusted data" while loading', () => {
  assert.match(source, /loading: \{ type: Boolean, default: false \}/)
  assert.match(source, /<div v-if="isMissing && loading" class="xt-metric__skeleton"[^>]*data-testid="kpi-loading"/)
  assert.match(source, /<div v-else-if="isMissing" class="xt-metric__empty">暂无可信数据<\/div>/)
  assert.match(source, /prefers-reduced-motion: reduce\) \{ \.xt-metric__skeleton \{ animation: none; \} \}/)
})

test('overview passes the daily loading state to every KPI', () => {
  const today = readFileSync(new URL('../src/views/manage/today/TodayPage.vue', import.meta.url), 'utf8')
  assert.equal((today.match(/<XtMetric/g) || []).length, (today.match(/:loading="snapshot\.pending\.value\.daily"/g) || []).length)
})
