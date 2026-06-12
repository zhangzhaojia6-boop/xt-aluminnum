import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const pagePath = path.resolve('src/views/review/GovernanceCenter.vue')
const src = fs.readFileSync(pagePath, 'utf8')

test('GovernanceCenter keeps the real auth and user distribution data path', () => {
  assert.match(src, /useAuthStore/)
  assert.match(src, /fetchUsersPage/)
  assert.match(src, /if \(!auth\.isAdmin\)/)
  assert.match(src, /fetchUsersPage\(\{\s*limit:\s*300,\s*skip:\s*0\s*\}\)/)
  assert.match(src, /roleDistribution\.value\s*=\s*buildRoleDistribution\(page\.items\s*\|\|\s*\[\]\)/)
})

test('GovernanceCenter keeps role, scope, review, and config state cards', () => {
  for (const field of [
    'roleLabel',
    'scopeLabel',
    'auth.canAccessReviewSurface',
    'auth.canAccessDesktopConfig',
    'auth.dataScopeType',
    'formatRoleLabel'
  ]) {
    assert.match(src, new RegExp(field.replaceAll('.', '\\.')))
  }

  for (const label of ['当前角色', '数据范围', '审阅权限', '配置权限']) {
    assert.match(src, new RegExp(label))
  }
})

test('GovernanceCenter keeps every permission matrix field and source permission', () => {
  for (const field of ['label', 'scope', 'enabled', 'permissionRows']) {
    assert.match(src, new RegExp(field))
  }

  for (const permission of [
    'canAccessFactoryDashboard',
    'canAccessWorkshopDashboard',
    'canAccessReviewDesk',
    'canAccessReviewSurface',
    'canAccessDesktopConfig',
    'isAdmin'
  ]) {
    assert.match(src, new RegExp(permission))
  }

  for (const label of ['能力', '生效范围', '状态', '可用', '不可用']) {
    assert.match(src, new RegExp(label))
  }
})

test('GovernanceCenter keeps role distribution fields and sorting semantics', () => {
  assert.match(src, /buildRoleDistribution/)
  assert.match(src, /counters\.set\(role,\s*\(counters\.get\(role\)\s*\|\|\s*0\)\s*\+\s*1\)/)
  assert.match(src, /\.sort\(\(a,\s*b\)\s*=>\s*b\[1\]\s*-\s*a\[1\]\)/)
  assert.match(src, /\{ role,\s*count \}/)
  assert.match(src, /row\.role/)
  assert.match(src, /row\.count/)
})

test('GovernanceCenter uses the industrial blue responsive surface', () => {
  assert.match(src, /data-testid="review-governance-center"/)
  assert.match(src, /data-testid="governance-center-stats"/)
  assert.match(src, /data-testid="governance-center-permission-table"/)
  assert.match(src, /data-testid="governance-center-permission-mobile"/)
  assert.match(src, /data-testid="governance-center-role-distribution"/)
  assert.match(src, /权限治理/)
  assert.match(src, /治理能力总览/)
  assert.match(src, /角色分布/)
  assert.match(src, /--governance-cyan:\s*#00f2ff/)
  assert.match(src, /governanceSweep/)
  assert.match(src, /governancePulse/)
  assert.match(src, /@media \(max-width: 720px\)/)
})

test('GovernanceCenter remains read-only and avoids forbidden product wording', () => {
  assert.doesNotMatch(src, /createUser|updateUser|deleteUser|resetUserPassword|syncDingtalkUsers/)
  assert.doesNotMatch(src, /cyberpunk|quantum|sci-?fi/i)
})
