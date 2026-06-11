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
  assert.match(src, /skipAuthLogout:\s*true/)
})

test('api interceptor can keep login when optional request gets 401', () => {
  const src = source('../src/api/index.js')
  assert.match(src, /skipAuthLogout/)
  assert.match(src, /status === 401 && !skipAuthLogout/)
})

test('api interceptor translates network failures into clear Chinese messages', () => {
  const src = source('../src/api/index.js')
  assert.match(src, /formatApiErrorMessage/)
  assert.match(src, /ERR_NETWORK/)
  assert.match(src, /连接服务器失败，请检查网络、代理或稍后重试/)
  assert.match(src, /ECONNABORTED/)
  assert.match(src, /请求超时，服务器响应太慢，请稍后重试/)
})

test('login page reuses the clear api network error wording', () => {
  const src = source('../src/views/Login.vue')
  assert.match(src, /formatApiErrorMessage/)
  assert.match(src, /if \(!error\?\.response\) return formatApiErrorMessage\(error\)/)
  assert.match(src, /return formatApiErrorMessage\(error\)/)
  assert.doesNotMatch(src, /Network Error/)
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
