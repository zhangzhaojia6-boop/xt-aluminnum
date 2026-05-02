import test from 'node:test'
import assert from 'node:assert/strict'

import { validateCoilEntryForm } from '../src/utils/coilEntryValidation.js'

test('validateCoilEntryForm requires tracking card number', () => {
  assert.equal(
    validateCoilEntryForm({ tracking_card_no: '', input_weight: 100, output_weight: 96 }),
    '请填写卷号'
  )
})

test('validateCoilEntryForm requires both input and output weight', () => {
  assert.equal(
    validateCoilEntryForm({ tracking_card_no: 'RA-001', input_weight: 100, output_weight: null }),
    '请填写投入和产出重量'
  )
})

test('validateCoilEntryForm rejects zero and negative weights', () => {
  assert.equal(
    validateCoilEntryForm({ tracking_card_no: 'RA-001', input_weight: 0, output_weight: 96 }),
    '投入重量必须大于 0'
  )
  assert.equal(
    validateCoilEntryForm({ tracking_card_no: 'RA-001', input_weight: 100, output_weight: -1 }),
    '产出重量必须大于 0'
  )
})

test('validateCoilEntryForm rejects output greater than input', () => {
  assert.equal(
    validateCoilEntryForm({ tracking_card_no: 'RA-001', input_weight: 90, output_weight: 96 }),
    '产出重量不能大于投入重量'
  )
})

test('validateCoilEntryForm accepts valid coil weights', () => {
  assert.equal(
    validateCoilEntryForm({ tracking_card_no: 'RA-001', input_weight: 100, output_weight: 96 }),
    null
  )
})

test('validateCoilEntryForm requires manual destination when flow has no next process', () => {
  assert.equal(
    validateCoilEntryForm({
      tracking_card_no: 'RA-001',
      input_weight: 100,
      output_weight: 96,
      flow: {
        flow_source: 'mes_projection',
        current_workshop: '冷轧',
        current_process: '轧制',
        next_workshop: '',
        next_process: ''
      }
    }),
    '请填写下道车间和工序'
  )
})
