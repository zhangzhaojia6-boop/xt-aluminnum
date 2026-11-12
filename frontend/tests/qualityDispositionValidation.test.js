import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

test('quality issues API unwraps paged envelopes for tables', () => {
  const apiSource = readFileSync(new URL('../src/api/quality.js', import.meta.url), 'utf8')
  assert.match(apiSource, /function unwrapItems/)
  assert.match(apiSource, /Array\.isArray\(payload\)/)
  assert.match(apiSource, /Array\.isArray\(payload\.items\)/)
  assert.match(apiSource, /return unwrapItems\(data\)/)
})
