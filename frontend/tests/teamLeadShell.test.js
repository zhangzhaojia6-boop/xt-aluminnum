import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const routerSource = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
const loginSource = readFileSync(new URL('../src/views/Login.vue', import.meta.url), 'utf8')
const apiSource = readFileSync(new URL('../src/api/team-lead.js', import.meta.url), 'utf8')
const shellSource = readFileSync(new URL('../src/views/team/TeamLeadShell.vue', import.meta.url), 'utf8')
const overviewSource = readFileSync(new URL('../src/views/team/TeamLeadOverview.vue', import.meta.url), 'utf8')

test('team lead route and login dispatch are wired', () => {
  assert.match(routerSource, /path: '\/team-lead'/)
  assert.match(routerSource, /TeamLeadShell/)
  assert.match(loginSource, /team_leader/)
  assert.match(loginSource, /deputy_leader/)
  assert.match(loginSource, /\/team-lead/)
})

test('team lead api and shell expose five quadrants without helper copy', () => {
  assert.match(apiSource, /fetchTeamLeadOverview/)
  assert.match(apiSource, /\/team-lead\/overview/)
  assert.match(shellSource, /setInterval/)
  assert.match(overviewSource, /scheduled_count/)
  assert.match(overviewSource, /attended_count/)
  assert.match(overviewSource, /reported_count/)
  assert.match(overviewSource, /returned_count/)
  assert.match(overviewSource, /reminder_count/)
  assert.match(overviewSource, /\/entry\/report\/\$\{item\.business_date\}\/\$\{item\.shift_id\}/)
  assert.doesNotMatch(overviewSource, /helperText|description|tooltip|explanation|rationale/)
})
