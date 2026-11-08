import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const loginPath = path.resolve('src/views/Login.vue')
const src = fs.readFileSync(loginPath, 'utf8')

// Slice the <script setup>...</script> block so we can assert on it alone.
const scriptMatch = src.match(/<script setup>([\s\S]*?)<\/script>/)
assert.ok(scriptMatch, '<script setup> block must exist')
const scriptBody = scriptMatch[1]

test('Login.vue stays on the paper theme', () => {
  assert.doesNotMatch(scriptBody, /useHudTheme/)
})

test('Login.vue shows the rolling line instead of made-up plant status', () => {
  assert.match(scriptBody, /import XtRollingLine from ['"]\.\.\/components\/xt\/XtRollingLine\.vue['"]/)
  assert.match(src, /<XtRollingLine/)
  assert.doesNotMatch(src, /XtFactoryMap|loginMapNodes/)
})

test('Login.vue has no decorative particle backdrop', () => {
  assert.doesNotMatch(scriptBody, /ParticleField|defineAsyncComponent/)
})

test('Login.vue keeps the login form hooks', () => {
  for (const id of ['login-page', 'login-brand', 'login-username', 'login-password', 'login-submit', 'login-error', 'login-workshop-notice']) {
    assert.match(src, new RegExp(`data-testid="${id}"`))
  }
})

test('Login.vue has no forbidden product lexicon', () => {
  assert.doesNotMatch(src, /cyberpunk|palantir|quantum|sci-?fi/i)
})

test('Login.vue keeps 数据中枢 brand tag', () => {
  assert.match(src, /数据中枢/)
})

test('Login.vue style follows the design tokens', () => {
  const styleMatch = src.match(/<style scoped>([\s\S]*)<\/style>/)
  assert.ok(styleMatch)
  assert.match(styleMatch[1], /var\(--xt-primary\)/)
  assert.doesNotMatch(styleMatch[1], /rgba\(|linear-gradient/)
})
