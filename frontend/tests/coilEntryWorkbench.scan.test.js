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
  assert.match(scanLookupSource, /new globalThis\.window\.BarcodeDetector/)
  assert.match(scanLookupSource, /\.detect\(/)
  assert.match(scanLookupSource, /const canScan = computed\(\(\) => Boolean\(dingtalkScanner\(\)\) \|\| hasBrowserDetector\(\)\)/)
  assert.doesNotMatch(scanLookupSource, /throw new Error\('browser_scanner_unavailable'\)/)
})

test('scan lookup composable runs browser barcode detector path', async () => {
  let stopped = false
  let detected = false
  const originalWindow = globalThis.window
  const originalDocument = globalThis.document
  const originalNavigator = globalThis.navigator

  const { api } = await import('../src/api/index.js')
  const originalGet = api.get

  Object.defineProperty(globalThis, 'window', {
    configurable: true,
    value: {
      BarcodeDetector: class {
        async detect() {
          detected = true
          return [{ rawValue: 'QR-BROWSER-1' }]
        }
      }
    }
  })
  Object.defineProperty(globalThis, 'document', {
    configurable: true,
    value: {
      createElement() {
        return {
          muted: false,
          playsInline: false,
          srcObject: null,
          async play() {}
        }
      }
    }
  })
  Object.defineProperty(globalThis, 'navigator', {
    configurable: true,
    value: {
      mediaDevices: {
        async getUserMedia() {
          return { getTracks: () => [{ stop() { stopped = true } }] }
        }
      }
    }
  })
  api.get = async (path, config) => {
    assert.equal(path, '/mobile/scan-lookup')
    assert.equal(config.params.qr, 'QR-BROWSER-1')
    return { data: { source: 'coil_snapshot', header_fields: { tracking_card_no: 'TRACK-BROWSER-1' }, lock_keys: [], lock_token: 'token' } }
  }

  try {
    const { useScanLookup } = await import('../src/composables/useScanLookup.js')
    const lookup = useScanLookup()
    assert.equal(lookup.canScan.value, true)
    const result = await lookup.scanLookup()
    assert.equal(result.header_fields.tracking_card_no, 'TRACK-BROWSER-1')
    assert.equal(detected, true)
    assert.equal(stopped, true)
  } finally {
    api.get = originalGet
    Object.defineProperty(globalThis, 'window', { configurable: true, value: originalWindow })
    Object.defineProperty(globalThis, 'document', { configurable: true, value: originalDocument })
    Object.defineProperty(globalThis, 'navigator', { configurable: true, value: originalNavigator })
  }
})

test('coil entry workbench applies scanned fields and locked snapshot', () => {
  assert.match(coilEntrySource, /scanLookup/)
  assert.match(coilEntrySource, /扫码带出/)
  assert.match(coilEntrySource, /lockedFieldsSnapshot/)
  assert.match(coilEntrySource, /lockedFieldsToken/)
  assert.match(coilEntrySource, /:disabled="isLockedField\('tracking_card_no'\)"/)
  assert.match(coilEntrySource, /locked_fields_snapshot/)
  assert.match(coilEntrySource, /locked_fields_token/)
})

test('unified entry form keeps scanned per-coil fields readonly', () => {
  assert.match(unifiedEntrySource, /scanLookup/)
  assert.match(unifiedEntrySource, /lockedFieldsSnapshot/)
  assert.match(unifiedEntrySource, /lockedFieldsToken/)
  assert.match(unifiedEntrySource, /isLockedField\(field\.name\)/)
  assert.match(unifiedEntrySource, /locked_fields_snapshot/)
  assert.match(unifiedEntrySource, /locked_fields_token/)
  assert.match(unifiedEntrySource, /lockedFieldsSnapshot\.value = \{\}\s+lockedFieldsToken\.value = ''/)
})

test('unified entry form maps casting output and spec fields into canonical payload', () => {
  assert.match(unifiedEntrySource, /values\.output_weight \?\? values\.unit_output/)
  assert.match(unifiedEntrySource, /input_spec: values\.input_spec \|\| values\.ingot_spec \|\| null/)
  assert.match(unifiedEntrySource, /appendTemplateExtraFields\(extra, values\)/)
  assert.match(unifiedEntrySource, /material_state: values\.material_state \|\| null/)
  assert.match(unifiedEntrySource, /spool_weight: values\.spool_weight/)
})
