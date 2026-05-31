import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const src = readFileSync(new URL('../src/layout/EntryShell.vue', import.meta.url), 'utf8')

test('EntryShell bottom navigation points operators to active fill and all-day history pages', () => {
  assert.match(src, /path: '\/entry\/fill', label: '录入'/)
  assert.match(src, /path: '\/entry\/history', label: '历史'/)
  assert.doesNotMatch(src, /path: '\/entry\/report', label: '录入'/)
  assert.doesNotMatch(src, /path: '\/entry\/profile', label: '我的'/)
})
