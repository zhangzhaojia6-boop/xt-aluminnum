import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  hasReconciliationDispositionNote,
  normalizeReconciliationDispositionNote,
} from '../src/utils/reconciliationDispositionValidation.js'

const reconciliationCenterSource = readFileSync(
  new URL('../src/views/reconciliation/ReconciliationCenter.vue', import.meta.url),
  'utf8',
)
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

test('ReconciliationCenter prompts for normalized notes on every action', () => {
  assert.match(reconciliationCenterSource, /reconciliationDispositionValidation/)
  assert.match(reconciliationCenterSource, /useRoute/)
  assert.match(reconciliationCenterSource, /normalizeQueryFilter/)
  assert.match(reconciliationCenterSource, /route\.query\.business_date/)
  assert.match(reconciliationCenterSource, /route\.query\.status/)
  assert.match(reconciliationCenterSource, /inputValidator:\s*hasReconciliationDispositionNote/)
  assert.match(reconciliationCenterSource, /promptForReconciliationNote/)
  assert.match(reconciliationCenterSource, /confirmReconciliationItem\(row\.id,\s*note\)/)
  assert.match(reconciliationCenterSource, /ignoreReconciliationItem\(row\.id,\s*note\)/)
  assert.match(reconciliationCenterSource, /correctReconciliationItem\(row\.id,\s*note\)/)
  assert.match(reconciliationCenterSource, /formatReconciliationSourceLabel\(row\.source_a\)/)
  assert.match(reconciliationCenterSource, /formatReconciliationSourceLabel\(row\.source_b\)/)
  assert.match(reconciliationCenterSource, /formatReconciliationDiffValue\(row\)/)
  assert.match(reconciliationCenterSource, /buildDesktopPreservingQuery/)
  assert.match(reconciliationCenterSource, /route\.query\.desktop/)
  assert.match(
    reconciliationCenterSource,
    /router\.push\(\{\s*name:\s*'reconciliation-detail',\s*params:\s*\{\s*id\s*\},\s*query:\s*buildDesktopPreservingQuery\(\)/s,
  )
  assert.match(reconciliationCenterSource, /production:\s*'填报端产量'/)
  assert.match(reconciliationCenterSource, /mes:\s*'外部 MES'/)
  assert.doesNotMatch(reconciliationCenterSource, /已确认业务口径/)
  assert.doesNotMatch(reconciliationCenterSource, /当前无需处理/)
  assert.doesNotMatch(reconciliationCenterSource, /correctReconciliationItem\(row\.id,\s*value\)/)
})

test('ReconciliationDetail renders business labels and units for source values', () => {
  assert.match(reconciliationDetailSource, /formatReconciliationSourceLabel\(item\.value\?\.source_a\)/)
  assert.match(reconciliationDetailSource, /formatReconciliationSourceLabel\(item\.value\?\.source_b\)/)
  assert.match(reconciliationDetailSource, /formatReconciliationValue\(item\.value\?\.source_a_value,\s*item\.value\?\.field_name\)/)
  assert.match(reconciliationDetailSource, /formatReconciliationValue\(item\.value\?\.source_b_value,\s*item\.value\?\.field_name\)/)
  assert.match(reconciliationDetailSource, /formatReconciliationDiffValue\(item\.value\)/)
  assert.match(reconciliationDetailSource, /formatReconciliationFieldLabel\(item\.value\?\.field_name\)/)
  assert.match(reconciliationDetailSource, /formatReconciliationDimension\(item\.value\?\.dimension_key\)/)
  assert.match(reconciliationDetailSource, /production:\s*'填报端产量'/)
  assert.match(reconciliationDetailSource, /mes:\s*'外部 MES'/)
  assert.doesNotMatch(reconciliationDetailSource, /formatSourceTypeLabel/)
  assert.doesNotMatch(reconciliationDetailSource, /来源 A/)
  assert.doesNotMatch(reconciliationDetailSource, /MES 系统/)
})
