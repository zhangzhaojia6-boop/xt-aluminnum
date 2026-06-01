import test from 'node:test'
import assert from 'node:assert/strict'

import { validateEntryWeights } from '../src/utils/entryWeightValidation.js'

test('validateEntryWeights rejects negative visible weight values', () => {
  const fields = [{ name: 'input_weight', label: '投入重量', type: 'number' }]
  assert.equal(
    validateEntryWeights({ input_weight: -1 }, fields),
    '投入重量不能为负数'
  )
})

test('validateEntryWeights rejects output greater than input', () => {
  const fields = [
    { name: 'input_weight', label: '投入重量', type: 'number' },
    { name: 'output_weight', label: '产出重量', type: 'number' },
  ]
  assert.equal(
    validateEntryWeights({ input_weight: 90, output_weight: 96 }, fields),
    '产出重量不能大于投入重量'
  )
})

test('validateEntryWeights rejects output plus scrap greater than input when scrap is visible', () => {
  const fields = [
    { name: 'input_weight', label: '投入重量', type: 'number' },
    { name: 'output_weight', label: '产出重量', type: 'number' },
    { name: 'scrap_weight', label: '废料重量', type: 'number' },
  ]
  assert.equal(
    validateEntryWeights({ input_weight: 100, output_weight: 96, scrap_weight: 8 }, fields),
    '产出重量和废料重量合计不能大于投入重量'
  )
})

test('validateEntryWeights rejects scrap greater than input even when output is not visible', () => {
  const fields = [
    { name: 'input_weight', label: '投入铝锭', type: 'number' },
    { name: 'scrap_weight', label: '废料', type: 'number' },
  ]
  assert.equal(
    validateEntryWeights({ input_weight: 2400, scrap_weight: 4000 }, fields),
    '废料重量不能大于投入重量'
  )
})

test('validateEntryWeights treats casting unit_output as output weight', () => {
  const fields = [
    { name: 'input_weight', label: '投入铝锭', type: 'number' },
    { name: 'unit_output', label: '单机产量', type: 'number' },
    { name: 'scrap_weight', label: '废料', type: 'number' },
  ]
  assert.equal(
    validateEntryWeights({ input_weight: 100, unit_output: 96, scrap_weight: 8 }, fields),
    '产出重量和废料重量合计不能大于投入重量'
  )
})

test('validateEntryWeights accepts empty optional weights and valid material balance', () => {
  const fields = [
    { name: 'input_weight', label: '投入重量', type: 'number' },
    { name: 'output_weight', label: '产出重量', type: 'number' },
    { name: 'scrap_weight', label: '废料重量', type: 'number' },
  ]
  assert.equal(validateEntryWeights({ input_weight: '', output_weight: null }, fields), null)
  assert.equal(validateEntryWeights({ input_weight: 100, output_weight: 96, scrap_weight: 4 }, fields), null)
})

test('validateEntryWeights tolerates decimal precision in material balance', () => {
  const fields = [
    { name: 'input_weight', label: '投入重量', type: 'number' },
    { name: 'output_weight', label: '产出重量', type: 'number' },
    { name: 'scrap_weight', label: '废料重量', type: 'number' },
  ]
  assert.equal(validateEntryWeights({ input_weight: 0.3, output_weight: 0.1, scrap_weight: 0.2 }, fields), null)
})
