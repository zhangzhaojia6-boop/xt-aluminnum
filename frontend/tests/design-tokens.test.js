import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const tokens = readFileSync(new URL('../src/design/xt-tokens.css', import.meta.url), 'utf8')

test('brand and paper tokens follow the design language', () => {
  assert.match(tokens, /--xt-primary:\s*#003890/)
  assert.match(tokens, /--xt-bg-page:\s*#ffffff/i)
  assert.match(tokens, /--xt-border:\s*#e5e7eb/i)
})

test('dark command tokens are gone', () => {
  assert.doesNotMatch(tokens, /--xt-command-blue-canvas/)
})
