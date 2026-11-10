import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import { writeHudPreference } from '../src/composables/useHudTheme.js'
import { applyRouteTheme, isDarkPath, resolveTheme } from '../src/theme/route-theme.js'

function memoryStorage(initial = {}) {
  const store = new Map(Object.entries(initial))
  return {
    store,
    getItem: (key) => (store.has(key) ? store.get(key) : null),
    setItem: (key, value) => store.set(key, value),
    removeItem: (key) => store.delete(key)
  }
}

function fakeDoc() {
  const classes = new Set()
  return {
    documentElement: {
      dataset: {},
      classList: { add: (c) => classes.add(c), remove: (c) => classes.delete(c), has: (c) => classes.has(c) }
    }
  }
}

test('manage and login are dark; phone entry pages stay light', () => {
  const storage = memoryStorage()
  for (const path of ['/manage', '/manage/today', '/manage/factory-3d', '/login']) {
    assert.equal(resolveTheme(path, storage), 'hud', path)
  }
  for (const path of ['/entry', '/entry/drafts', '/mobile', '/', '/procurement']) {
    assert.equal(resolveTheme(path, storage), 'light', path)
  }
  assert.equal(isDarkPath('/manager-other'), false)
})

test('emergency switch forces light everywhere', () => {
  const storage = memoryStorage({ 'xt-theme-force-light': '1' })
  assert.equal(resolveTheme('/manage/today', storage), 'light')
})

test('applyRouteTheme toggles both the hud attribute and Element Plus dark class', () => {
  const doc = fakeDoc()
  const storage = memoryStorage()
  applyRouteTheme('/manage/live', doc, storage)
  assert.equal(doc.documentElement.dataset.xtTheme, 'hud')
  assert.equal(doc.documentElement.classList.has('dark'), true)

  applyRouteTheme('/entry', doc, storage)
  assert.equal(doc.documentElement.dataset.xtTheme, undefined)
  assert.equal(doc.documentElement.classList.has('dark'), false)

  applyRouteTheme('/login', doc, storage)
  assert.equal(doc.documentElement.dataset.xtTheme, 'hud')
})

test('writeHudPreference only stores the preference and never touches the page', () => {
  const storage = memoryStorage()
  globalThis.localStorage = storage
  globalThis.document = fakeDoc()
  try {
    writeHudPreference(true)
    assert.equal(storage.store.get('xt-theme-preference'), 'hud')
    assert.equal(document.documentElement.dataset.xtTheme, undefined)
    writeHudPreference(false)
    assert.equal(storage.store.has('xt-theme-preference'), false)
  } finally {
    delete globalThis.localStorage
    delete globalThis.document
  }
})

test('index.html sets the dark theme before first paint with the same paths', () => {
  const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8')
  assert.match(html, /\['\/manage', '\/login', '\/admin'\]/)
  assert.match(html, /setAttribute\('data-xt-theme', 'hud'\)/)
  assert.match(html, /classList\.add\('dark'\)/)
  assert.match(html, /xt-theme-force-light/)
  assert.match(html, /html\[data-xt-theme='hud'\] \{ background: #060d18; color-scheme: dark; \}/)
})

test('router applies the route theme after every navigation', () => {
  const router = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
  assert.match(router, /routerInstance\.afterEach\(\(to\) => applyRouteTheme\(to\.path\)\)/)
})
