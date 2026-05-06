import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const importHistorySource = readFileSync(
  new URL('../src/views/imports/ImportHistory.vue', import.meta.url),
  'utf8',
)
const importsApiSource = readFileSync(
  new URL('../src/api/imports.js', import.meta.url),
  'utf8',
)

test('import history renders daily production mapping gate preview', () => {
  assert.match(importsApiSource, /fetchDailyProductionMappingPreview/)
  assert.match(importsApiSource, /\/imports\/daily-production\/mapping-preview/)
  assert.match(importHistorySource, /fetchDailyProductionMappingPreview/)
  assert.match(importHistorySource, /class="mapping-gate"/)
  assert.match(importHistorySource, /每日产量/)
  assert.match(importHistorySource, /映射门禁/)
  assert.match(importHistorySource, /mappingPreview\.ready_rows/)
  assert.match(importHistorySource, /mappingPreview\.needs_equipment_mapping_rows/)
  assert.match(importHistorySource, /mappingPreview\.unresolved_rows/)
  assert.match(importHistorySource, /preview\.total_rows/)
  assert.match(importHistorySource, /unresolvedMappingLabels/)
  assert.match(importHistorySource, /candidate_workshops/)
  assert.match(importHistorySource, /candidate_equipment/)
  assert.match(importHistorySource, /candidateSummary/)
  assert.match(importHistorySource, /车间/)
  assert.match(importHistorySource, /机列/)
})
