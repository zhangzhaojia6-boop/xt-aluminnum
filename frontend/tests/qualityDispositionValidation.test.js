import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  hasQualityDispositionNote,
  normalizeQualityDispositionNote,
} from '../src/utils/qualityDispositionValidation.js'

const qualityCenterSource = readFileSync(
  new URL('../src/views/quality/QualityCenter.vue', import.meta.url),
  'utf8',
)

test('hasQualityDispositionNote rejects blank disposition notes', () => {
  assert.equal(hasQualityDispositionNote(''), false)
  assert.equal(hasQualityDispositionNote('   '), false)
  assert.equal(hasQualityDispositionNote(null), false)
  assert.equal(hasQualityDispositionNote(' 已复核完成 '), true)
})

test('normalizeQualityDispositionNote trims operator notes', () => {
  assert.equal(normalizeQualityDispositionNote(' 已复核完成 '), '已复核完成')
  assert.equal(normalizeQualityDispositionNote(null), '')
})

test('QualityCenter validates and submits normalized disposition notes', () => {
  assert.match(qualityCenterSource, /qualityDispositionValidation/)
  assert.match(qualityCenterSource, /inputValidator:\s*hasQualityDispositionNote/)
  assert.match(qualityCenterSource, /normalizeQualityDispositionNote\(value\)/)
  assert.doesNotMatch(qualityCenterSource, /resolveQualityIssue\(row\.id,\s*value\)/)
  assert.doesNotMatch(qualityCenterSource, /ignoreQualityIssue\(row\.id,\s*value\)/)
})
