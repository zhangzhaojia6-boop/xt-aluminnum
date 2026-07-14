import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const SRC = readFileSync(new URL('../src/views/manage/alerts/AlertsPage.vue', import.meta.url), 'utf8')

test('AlertsPage keeps the alert timeline business wiring', () => {
  assert.match(SRC, /useAlertsTimeline/)
  assert.match(SRC, /SURFACE_TO_DOMAIN\s*=\s*\{\s*anomaly:\s*'production'/)
  assert.match(SRC, /timeline\.setDomains\(readDomainsFromRoute\(\)\)/)
  assert.match(SRC, /syncRouteFromDomains/)
  assert.match(SRC, /timeline\.load\(\)/)
})

test('AlertsPage keeps existing timeline components and counts', () => {
  assert.match(SRC, /DateSwitcher/)
  assert.match(SRC, /DomainFilterChips/)
  assert.match(SRC, /EventTimeline/)
  assert.match(SRC, /openCount/)
  assert.match(SRC, /businessEvents\.value\.length/)
})

test('AlertsPage applies industrial blue command surface without hard-coded hex', () => {
  assert.match(SRC, /data-testid="manage-alerts-stats"/)
  assert.match(SRC, /data-testid="manage-alerts-filters"/)
  assert.match(SRC, /异常总览/)
  assert.match(SRC, /异常清单/)
  assert.doesNotMatch(SRC, /xtAlertsSweep/)
  assert.doesNotMatch(SRC, /xtAlertsPulse/)
  assert.doesNotMatch(SRC, /animation:\s*[^;]*infinite/)
  assert.doesNotMatch(SRC, /backdrop-filter|filter:\s*blur/i)
  const style = SRC.split('<style')[1] || ''
  assert.equal(/#[0-9a-fA-F]{3,6}/.test(style), false)
  assert.match(style, /var\(--xt-primary\)/)
})
