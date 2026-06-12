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

test('mobile api exposes MES pending supplement endpoint', () => {
  assert.match(mobileApiSource, /fetchMesPendingSupplements/)
  assert.match(mobileApiSource, /\/mobile\/mes-pending-supplements/)
})

test('MES pending supplements are optional and never trigger auth logout', () => {
  assert.match(mobileApiSource, /fetchMesPendingSupplements/)
  assert.match(mobileApiSource, /skipAuthLogout:\s*true/)
  assert.match(mobileApiSource, /skipErrorToast:\s*true/)
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
    return { data: { source: 'coil_snapshot', header_fields: { tracking_card_no: 'TRACK-BROWSER-1' }, lock_keys: [], lock_token: null } }
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

test('coil entry workbench applies scanned fields without locking them', () => {
  assert.match(coilEntrySource, /scanLookup/)
  assert.match(coilEntrySource, /扫码带出/)
  assert.match(coilEntrySource, /MES_ASSISTED_SCAN_FIELDS/)
  for (const field of ['tracking_card_no', 'alloy_grade', 'input_spec', 'output_spec', 'input_weight', 'output_weight', 'on_machine_time', 'off_machine_time', 'material_state']) {
    assert.match(coilEntrySource, new RegExp(`['"]${field}['"]`))
  }
  assert.match(coilEntrySource, /for \(const key of MES_ASSISTED_SCAN_FIELDS\)/)
  assert.match(coilEntrySource, /lockedFieldsSnapshot/)
  assert.match(coilEntrySource, /lockedFieldsToken/)
  assert.doesNotMatch(coilEntrySource, /applyLockedSnapshot\(result\?\.lock_keys/)
  assert.match(coilEntrySource, /lockedFieldsSnapshot\.value = \{\}\s+lockedFieldsToken\.value = ''/)
  assert.match(coilEntrySource, /MES 参考值/)
  assert.match(coilEntrySource, /人工填报值可改/)
  assert.match(coilEntrySource, /mesReferenceRows/)
  assert.match(coilEntrySource, /on_machine_time: form\.value\.on_machine_time/)
  assert.match(coilEntrySource, /off_machine_time: form\.value\.off_machine_time/)
  assert.match(coilEntrySource, /material_state: form\.value\.material_state/)
  assert.match(coilEntrySource, /locked_fields_snapshot/)
  assert.match(coilEntrySource, /locked_fields_token/)
})

test('coil entry workbench lets operators pick MES pending supplements', () => {
  assert.match(coilEntrySource, /fetchMesPendingSupplements/)
  assert.match(coilEntrySource, /MES 待补录/)
  assert.match(coilEntrySource, /正常先点上方 MES 待补录卡片/)
  assert.match(coilEntrySource, /找不到卷材？扫码带出/)
  assert.match(coilEntrySource, /手工补录一卷/)
  assert.match(coilEntrySource, /当前机台暂无 MES 待补录卷材/)
  assert.match(coilEntrySource, /data-testid="mes-pending-supplements"/)
  assert.match(coilEntrySource, /data-testid="mes-pending-card"/)
  assert.match(coilEntrySource, /data-testid="mes-entry-focus"/)
  assert.match(coilEntrySource, /data-testid="coil-quality-module"/)
  assert.match(coilEntrySource, /MES 待补录确认/)
  assert.match(coilEntrySource, /MES 已带入/)
  assert.match(coilEntrySource, /核对机台和现场补录项即可/)
  assert.match(coilEntrySource, /applyMesPendingItem/)
  assert.match(coilEntrySource, /activeMesPendingItem/)
  assert.match(coilEntrySource, /isMesPendingMode/)
  assert.match(coilEntrySource, /entryDialogTitle/)
  assert.match(coilEntrySource, /openManualEntryDialog/)
  assert.match(coilEntrySource, /buildMesPendingHeaderFields/)
  assert.match(coilEntrySource, /pendingBadges/)
  assert.match(coilEntrySource, /pendingProcessText/)
  assert.match(coilEntrySource, /pendingMachineText/)
  assert.match(coilEntrySource, /pendingSpecText/)
  assert.match(coilEntrySource, /pendingMaterialText/)
  assert.match(coilEntrySource, /coil-mes-card__facts/)
  assert.match(coilEntrySource, /上机/)
  assert.match(coilEntrySource, /下机/)
  assert.match(coilEntrySource, /类型/)
  assert.match(coilEntrySource, /pendingPassLabel/)
  assert.match(coilEntrySource, /typeof sequence === 'string'/)
  assert.match(coilEntrySource, /sequence\?\.pass_label/)
  assert.match(coilEntrySource, /material_category === 'cold_roll_pass'/)
  assert.match(coilEntrySource, /hot_roll_process: '热轧坯料'/)
  assert.match(coilEntrySource, /cast_roll_process: '铸轧坯料'/)
  assert.match(coilEntrySource, /machine_match_status === 'matched'/)
  assert.match(coilEntrySource, /machine_match_status === 'unmatched'/)
  assert.match(coilEntrySource, /machine_match_needs_confirmation/)
  assert.match(coilEntrySource, /机台已匹配/)
  assert.match(coilEntrySource, /机台待确认/)
  assert.match(coilEntrySource, /mes_reference/)
  assert.match(coilEntrySource, /process_record_id: item\.mes_process_record_id/)
  assert.match(coilEntrySource, /source_id: item\.mes_source_id/)
  assert.match(coilEntrySource, /material_code: item\.material_code/)
  assert.match(coilEntrySource, /mes_worker_name: item\.mes_worker_name/)
  assert.match(coilEntrySource, /人工值仍可修改/)
  assert.match(coilEntrySource, /machine_binding_confidence: item\.machine_binding_confidence/)
  assert.match(coilEntrySource, /mes_end_time: item\.end_time/)
  assert.match(coilEntrySource, /mes_last_seen_at: item\.mes_last_seen_at/)
  assert.match(coilEntrySource, /material_reference: item\.material_reference/)
  assert.match(coilEntrySource, /process_sequence: item\.process_sequence/)
  assert.match(coilEntrySource, /quality\.has_issue/)
  assert.match(coilEntrySource, /v-if="quality\.has_issue"/)
  assert.match(coilEntrySource, /buildQualityPayload/)
  assert.match(coilEntrySource, /quality_issue/)
  assert.match(coilEntrySource, /resetQuality/)
  assert.match(coilEntrySource, /business_day_start \|\| '09:30'/)
  assert.match(coilEntrySource, /const flowPayload = buildFlowPayload\(form\.value\.flow\)/)
  assert.match(coilEntrySource, /const qualityPayload = buildQualityPayload\(\)/)
  assert.match(coilEntrySource, /\.\.\.\(form\.value\.extra_payload \|\| \{\}\)/)
  assert.match(coilEntrySource, /\.\.\.\(flowPayload\.extra_payload \|\| \{\}\)/)
  assert.match(coilEntrySource, /extra_payload: Object\.keys\(extraPayload\)\.length \? extraPayload : null/)
  assert.doesNotMatch(coilEntrySource, /fetchMesPendingSupplements\(\{[^)]*business_date/)
})

test('unified entry form keeps scanned per-coil fields editable', () => {
  assert.match(unifiedEntrySource, /scanLookup/)
  assert.match(unifiedEntrySource, /扫码带出/)
  assert.match(unifiedEntrySource, /MES_ASSISTED_SCAN_FIELDS/)
  for (const field of ['tracking_card_no', 'alloy_grade', 'input_spec', 'output_spec', 'input_weight', 'output_weight', 'on_machine_time', 'off_machine_time', 'material_state']) {
    assert.match(unifiedEntrySource, new RegExp(`['"]${field}['"]`))
  }
  assert.match(unifiedEntrySource, /for \(const key of MES_ASSISTED_SCAN_FIELDS\)/)
  assert.match(unifiedEntrySource, /lockedFieldsSnapshot/)
  assert.match(unifiedEntrySource, /lockedFieldsToken/)
  assert.doesNotMatch(unifiedEntrySource, /applyLockedSnapshot\(result\?\.lock_keys/)
  assert.match(unifiedEntrySource, /locked_fields_snapshot/)
  assert.match(unifiedEntrySource, /locked_fields_token/)
  assert.match(unifiedEntrySource, /lockedFieldsSnapshot\.value = \{\}\s+lockedFieldsToken\.value = ''/)
  assert.match(unifiedEntrySource, /MES 参考值/)
  assert.match(unifiedEntrySource, /人工填报值可改/)
  assert.match(unifiedEntrySource, /mesReferenceRows/)
})

test('unified entry form maps casting output and spec fields into canonical payload', () => {
  assert.match(unifiedEntrySource, /values\.output_weight \?\? values\.unit_output/)
  assert.match(unifiedEntrySource, /input_spec: values\.input_spec \|\| values\.ingot_spec \|\| null/)
  assert.match(unifiedEntrySource, /appendTemplateExtraFields\(extra, values\)/)
  assert.match(unifiedEntrySource, /material_state: values\.material_state \|\| null/)
  assert.match(unifiedEntrySource, /spool_weight: values\.spool_weight/)
  assert.match(unifiedEntrySource, /trim_weight: values\.trim_weight/)
  assert.match(unifiedEntrySource, /tray_weight: values\.tray_weight/)
})
