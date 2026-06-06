import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const file = path.resolve('src/components/hud/ParticleField.vue')

test('ParticleField source exists', () => {
  assert.ok(fs.existsSync(file), 'src/components/hud/ParticleField.vue must exist')
})

test('ParticleField is a static industrial backdrop without decorative WebGL', () => {
  const src = fs.readFileSync(file, 'utf8')
  assert.doesNotMatch(src, /from\s+['"]three['"]/, 'three must not be statically imported')
  assert.doesNotMatch(src, /import\(\s*['"]three['"]\s*\)/, 'three must not be dynamically imported')
  assert.doesNotMatch(src, /requestAnimationFrame|cancelAnimationFrame/, 'decorative RAF loops are forbidden')
  assert.doesNotMatch(src, /WebGLRenderer|BufferGeometry|PointsMaterial|PerspectiveCamera|new THREE/, 'decorative WebGL code is forbidden')
  assert.doesNotMatch(src, /<canvas/, 'static backdrop must not allocate a canvas')
  assert.match(src, /data-testid="hud-particles-fallback"/, 'must keep the testable static fallback layer')
})

test('ParticleField keeps motion-safe static texture only', () => {
  const src = fs.readFileSync(file, 'utf8')
  assert.match(src, /prefers-reduced-motion/, 'must still have an explicit reduced-motion branch')
  assert.doesNotMatch(src, /animation:\s*[^;]*infinite/, 'static backdrop must not use infinite animation')
  assert.doesNotMatch(src, /filter:\s*blur|backdrop-filter/, 'static backdrop must not use blur filters')
})
