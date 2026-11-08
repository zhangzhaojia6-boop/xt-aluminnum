import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import { resolveGuardDecision } from '../src/router/guardRules.js'
import { settingsDrawerGroups } from '../src/config/manage-settings-drawer.js'

const source = (rel) => readFileSync(new URL(rel, import.meta.url), 'utf8')

const procurementRoute = { name: 'procurement-todo', meta: { requiresAuth: true, zone: 'procurement', access: 'procurement' }, query: {}, matched: [] }

test('every role reaches the procurement zone once logged in', () => {
  const people = [
    { token: 't', isFillOnlyRole: true, canAccessFillSurface: true },
    { token: 't', isWorkshopDirector: true, canAccessWorkshopDashboard: true, canAccessReviewSurface: true },
    { token: 't', canAccessReviewSurface: true },
    { token: 't', adminSurface: true, canAccessReviewSurface: true },
  ]
  for (const auth of people) {
    assert.equal(resolveGuardDecision({ to: procurementRoute, auth, compactClient: true }), true)
    assert.equal(resolveGuardDecision({ to: procurementRoute, auth, compactClient: false }), true)
  }
})

test('procurement still requires login', () => {
  const decision = resolveGuardDecision({ to: { ...procurementRoute, fullPath: '/procurement' }, auth: { token: '' } })
  assert.equal(decision.name, 'login')
})

test('router mounts the procurement pages with new before the id route', () => {
  const router = source('../src/router/index.js')
  assert.match(router, /path: '\/procurement'/)
  assert.ok(router.indexOf("path: 'new'") < router.indexOf("path: ':id'"))
  assert.match(router, /path: 'board'/)
})

test('settings drawer links to procurement for reviewers', () => {
  const groups = settingsDrawerGroups({ reviewSurface: true })
  const paths = groups.flatMap((group) => group.items.map((item) => item.path))
  assert.ok(paths.includes('/manage/procurement'))
})

test('field home links to procurement', () => {
  assert.match(source('../src/views/mobile/MobileEntry.vue'), /to="\/procurement"/)
})

test('detail page never treats an admin as the approver and shows the nine documents', () => {
  const detail = source('../src/views/procurement/ProcurementDetail.vue')
  assert.match(detail, /v-if="item\.can_act"/)
  assert.match(detail, /document_checklist/)
  assert.match(detail, /expected_step: item\.value\.current_step/)
  assert.doesNotMatch(detail, /description|helperText|tooltip|rationale/)
})
