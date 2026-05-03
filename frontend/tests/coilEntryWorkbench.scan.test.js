import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const mobileApiSource = readFileSync(new URL('../src/api/mobile.js', import.meta.url), 'utf8')
const scanLookupSource = readFileSync(new URL('../src/composables/useScanLookup.js', import.meta.url), 'utf8')
const coilEntrySource = readFileSync(new URL('../src/views/mobile/CoilEntryWorkbench.vue', import.meta.url), 'utf8')
const unifiedEntrySource = readFileSync(new URL('../src/views/mobile/UnifiedEntryForm.vue', import.meta.url), 'utf8')

test('mobile api exposes scan lookup endpoint', () => {
  assert.match(mobileApiSource, /fetchScanLookup/)
  assert.match(mobileApiSource, /\/mobile\/scan-lookup/)
})

test('scan lookup composable supports dingtalk and browser scanners', () => {
  assert.match(scanLookupSource, /useScanLookup/)
  assert.match(scanLookupSource, /dd\.biz\.util\.scan/)
  assert.match(scanLookupSource, /BarcodeDetector/)
})

test('coil entry workbench applies scanned fields and locked snapshot', () => {
  assert.match(coilEntrySource, /scanLookup/)
  assert.match(coilEntrySource, /扫码带出/)
  assert.match(coilEntrySource, /lockedFieldsSnapshot/)
  assert.match(coilEntrySource, /:disabled="isLockedField\('tracking_card_no'\)"/)
  assert.match(coilEntrySource, /locked_fields_snapshot/)
})

test('unified entry form keeps scanned per-coil fields readonly', () => {
  assert.match(unifiedEntrySource, /scanLookup/)
  assert.match(unifiedEntrySource, /lockedFieldsSnapshot/)
  assert.match(unifiedEntrySource, /isLockedField\(field\.name\)/)
  assert.match(unifiedEntrySource, /locked_fields_snapshot/)
})
