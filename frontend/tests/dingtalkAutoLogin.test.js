import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const mobileEntrySource = readFileSync(new URL('../src/views/mobile/MobileEntry.vue', import.meta.url), 'utf8')
const authStoreSource = readFileSync(new URL('../src/stores/auth.js', import.meta.url), 'utf8')
const routerSource = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
const dingtalkApiSource = readFileSync(new URL('../src/api/dingtalk.js', import.meta.url), 'utf8')
const loaderSource = readFileSync(new URL('../public/dingtalk-jsapi-loader.js', import.meta.url), 'utf8')

test('dingtalk h5 login api uses the h5 endpoint', () => {
  assert.match(dingtalkApiSource, /dingtalkH5LoginApi/)
  assert.match(dingtalkApiSource, /\/dingtalk\/h5-login/)
  assert.match(authStoreSource, /dingtalkH5LoginApi/)
  assert.match(authStoreSource, /result\.user/)
  assert.match(authStoreSource, /this\.setSession\(token, result\.user, result\.machine_info/)
})

test('mobile entry attempts jsapi auth only in dingtalk runtime', () => {
  assert.match(mobileEntrySource, /isDingTalkRuntime/)
  assert.match(mobileEntrySource, /loadDingTalkJsApi/)
  assert.match(mobileEntrySource, /getDingTalkAuthCode/)
  assert.match(mobileEntrySource, /钉钉鉴权失败，改用账号登录/)
})

test('router lets dingtalk runtime reach mobile entry before token exists', () => {
  assert.match(routerSource, /isDingTalkRuntimeClient/)
  assert.match(routerSource, /to\.name === 'mobile-entry'/)
  assert.match(routerSource, /isDingTalkRuntimeClient\(\)/)
})

test('dingtalk jsapi loader uses pinned open platform script', () => {
  assert.match(loaderSource, /dingtalk-jsapi\/2\.10\.3\/dingtalk\.open\.js/)
  assert.match(loaderSource, /loadDingTalkJsApi/)
})
