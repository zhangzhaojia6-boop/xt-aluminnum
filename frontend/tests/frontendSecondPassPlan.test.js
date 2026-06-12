import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

function source(rel) {
  return readFileSync(new URL(rel, import.meta.url), 'utf8')
}

const live = source('../src/views/manage/live/LiveDashboardPage.vue')
const today = source('../src/views/manage/today/TodayPage.vue')
const production = source('../src/views/manage/production/ProductionPage.vue')
const fillDetails = source('../src/views/manage/fill-details/FillDetailsPage.vue')
const energy = source('../src/views/energy/EnergyCenter.vue')
const alerts = source('../src/views/manage/alerts/AlertsPage.vue')
const workshopDashboard = source('../src/views/manage/workshop-dashboard/WorkshopDashboardPage.vue')
const systemSettings = source('../src/views/manage/admin/SystemSettingsPage.vue')
const tokens = source('../src/design/xt-tokens.css')
const hud = source('../src/design/xt-hud.css')
const industrial = source('../src/design/industrial.css')
const entryShell = source('../src/layout/EntryShell.vue')

const CORE_PAGES = [
  ['live', live],
  ['today', today],
  ['production', production],
]

const SECONDARY_PAGES = [
  ['fill-details', fillDetails],
  ['energy', energy],
  ['alerts', alerts],
  ['workshop-dashboard', workshopDashboard],
]

test('second pass core management pages declare the same visual pass and data-source strip', () => {
  for (const [name, src] of CORE_PAGES) {
    assert.match(src, /data-visual-pass="stitch-image2-second-pass"/, `${name} missing second-pass marker`)
    assert.match(src, /data-testid="second-pass-source-strip"/, `${name} missing source strip`)
    assert.match(src, /MES 外部数据/, `${name} missing MES source label`)
    assert.match(src, /人工填报/, `${name} missing manual source label`)
    assert.match(src, /算法数据/, `${name} missing algorithm source label`)
  }
})

test('second pass secondary management pages keep the same visual pass and source contract', () => {
  for (const [name, src] of SECONDARY_PAGES) {
    assert.match(src, /data-visual-pass="stitch-image2-second-pass"/, `${name} missing second-pass marker`)
    assert.match(src, /data-testid="second-pass-source-strip"/, `${name} missing source strip`)
    assert.match(src, /MES 外部数据/, `${name} missing MES source label`)
    assert.match(src, /人工填报/, `${name} missing manual source label`)
    assert.match(src, /算法数据/, `${name} missing algorithm source label`)
  }
})

test('system settings exposes the thirteen-workshop and MES mapping cockpit in the same visual language', () => {
  assert.match(systemSettings, /data-visual-pass="stitch-image2-second-pass"/)
  assert.match(systemSettings, /data-testid="second-pass-source-strip"/)
  assert.match(systemSettings, /MES 外部数据/)
  assert.match(systemSettings, /人工填报/)
  assert.match(systemSettings, /算法数据/)
  assert.match(systemSettings, /十三车间/)
  assert.match(systemSettings, /别名映射/)
  assert.match(systemSettings, /机列台账/)
  assert.match(systemSettings, /PC 工艺映射/)
  assert.match(systemSettings, /数据源状态/)
  assert.doesNotMatch(systemSettings, />ENV:/)
  assert.doesNotMatch(systemSettings, />ACTIVE</)
  assert.doesNotMatch(systemSettings, />ONLINE</)
  assert.doesNotMatch(systemSettings, /MASTER_DATA|ALIAS_SYNC|RULE_ENGINE|USER_RBAC|QR_SERVICE|AI_ASSIST/)
})

test('second pass visual system exposes shared industrial blue surface tokens', () => {
  for (const token of [
    '--xt-command-blue-canvas',
    '--xt-command-blue-panel',
    '--xt-command-blue-line',
    '--xt-command-blue-cyan',
    '--xt-command-blue-green',
    '--xt-command-blue-amber',
  ]) {
    assert.match(tokens, new RegExp(`${token}:`), `missing ${token}`)
  }

  assert.match(hud, /--xt-hud-source-strip-bg:/)
  assert.match(hud, /--xt-hud-source-strip-border:/)
  assert.match(hud, /\.xt-second-pass-source-strip/)
  assert.match(hud, /\.xt-second-pass-source-strip__item/)
  assert.match(industrial, /\.xt-second-pass-source-strip/)
  assert.match(industrial, /\.xt-second-pass-source-strip__item/)
})

test('mobile entry shell prefers stable field readability over decorative infinite sweep effects', () => {
  assert.doesNotMatch(entryShell, /xtEntryScan/)
  assert.doesNotMatch(entryShell, /xtEntryButtonSweep/)
  assert.doesNotMatch(entryShell, /animation:\s*[^;{}]*(infinite|linear infinite|ease-in-out infinite)/)
  assert.match(entryShell, /overflow-wrap:\s*anywhere/)
  assert.match(entryShell, /word-break:\s*break-word/)
  assert.match(entryShell, /touch-action:\s*manipulation/)
})
