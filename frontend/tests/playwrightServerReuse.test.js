import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const configSource = readFileSync(new URL('../playwright.config.js', import.meta.url), 'utf8')

test('playwright existing-server reuse needs an explicit trust flag', () => {
  assert.match(configSource, /PLAYWRIGHT_REUSE_SERVERS/)
  assert.match(configSource, /PLAYWRIGHT_TRUST_EXISTING_SERVERS/)
  assert.match(configSource, /PLAYWRIGHT_REUSE_SERVERS[\s\S]*PLAYWRIGHT_TRUST_EXISTING_SERVERS/)
})
