import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const usersApiSource = readFileSync(new URL('../src/api/users.js', import.meta.url), 'utf8')
const userManagementSource = readFileSync(new URL('../src/views/master/UserManagement.vue', import.meta.url), 'utf8')

test('user api exposes dingtalk contact sync endpoint', () => {
  assert.match(usersApiSource, /syncDingtalkUsers/)
  assert.match(usersApiSource, /\/users\/sync-dingtalk/)
})

test('user management page exposes one-click dingtalk member sync', () => {
  assert.match(userManagementSource, /syncDingtalkUsers/)
  assert.match(userManagementSource, /同步钉钉成员/)
  assert.match(userManagementSource, /syncingDingtalk/)
})
