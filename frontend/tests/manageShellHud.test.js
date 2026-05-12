import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const shellPath = path.resolve('src/layout/ManageShell.vue')
const src = fs.readFileSync(shellPath, 'utf8')

const scriptMatch = src.match(/<script setup>([\s\S]*?)<\/script>/)
assert.ok(scriptMatch)
const scriptBody = scriptMatch[1]

test('ManageShell imports useHudTheme', () => {
  assert.match(scriptBody, /from ['"]\.\.\/composables\/useHudTheme\.js['"]/)
})

test('ManageShell opts into HUD without force (preference-driven)', () => {
  assert.match(scriptBody, /useHudTheme\(\s*\)/, 'must call useHudTheme() with no args')
  assert.doesNotMatch(scriptBody, /useHudTheme\(\s*\{\s*force:\s*true/)
})

test('ManageShell does not rewrite existing lifecycle handlers', () => {
  // The onBeforeUnmount block that removes keydown + assistant listeners
  // must still be present verbatim.
  assert.match(
    scriptBody,
    /onBeforeUnmount\(\(\)\s*=>\s*\{\s*window\.removeEventListener\(['"]keydown['"]/
  )
})

test('ManageShell keeps data-testid="manage-shell"', () => {
  assert.match(src, /data-testid="manage-shell"/)
})

test('ManageShell keeps 数据中枢 brand text', () => {
  assert.match(src, /数据中枢/)
})

test('ManageShell has no forbidden product lexicon', () => {
  assert.doesNotMatch(src, /cyberpunk|palantir|quantum|sci-?fi/i)
})
