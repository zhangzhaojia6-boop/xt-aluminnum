import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

test('destination screen shows an unknown coil count as a dash', () => {
  const src = readFileSync(new URL('../src/views/factory-command/DestinationScreen.vue', import.meta.url), 'utf8')
  assert.match(src, /item\.coil_count\s*\?\?\s*'—'/)
})
