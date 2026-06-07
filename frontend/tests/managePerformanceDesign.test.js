import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const ROOT = path.resolve('src')

const CRITICAL_MANAGE_SURFACES = [
  'layout/ManageShell.vue',
  'views/manage/live/LiveDashboardPage.vue',
  'views/manage/live/LiveMarketTicker.vue',
  'views/manage/live/LiveMachineCard.vue',
  'views/manage/live/LiveMachineMatrix.vue',
  'views/manage/live/LiveEventRail.vue',
  'views/manage/live/LiveMetricCompareCard.vue',
  'views/manage/live/LiveDataStatePanel.vue',
  'views/manage/live/LiveMachineDrawer.vue',
  'views/manage/today/TodayPage.vue',
  'views/manage/production/ProductionPage.vue',
  'views/energy/EnergyCenter.vue',
  'views/manage/fill-details/FillDetailsPage.vue',
  'views/manage/alerts/AlertsPage.vue',
  'views/manage/admin/SystemSettingsPage.vue',
  'components/xt/XtCameraGuide.vue',
  'components/manage/DateSwitcher.vue',
  'components/manage/FactorySourceStrip.vue',
  'components/manage/KpiBar.vue',
  'components/manage/IndustrialProcessIcon.vue',
  'components/manage/MissingReportPanel.vue',
  'components/manage/SummaryHero.vue',
  'components/manage/OutputTrendLine.vue',
  'components/manage/WorkshopBarChart.vue',
  'components/manage/CostLine.vue',
]

function read(rel) {
  return fs.readFileSync(path.join(ROOT, rel), 'utf8')
}

test('critical management surfaces do not ship infinite decorative light effects', () => {
  for (const rel of CRITICAL_MANAGE_SURFACES) {
    const src = read(rel)
    assert.doesNotMatch(src, /animation:\s*[^;{}]*(infinite|linear infinite|ease-in-out infinite)/, `${rel} has an infinite decorative animation`)
    assert.doesNotMatch(src, /@keyframes\s+[^\s{]*(Sweep|Pulse|Scan|EnergyLine|Glow)/i, `${rel} keeps a decorative keyframe`)
  }
})

test('critical management surfaces avoid blur filters and oversized glow shadows', () => {
  for (const rel of CRITICAL_MANAGE_SURFACES) {
    const src = read(rel)
    assert.doesNotMatch(src, /backdrop-filter|filter:\s*blur/i, `${rel} uses a runtime blur effect`)
    assert.doesNotMatch(src, /text-shadow\s*:/i, `${rel} uses glowing text instead of clear typography`)
    assert.doesNotMatch(src, /box-shadow:\s*0\s+0\s+(1[6-9]|[2-9]\d)px/i, `${rel} uses an oversized glow shadow`)
    assert.doesNotMatch(src, /0\s+(1[8-9]|[2-9]\d)px\s+(3[6-9]|[4-9]\d)px/i, `${rel} uses an oversized soft shadow`)
  }
})

test('critical management surfaces keep industrial structure after light-effect reduction', () => {
  const shell = read('layout/ManageShell.vue')
  const today = read('views/manage/today/TodayPage.vue')
  const stitch = read('utils/stitchManageSurface.js')
  const strip = read('components/manage/FactorySourceStrip.vue')
  const kpi = read('components/manage/KpiBar.vue')
  const missing = read('components/manage/MissingReportPanel.vue')

  assert.match(shell, /data-testid="manage-shell"/)
  assert.match(shell, /xt-manage--today-wall/)
  assert.match(shell, /xt-manage--dashboard-wall/)
  assert.match(shell, /DASHBOARD_WALL_PATHS/)
  assert.match(today, /data-testid="today-command-wall"/)
  assert.match(today, /data-testid="today-production-flow"/)
  assert.match(today, /data-testid="today-event-rail"/)
  assert.match(today, /:data-stitch-screen-id="stitchSurface\.stitch\.screenId"/)
  assert.match(today, /IndustrialProcessIcon/)
  assert.match(stitch, /d9646f7499664e2b988ff67670cc6214/)
  assert.match(stitch, /707c0acd1b3e4873a38973141ee5ff89/)
  assert.match(stitch, /3a7288d183ed48609f2f851097ded0cb/)
  assert.match(stitch, /23626a62189043148d752492349fbcab/)
  assert.match(stitch, /425e659eeb834f648f18039a38868034/)
  assert.match(strip, /data-testid="factory-source-strip"/)
  assert.match(strip, /xt-source-strip__rail/)
  assert.match(kpi, /data-testid="manage-kpi-bar"/)
  assert.match(missing, /data-testid="missing-report-panel"/)
})

test('core interactive components keep visible keyboard focus and button semantics', () => {
  const search = read('components/xt/XtSearch.vue')
  const section = read('components/xt/XtSectionCard.vue')

  assert.doesNotMatch(search, /outline:\s*none/)
  assert.match(search, /\.xt-search__input:focus-visible\s*\{[\s\S]*?outline:/)
  assert.match(search, /\.xt-search__item:focus-visible\s*\{[\s\S]*?outline:/)

  assert.match(section, /type="button"/)
  assert.match(section, /:aria-expanded="!collapsed"/)
  assert.match(section, /:aria-label="collapsed \? '展开区块' : '收起区块'"/)
  assert.match(section, /@click\.stop="toggle"/)
})
