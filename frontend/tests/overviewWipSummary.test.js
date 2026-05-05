import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import { buildOverviewWipSummary } from '../src/utils/overviewWipSummary.js'

const overviewCenterSource = readFileSync(
  new URL('../src/views/review/OverviewCenter.vue', import.meta.url),
  'utf8',
)

test('buildOverviewWipSummary renders MES projection values and source state', () => {
  const summary = buildOverviewWipSummary({
    source: 'mes_projection',
    wip_tons: 12.345,
    today_output_tons: 6,
    freshness: { status: 'fresh', lag_seconds: 42 },
  })

  assert.equal(summary.wipTotalTonLabel, '12.35 t')
  assert.equal(summary.dailyOutputTonLabel, '6 t')
  assert.equal(summary.sourceLabel, 'MES 投影')
  assert.equal(summary.sourceTone, 'success')
})

test('buildOverviewWipSummary marks local fallback data without sample tonnage', () => {
  const summary = buildOverviewWipSummary({
    source: 'local_shift_data',
    wip_tons: 3,
    today_output_tons: 2,
    freshness: { status: 'fresh' },
  })

  assert.equal(summary.wipTotalTonLabel, '3 t')
  assert.equal(summary.dailyOutputTonLabel, '2 t')
  assert.equal(summary.sourceLabel, '本地填报')
  assert.equal(summary.sourceTone, 'warning')
})

test('buildOverviewWipSummary hides values when WIP source is unavailable', () => {
  const summary = buildOverviewWipSummary({
    source: 'unavailable',
    freshness: { status: 'failed' },
  })

  assert.equal(summary.wipTotalTonLabel, '--')
  assert.equal(summary.dailyOutputTonLabel, '--')
  assert.equal(summary.sourceLabel, '同步失败')
  assert.equal(summary.sourceTone, 'danger')
})

test('OverviewCenter uses live factory command data instead of WIP mock', () => {
  assert.match(overviewCenterSource, /fetchFactoryCommandOverview/)
  assert.match(overviewCenterSource, /buildOverviewWipSummary/)
  assert.doesNotMatch(overviewCenterSource, /mesWipSnapshotMock/)
  assert.doesNotMatch(overviewCenterSource, /source-badge is-fallback">fallback/)
})
