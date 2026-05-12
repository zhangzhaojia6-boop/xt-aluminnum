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

test('Login.vue uses useHudTheme composable with force:true', () => {
  assert.match(scriptBody, /useHudTheme\s*\(\s*\{\s*force:\s*true\s*\}\s*\)/)
})

test('Login.vue imports useHudTheme from composables', () => {
  assert.match(scriptBody, /from ['"]\.\.\/composables\/useHudTheme\.js['"]/)
})

test('Login.vue lazy-loads the particle backdrop via defineAsyncComponent', () => {
  assert.match(scriptBody, /defineAsyncComponent\(\s*\(\s*\)\s*=>\s*import\(\s*['"]\.\.\/components\/hud\/ParticleField\.vue['"]\s*\)\s*\)/)
})

test('Login.vue mounts LoginHudBackdrop at the top of login-page', () => {
  const templateMatch = src.match(/<template>([\s\S]*?)<\/template>/)
  assert.ok(templateMatch)
  const tpl = templateMatch[1]
  assert.match(tpl, /<LoginHudBackdrop[^>]*data-testid="login-hud-backdrop"/)
  // Backdrop must sit inside .login-page as the first child, before .login-stage.
  const idxBackdrop = tpl.indexOf('LoginHudBackdrop')
  const idxStage = tpl.indexOf('login-stage')
  assert.ok(idxBackdrop > 0, 'backdrop placeholder not found')
  assert.ok(idxBackdrop < idxStage, 'backdrop must appear before login-stage')
})

test('Login.vue has no forbidden product lexicon', () => {
  assert.doesNotMatch(src, /cyberpunk|palantir|quantum|sci-?fi/i)
})

test('Login.vue keeps 数据中枢 brand tag', () => {
  assert.match(src, /数据中枢/)
})

test('Login.vue style block adds backdrop positioning without touching existing rules', () => {
  const styleMatch = src.match(/<style scoped>([\s\S]*)<\/style>/)
  assert.ok(styleMatch)
  const styleBody = styleMatch[1]
  assert.match(styleBody, /\.login-page__backdrop\s*\{[\s\S]*?position:\s*absolute/)
  assert.match(styleBody, /\.login-page__backdrop\s*\{[\s\S]*?inset:\s*0/)
})
