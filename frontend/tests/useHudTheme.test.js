import { test } from 'node:test'
import assert from 'node:assert/strict'
import { applyHudTheme, clearHudTheme, isHudActive } from '../src/composables/useHudTheme.js'

test('applyHudTheme sets data-xt-theme="hud" on documentElement', () => {
  const fakeDoc = { documentElement: { dataset: {} } }
  applyHudTheme(fakeDoc)
  assert.equal(fakeDoc.documentElement.dataset.xtTheme, 'hud')
  assert.equal(isHudActive(fakeDoc), true)
})

test('clearHudTheme removes data-xt-theme', () => {
  const fakeDoc = { documentElement: { dataset: { xtTheme: 'hud' } } }
  clearHudTheme(fakeDoc)
  assert.equal(fakeDoc.documentElement.dataset.xtTheme, undefined)
  assert.equal(isHudActive(fakeDoc), false)
})

test('clearHudTheme is a no-op when theme is already absent', () => {
  const fakeDoc = { documentElement: { dataset: {} } }
  clearHudTheme(fakeDoc)
  assert.equal(fakeDoc.documentElement.dataset.xtTheme, undefined)
})
