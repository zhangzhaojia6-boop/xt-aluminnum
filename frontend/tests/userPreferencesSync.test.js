import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

function source(relativePath) {
  return readFileSync(new URL(relativePath, import.meta.url), 'utf8')
}

test('user preferences api wraps GET and PUT theme endpoints with quiet errors', () => {
  const src = source('../src/api/user-preferences.js')
  assert.match(src, /api\.get\('\/user\/preferences'/)
  assert.match(src, /api\.put\('\/user\/preferences'/)
  assert.match(src, /skipErrorToast:\s*true/)
})

test('auth store syncs server theme preference into HUD local preference', () => {
  const src = source('../src/stores/auth.js')
  assert.match(src, /fetchUserPreferences/)
  assert.match(src, /writeHudPreference/)
  assert.match(src, /async syncThemePreference\(\)/)
  assert.match(src, /prefs\?\.theme === 'hud'/)
  assert.match(src, /void this\.syncThemePreference\(\)/)
})

test('main bootstraps theme preference after api interceptors are installed', () => {
  const src = source('../src/main.js')
  const setupIdx = src.indexOf('setupApiInterceptors(router, pinia)')
  const syncIdx = src.indexOf('void authStore.syncThemePreference()')
  assert.ok(setupIdx >= 0)
  assert.ok(syncIdx > setupIdx)
})
