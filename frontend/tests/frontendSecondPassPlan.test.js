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
const tokens = source('../src/design/xt-tokens.css')
const hud = source('../src/design/xt-hud.css')
const industrial = source('../src/design/industrial.css')
const entryShell = source('../src/layout/EntryShell.vue')

const CORE_PAGES = [
  ['live', live],
  ['production', production],
]

const SECONDARY_PAGES = [
  ['fill-details', fillDetails],
  ['energy', energy],
  ['workshop-dashboard', workshopDashboard],
]

test('second pass core management pages declare the same visual pass and data-source strip', () => {
  for (const [name, src] of CORE_PAGES) {
    assert.match(src, /data-visual-pass="stitch-image2-second-pass"/, `${name} missing second-pass marker`)
  }
  assert.match(today, /data-visual-pass="light-workspace"/)
  // 这三个固定标签不随数据变化；这些页面的数字旁已有真实来源，不再显示。
  for (const [name, src] of [['today', today], ['live', live], ['production', production]]) {
    assert.doesNotMatch(src, /data-testid="second-pass-source-strip"/, `${name} shows static source labels`)
    assert.doesNotMatch(src, />MES 外部数据</, `${name} shows static MES label`)
    assert.doesNotMatch(src, />人工填报</, `${name} shows static manual label`)
    assert.doesNotMatch(src, />算法数据</, `${name} shows static algorithm label`)
  }
})

test('second pass secondary management pages keep the same visual pass and source contract', () => {
  for (const [name, src] of SECONDARY_PAGES) {
    assert.match(src, /data-visual-pass="stitch-image2-second-pass"/, `${name} missing second-pass marker`)
    assert.doesNotMatch(src, /second-pass-source-strip/, `${name} shows static source labels`)
    assert.doesNotMatch(src, />MES 外部数据</, `${name} shows static MES label`)
  }
  assert.match(alerts, /data-visual-pass="stitch-image2-second-pass"/)
  assert.doesNotMatch(alerts, /data-testid="second-pass-source-strip"/)
  assert.doesNotMatch(alerts, />MES 外部数据</)
  assert.doesNotMatch(alerts, />人工填报</)
  assert.doesNotMatch(alerts, />算法数据</)
})

test('dark command surface tokens stay removed after the paper redesign', () => {
  for (const token of [
    '--xt-command-blue-canvas',
    '--xt-command-blue-panel',
    '--xt-command-blue-line',
    '--xt-command-blue-cyan',
    '--xt-command-blue-green',
    '--xt-command-blue-amber',
  ]) {
    assert.doesNotMatch(tokens, new RegExp(`${token}:`), `unexpected ${token}`)
  }

  assert.doesNotMatch(hud, /xt-second-pass-source-strip|--xt-hud-source-strip/)
  assert.doesNotMatch(industrial, /xt-second-pass-source-strip/)
})

test('mobile entry shell prefers stable field readability over decorative infinite sweep effects', () => {
  assert.doesNotMatch(entryShell, /xtEntryScan/)
  assert.doesNotMatch(entryShell, /xtEntryButtonSweep/)
  assert.doesNotMatch(entryShell, /animation:\s*[^;{}]*(infinite|linear infinite|ease-in-out infinite)/)
  assert.match(entryShell, /overflow-wrap:\s*anywhere/)
  assert.match(entryShell, /word-break:\s*break-word/)
  assert.match(entryShell, /touch-action:\s*manipulation/)
})
