import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/views/master/QRCodePrint.vue', import.meta.url), 'utf8')

test('QRCodePrint keeps the real QR data and print operations', () => {
  assert.match(source, /fetchEquipmentPage/)
  assert.match(source, /function fetchAllEquipment/)
  assert.match(source, /while \(items\.length < total\)/)
  assert.match(source, /fetchWorkshops/)
  assert.match(source, /QRCode\.toDataURL/)
  assert.match(source, /buildLoginUrl/)
  assert.match(source, /window\.print/)
  assert.match(source, /equipment_type === 'virtual_workshop_qr'/)
  assert.match(source, /主任看板码/)
  assert.match(source, /isDirectorQr/)
})

test('QRCodePrint uses the industrial QR matrix while preserving scan-safe output', () => {
  assert.match(source, /data-testid="qr-print-page"/)
  assert.match(source, /机台二维码清单/)
  assert.match(source, /qrSummary/)
  assert.match(source, /qr-print-card__qr/)
  assert.match(source, /background:\s*#fff/)
  assert.match(source, /@media print/)
  assert.match(source, /repeat\(auto-fit,\s*minmax\(170px,\s*1fr\)\)/)
  assert.doesNotMatch(source, /ReferencePageFrame/)
  assert.doesNotMatch(source, /reference-page/)
})
