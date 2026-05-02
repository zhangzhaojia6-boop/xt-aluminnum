import test from 'node:test'
import assert from 'node:assert/strict'

import { buildFlowPayload, resolveFlowFieldState, validateFlowSelection } from '../src/utils/coilFlowFields.js'

test('buildFlowPayload maps external MES flow data into extra payload flow', () => {
  const payload = buildFlowPayload({
    source: 'mes_projection',
    previous_workshop: '热轧',
    previous_process: '热轧出口',
    current_workshop: '冷轧',
    current_process: '轧制',
    next_workshop: '精整',
    next_process: '剪切',
    confirmed_at: '2026-05-02T08:30:00+08:00'
  })

  assert.deepEqual(payload.extra_payload.flow, {
    previous_workshop: '热轧',
    previous_process: '热轧出口',
    current_workshop: '冷轧',
    current_process: '轧制',
    next_workshop: '精整',
    next_process: '剪切',
    flow_source: 'mes_projection',
    flow_confirmed_at: '2026-05-02T08:30:00+08:00'
  })
})

test('missing external next process requires manual destination', () => {
  assert.equal(
    validateFlowSelection({
      source: 'mes_projection',
      current_workshop: '冷轧',
      current_process: '轧制',
      next_workshop: '',
      next_process: ''
    }),
    '请填写下道车间和工序'
  )
})

test('external route data locks previous current and next fields by default', () => {
  const state = resolveFlowFieldState({
    source: 'mes_projection',
    previous_process: '热轧出口',
    current_process: '轧制',
    next_process: '剪切'
  })

  assert.equal(state.previous.locked, true)
  assert.equal(state.current.locked, true)
  assert.equal(state.next.locked, true)
})

test('manual route source is marked pending MES match', () => {
  const payload = buildFlowPayload({
    source: 'manual',
    current_workshop: '冷轧',
    current_process: '轧制',
    next_workshop: '精整',
    next_process: '剪切'
  })

  assert.equal(payload.extra_payload.flow.flow_source, 'manual_pending_match')
})
