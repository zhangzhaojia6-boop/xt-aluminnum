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
  assert.doesNotMatch(reconciliationCenterSource, /已确认业务口径/)
  assert.doesNotMatch(reconciliationCenterSource, /当前无需处理/)
  assert.doesNotMatch(reconciliationCenterSource, /correctReconciliationItem\(row\.id,\s*value\)/)
})
