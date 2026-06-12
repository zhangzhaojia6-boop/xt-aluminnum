import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/views/master/UserManagement.vue', import.meta.url), 'utf8')

test('UserManagement keeps the real user operations while adding the industrial surface', () => {
  assert.match(source, /data-testid="admin-users-center"/)
  assert.match(source, /权限账号治理/)
  assert.match(source, /admin-users-center__status/)
  assert.match(source, /admin-users-center__panel/)
  assert.match(source, /admin-users-center__table/)
  assert.match(source, /governanceStats/)
  assert.match(source, /fetchUsersPage/)
  assert.match(source, /syncDingtalkUsers/)
  assert.match(source, /createUser/)
  assert.match(source, /updateUser/)
  assert.match(source, /resetUserPassword/)
})

test('UserManagement visual layer stays aligned with the industrial blue command style', () => {
  assert.match(source, /--users-accent:\s*#00f2ff/)
  assert.match(source, /usersScanline/)
  assert.match(source, /账号清单/)
  assert.match(source, /@media \(max-width: 640px\)/)
  assert.match(source, /prefers-reduced-motion/)
  assert.doesNotMatch(source, /ReferencePageFrame/)
  assert.doesNotMatch(source, /reference-page/)
})
