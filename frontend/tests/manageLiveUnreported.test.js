import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildLiveMachineMatrix,
  buildLiveProcessFlowItems,
  buildLiveTickerItems,
} from '../src/utils/liveDashboardPhase2.js'

const unreportedMachine = {
  machine_id: 1,
  machine_name: '1#机',
  day_total: { input: 0, output: 0, scrap: 0 },
  shifts: [
    { shift_id: 1, shift_name: '长白班', submission_status: 'not_started', status_tone: 'danger' },
    { shift_id: 2, shift_name: '大夜班', submission_status: 'not_applicable' },
  ],
}
const runningMachine = {
  machine_id: 2,
  machine_name: '2#机',
  day_total: { input: 10, output: 9, scrap: 1 },
  shifts: [{ shift_id: 1, shift_name: '长白班', submission_status: 'not_started', status_tone: 'danger' }],
}
const submittedZeroMachine = {
  machine_id: 3,
  machine_name: '3#机',
  day_total: { input: 0, output: 0, scrap: 0 },
  shifts: [{ shift_id: 1, shift_name: '长白班', submission_status: 'all_submitted' }],
}

test('a machine with zero totals and no submitted shift is unreported, not zero', () => {
  const matrix = buildLiveMachineMatrix([
    { workshop_id: 1, workshop_name: '铸轧二', machines: [unreportedMachine] },
    { workshop_id: 2, workshop_name: '2050冷轧', machines: [runningMachine, submittedZeroMachine] },
  ])
  const [cast, cold] = matrix.workshops

  assert.equal(cast.machines[0].unreported, true)
  assert.equal(cast.unreported, true)
  assert.equal(cold.unreported, false)
  assert.equal(cold.machines.find((machine) => machine.machineName === '2#机').unreported, false)
  assert.equal(cold.machines.find((machine) => machine.machineName === '3#机').unreported, false)
})

test('process flow shows a stage with only unreported machines as missing', () => {
  const items = buildLiveProcessFlowItems({
    workshops: [
      { workshop_id: 1, workshop_name: '铸轧二', machines: [unreportedMachine] },
      { workshop_id: 2, workshop_name: '2050冷轧', machines: [runningMachine, submittedZeroMachine] },
    ],
  })

  assert.equal(items.find((item) => item.stage === '铸轧').hasTrustedOutput, false)
  assert.equal(items.find((item) => item.stage === '冷轧').output, 9)
})

test('ticker does not count unfilled shifts a second time as anomalies', () => {
  const items = buildLiveTickerItems({
    overall_progress: { missing_cell_count: 153, attention_cell_count: 156 },
  })

  assert.equal(items.some((item) => item.label === '未填'), false)
  assert.equal(items.find((item) => item.label === '异常').value, '3')
})
