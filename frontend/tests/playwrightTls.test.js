import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

import { shouldIgnoreHttpsErrors } from '../e2e/helpers/tls.js'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const configPath = path.resolve(__dirname, '../playwright.config.js')

test('playwright tls errors are ignored only for local https or explicit opt-in', () => {
  assert.equal(shouldIgnoreHttpsErrors({ baseURL: 'https://localhost' }), true)
  assert.equal(shouldIgnoreHttpsErrors({ baseURL: 'https://app.localhost:4173' }), true)
  assert.equal(shouldIgnoreHttpsErrors({ baseURL: 'https://127.0.0.1:4173' }), true)
  assert.equal(shouldIgnoreHttpsErrors({ baseURL: 'https://0.0.0.0:4173' }), true)
  assert.equal(shouldIgnoreHttpsErrors({ baseURL: 'http://127.0.0.1:4173' }), false)
  assert.equal(shouldIgnoreHttpsErrors({ baseURL: 'https://mes.xintaily.com' }), false)
  assert.equal(shouldIgnoreHttpsErrors({ baseURL: 'https://mes.xintaily.com', allowInsecureTLS: '1' }), true)
  assert.equal(shouldIgnoreHttpsErrors({ baseURL: 'https://mes.xintaily.com', allowInsecureTLS: 'false' }), false)
})

test('playwright config does not hardcode tls errors as ignored', () => {
  const source = readFileSync(configPath, 'utf8')

  assert.match(source, /ignoreHTTPSErrors:\s*shouldIgnoreHttpsErrors/)
  assert.doesNotMatch(source, /ignoreHTTPSErrors:\s*true/)
})
