import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const file = path.resolve('src/components/hud/ParticleField.vue')

test('ParticleField source exists', () => {
  assert.ok(fs.existsSync(file), 'src/components/hud/ParticleField.vue must exist')
})

test('ParticleField respects prefers-reduced-motion', () => {
  const src = fs.readFileSync(file, 'utf8')
  assert.match(src, /prefers-reduced-motion/, 'must branch on reduced-motion')
})

test('ParticleField disposes resources on unmount', () => {
  const src = fs.readFileSync(file, 'utf8')
  assert.match(src, /onBeforeUnmount/)
  assert.match(src, /\.dispose\(\)/)
  assert.match(src, /cancelAnimationFrame/)
})

test('ParticleField listens to resize and visibilitychange', () => {
  const src = fs.readFileSync(file, 'utf8')
  assert.match(src, /'resize'/)
  assert.match(src, /'visibilitychange'/)
})

test('ParticleField uses dynamic import for three to keep it out of main bundle', () => {
  const src = fs.readFileSync(file, 'utf8')
  assert.match(src, /await\s+import\(\s*['"]three['"]\s*\)/, 'three must be dynamic-imported')
  const staticImportMatch = src.match(/^import\s+.*\bfrom\s+['"]three['"]/m)
  assert.equal(staticImportMatch, null, 'three must not be statically imported')
})

test('vite.config.js code-splits three into its own chunk', () => {
  const viteCfg = fs.readFileSync(path.resolve('vite.config.js'), 'utf8')
  assert.match(viteCfg, /\/three\//, 'manualChunks must match /three/')
  assert.match(viteCfg, /vendor-three/, 'three chunk name must be vendor-three')
})
