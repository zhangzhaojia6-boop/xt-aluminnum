import test from 'node:test'
import assert from 'node:assert/strict'

import {
  normalizeDailyFactAlerts,
  normalizeLiveMissingReports,
  normalizeMesFillGaps,
} from '../src/components/manage/_alertEventNormalize.js'
import { buildLiveMachineMatrix } from '../src/utils/liveDashboardPhase2.js'

test('MES gaps that only say local reporting is absent are retired, a weight mismatch stays', () => {
  const events = normalizeMesFillGaps({
    items: [
      { status: 'missing_local_entry', batch_no: 'a' },
      { status: 'mes_batch_unmapped', batch_no: 'b' },
      { status: 'local_entry_unassigned', batch_no: 'c' },
      { status: 'weight_mismatch', batch_no: 'd' },
    ],
  }, '2026-11-08')

  assert.equal(events.length, 1)
  assert.match(events[0].summary, /重量不一致/)
})

test('unfilled machine cells are no longer an alert, unfilled owner roles still are', () => {
  const events = normalizeLiveMissingReports({
    overall_progress: { missing_cell_count: 153 },
    owner_daily_status: { items: [{ role_label: '总电工', person_name: '王电工', status: 'not_started' }] },
  }, '2026-11-08')

  assert.equal(events.length, 1)
  assert.match(events[0].summary, /总电工/)
})

test('missing facts owned by machine operators leave the queue, other owners and conflicts stay', () => {
  const events = normalizeDailyFactAlerts({
    fact_missing: [
      { field: 'hot_roll_daily', owner_role: 'machine_operator' },
      { field: 'total_electricity_kwh', owner_role: 'energy_chief' },
    ],
    fact_conflicts: [{ field: 'daily_yield_rate', owner_role: 'machine_operator' }],
  }, '2026-11-08')

  assert.deepEqual(events.map((event) => event.id).sort(), [
    'fact-conflict:daily_yield_rate',
    'fact-missing:total_electricity_kwh',
  ])
})

test('a machine is not flagged because nobody filled it in', () => {
  const notStarted = [{ shift_id: 1, shift_name: '长白班', submission_status: 'not_started', status_tone: 'danger' }]
  const matrix = buildLiveMachineMatrix([{
    workshop_id: 1,
    workshop_name: '2050冷轧',
    machines: [
      { machine_id: 1, machine_name: 'A', day_total: { input: 10, output: 9 }, shifts: notStarted },
      { machine_id: 2, machine_name: 'B', day_total: { input: 0, output: 0 }, shifts: notStarted },
    ],
  }])
  const tones = Object.fromEntries(matrix.workshops[0].machines.map((machine) => [machine.machineName, machine.tone]))

  assert.deepEqual(tones, { A: 'success', B: 'muted' })
})

test('unfilled owner alerts never show the raw status code', () => {
  const events = normalizeLiveMissingReports({
    owner_daily_status: { items: [{ role_label: '内勤', status: 'not_started' }] },
  }, '2026-11-08')

  assert.equal(events[0].detail, '待提交')
})
