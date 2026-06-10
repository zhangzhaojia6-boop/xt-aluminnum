import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

function source(rel) {
  return readFileSync(new URL(rel, import.meta.url), 'utf8')
}

test('service worker updates must not force-reload management dashboards', () => {
  const src = source('../src/sw-register.js')

  assert.match(src, /controllerchange/)
  assert.doesNotMatch(src, /window\.location\.reload\(\)/)
})
