import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  hasReconciliationDispositionNote,
  normalizeReconciliationDispositionNote,
} from '../src/utils/reconciliationDispositionValidation.js'
import {
  formatReconciliationDiffValue,
  formatReconciliationDimension,
  formatReconciliationFieldLabel,
  formatReconciliationSourceLabel,
  formatReconciliationValue,
  parseReconciliationDimension,
} from '../src/utils/reconciliationDisplay.js'

const reconciliationDetailSource = readFileSync(
  new URL('../src/views/reconciliation/ReconciliationDetail.vue', import.meta.url),
  'utf8',
)

test('hasReconciliationDispositionNote rejects blank disposition notes', () => {
  assert.equal(hasReconciliationDispositionNote(''), false)
  assert.equal(hasReconciliationDispositionNote('   '), false)
  assert.equal(hasReconciliationDispositionNote(null), false)
  assert.equal(hasReconciliationDispositionNote(' 已核对业务口径 '), true)
})

test('normalizeReconciliationDispositionNote trims operator notes', () => {
  assert.equal(normalizeReconciliationDispositionNote(' 已核对业务口径 '), '已核对业务口径')
  assert.equal(normalizeReconciliationDispositionNote(null), '')
})

test('reconciliation display helpers keep fill and external MES labels consistent', () => {
  assert.equal(formatReconciliationSourceLabel('production'), '填报端产量')
  assert.equal(formatReconciliationSourceLabel('shift_production_data'), '填报端产量')
  assert.equal(formatReconciliationSourceLabel('mes'), '外部 MES')
  assert.equal(formatReconciliationSourceLabel('mes_export'), '外部 MES')
  assert.equal(formatReconciliationFieldLabel('output_weight'), '产出重量')
  assert.equal(formatReconciliationDimension('workshop:铸三车间|shift:小夜|machine:2#机'), '车间 铸三车间 / 班次 小夜 / 机列 2#机')
  assert.deepEqual(parseReconciliationDimension('workshop:铸三车间|shift:小夜'), {
    workshop: '铸三车间',
    shift: '小夜',
  })
  assert.equal(formatReconciliationValue('1175', '产出重量'), '1175 吨')
  assert.equal(formatReconciliationDiffValue({ diff_value: 15, field_name: '产出重量' }), '+15 吨')
  assert.equal(formatReconciliationDiffValue({ diff_value: -3.5, field_name: 'headcount' }), '-3.5 人')
})

test('ReconciliationDetail renders business labels and units for source values', () => {
  assert.match(reconciliationDetailSource, /formatReconciliationSourceLabel\(item\.value\?\.source_a\)/)
  assert.match(reconciliationDetailSource, /formatReconciliationSourceLabel\(item\.value\?\.source_b\)/)
  assert.match(reconciliationDetailSource, /formatReconciliationValue\(item\.value\?\.source_a_value,\s*item\.value\?\.field_name\)/)
  assert.match(reconciliationDetailSource, /formatReconciliationValue\(item\.value\?\.source_b_value,\s*item\.value\?\.field_name\)/)
  assert.match(reconciliationDetailSource, /formatReconciliationDiffValue\(item\.value\)/)
  assert.match(reconciliationDetailSource, /formatReconciliationFieldLabel\(item\.value\?\.field_name\)/)
  assert.match(reconciliationDetailSource, /formatReconciliationDimension\(item\.value\?\.dimension_key\)/)
  assert.match(reconciliationDetailSource, /reconciliationDisplay/)
  assert.doesNotMatch(reconciliationDetailSource, /production:\s*'填报端产量'/)
  assert.doesNotMatch(reconciliationDetailSource, /mes:\s*'外部 MES'/)
  assert.doesNotMatch(reconciliationDetailSource, /formatSourceTypeLabel/)
  assert.doesNotMatch(reconciliationDetailSource, /来源 A/)
  assert.doesNotMatch(reconciliationDetailSource, /MES 系统/)
})
