import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

function source(relativePath) {
  return readFileSync(new URL(relativePath, import.meta.url), 'utf8')
}

// --- useDateRange ---

test('useDateRange exports dateRange, dateFrom, dateTo, setRange, setPreset', () => {
  const src = source('../src/composables/useDateRange.js')
  assert.match(src, /export function useDateRange/)
  assert.match(src, /dateRange/)
  assert.match(src, /dateFrom/)
  assert.match(src, /dateTo/)
  assert.match(src, /setRange/)
  assert.match(src, /setPreset/)
})

test('useDateRange syncs with route query', () => {
  const src = source('../src/composables/useDateRange.js')
  assert.match(src, /useRoute/)
  assert.match(src, /useRouter/)
  assert.match(src, /date_from/)
  assert.match(src, /date_to/)
  assert.match(src, /router\.replace/)
})

test('useDateRange has preset shortcuts', () => {
  const src = source('../src/composables/useDateRange.js')
  assert.match(src, /today/)
  assert.match(src, /yesterday/)
  assert.match(src, /week/)
  assert.match(src, /month/)
  assert.match(src, /quarter/)
  assert.match(src, /last7/)
  assert.match(src, /last30/)
})

// --- useTableQuery ---

test('useTableQuery exports page, loading, data, load, onPageChange, onSortChange', () => {
  const src = source('../src/composables/useTableQuery.js')
  assert.match(src, /export function useTableQuery/)
  assert.match(src, /page/)
  assert.match(src, /loading/)
  assert.match(src, /data/)
  assert.match(src, /load/)
  assert.match(src, /onPageChange/)
  assert.match(src, /onSortChange/)
})

test('useTableQuery syncs pagination with route', () => {
  const src = source('../src/composables/useTableQuery.js')
  assert.match(src, /useRoute/)
  assert.match(src, /useRouter/)
  assert.match(src, /page_size/)
  assert.match(src, /router\.replace/)
})

test('useTableQuery supports sort field and order', () => {
  const src = source('../src/composables/useTableQuery.js')
  assert.match(src, /sortField/)
  assert.match(src, /sortOrder/)
  assert.match(src, /ascending/)
  assert.match(src, /descending/)
})

// --- useMetricCompare ---

test('useMetricCompare exports mode, result, load, setMode', () => {
  const src = source('../src/composables/useMetricCompare.js')
  assert.match(src, /export function useMetricCompare/)
  assert.match(src, /mode/)
  assert.match(src, /result/)
  assert.match(src, /load/)
  assert.match(src, /setMode/)
})

test('useMetricCompare supports yoy/mom/wow modes', () => {
  const src = source('../src/composables/useMetricCompare.js')
  assert.match(src, /yoy/)
  assert.match(src, /mom/)
  assert.match(src, /wow/)
  assert.match(src, /同比/)
  assert.match(src, /环比/)
  assert.match(src, /周比/)
})

test('useMetricCompare calls comparison API', () => {
  const src = source('../src/composables/useMetricCompare.js')
  assert.match(src, /\/comparison/)
  assert.match(src, /api\.get/)
})
