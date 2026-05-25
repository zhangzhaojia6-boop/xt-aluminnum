import { test } from 'node:test'
import assert from 'node:assert/strict'
import { applyHudTheme, clearHudTheme, isHudActive, writeHudPreference } from '../src/composables/useHudTheme.js'

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

test('writeHudPreference updates localStorage and active document theme', () => {
  const store = new Map()
  globalThis.localStorage = {
    getItem: (key) => store.get(key) || null,
    setItem: (key, value) => store.set(key, value),
    removeItem: (key) => store.delete(key)
  }
  globalThis.document = { documentElement: { dataset: {} } }
  try {
    writeHudPreference(true)
    assert.equal(store.get('xt-theme-preference'), 'hud')
    assert.equal(document.documentElement.dataset.xtTheme, 'hud')
    writeHudPreference(false)
    assert.equal(store.has('xt-theme-preference'), false)
    assert.equal(document.documentElement.dataset.xtTheme, undefined)
  } finally {
    delete globalThis.localStorage
    delete globalThis.document
  }
})
