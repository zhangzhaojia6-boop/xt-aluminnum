import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const routerSource = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
const guardSource = readFileSync(new URL('../src/router/guardRules.js', import.meta.url), 'utf8')
const userManagementSource = readFileSync(new URL('../src/views/master/UserManagement.vue', import.meta.url), 'utf8')

test('team lead board is cancelled from active routes', () => {
  assert.match(routerSource, /path: '\/team-lead'/)
  assert.match(routerSource, /redirect: \(to\) => \(\{ path: '\/entry'/)
  assert.doesNotMatch(routerSource, /TeamLeadShell/)
  assert.doesNotMatch(routerSource, /teamLeadMeta/)
  assert.doesNotMatch(routerSource, /team-lead-worker-detail/)
})

test('team lead roles are no longer selectable or used as landing roles', () => {
  assert.doesNotMatch(userManagementSource, /value: 'team_leader'/)
  assert.doesNotMatch(userManagementSource, /value: 'shift_leader'/)
  assert.doesNotMatch(userManagementSource, /value: 'deputy_leader'/)
  assert.match(userManagementSource, /value: 'consumable_stat'/)
  assert.doesNotMatch(guardSource, /isTeamLeadRole/)
  assert.doesNotMatch(guardSource, /team_lead/)
})
