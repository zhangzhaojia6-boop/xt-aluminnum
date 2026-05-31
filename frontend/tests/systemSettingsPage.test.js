import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const src = readFileSync(new URL('../src/views/manage/admin/SystemSettingsPage.vue', import.meta.url), 'utf8')

test('SystemSettingsPage keeps the current settings entry routes', () => {
  for (const path of [
    '/manage/master',
    '/manage/alias',
    '/manage/admin/users',
    '/manage/admin/templates',
    '/manage/admin/rules',
    '/manage/admin/governance',
    '/manage/admin/qr-print',
    '/manage/ai-assistant'
  ]) {
    assert.match(src, new RegExp(path.replaceAll('/', '\\/')))
  }
})

test('SystemSettingsPage keeps the settings hub test id and grouped structure', () => {
  assert.match(src, /data-testid="system-settings-page"/)
  assert.match(src, /const settingGroups = \[/)
  assert.match(src, /label: '配置'/)
  assert.match(src, /label: '权限'/)
  assert.match(src, /label: '工具 \/ 助手'/)
})

test('SystemSettingsPage exposes industrial status and linkage panels', () => {
  assert.match(src, /配置完整度/)
  assert.match(src, /系统联动监控/)
  assert.match(src, /xt-system-settings__ring/)
  assert.match(src, /xt-system-settings__linkage/)
})

test('SystemSettingsPage has mobile responsive layout protection', () => {
  assert.match(src, /@media \(max-width: 720px\)/)
  assert.match(src, /overflow-x: hidden/)
})
