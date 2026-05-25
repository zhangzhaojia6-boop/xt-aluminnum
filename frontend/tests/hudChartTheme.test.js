import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

function source(relativePath) {
  return readFileSync(new URL(relativePath, import.meta.url), 'utf8')
}

test('useHudChartTheme observes data-xt-theme and returns xt-hud theme name', () => {
  const src = source('../src/composables/useHudChartTheme.js')
  assert.match(src, /registerHudEchartsTheme/)
  assert.match(src, /XT_HUD_THEME_NAME/)
  assert.match(src, /MutationObserver/)
  assert.match(src, /attributeFilter:\s*\['data-xt-theme'\]/)
})

test('shared chart components pass HUD theme to VChart', () => {
  for (const file of [
    '../src/components/xt/XtBarChart.vue',
    '../src/components/xt/XtLineChart.vue',
    '../src/components/xt/XtGaugeChart.vue',
    '../src/components/manage/WorkshopBarChart.vue'
  ]) {
    const src = source(file)
    assert.match(src, /useHudChartTheme/)
    assert.match(src, /:theme="chartTheme"/)
  }
})
