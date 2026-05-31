import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const src = readFileSync(new URL('../src/views/mobile/OCRCapture.vue', import.meta.url), 'utf8')
const apiSrc = readFileSync(new URL('../src/api/mobile.js', import.meta.url), 'utf8')

test('OCRCapture keeps the real OCR and template data path', () => {
  assert.match(src, /fetchCurrentShift/)
  assert.match(src, /fetchWorkshopTemplate/)
  assert.match(src, /extractOcrFields/)
  assert.match(src, /enqueuePendingRequest/)
  assert.match(apiSrc, /api\.post\(\s*['"]\/ocr\/extract['"]/)
  assert.match(apiSrc, /formData\.append\(['"]workshop_type['"]/)
  assert.match(apiSrc, /formData\.append\(['"]file['"]/)
})

test('OCRCapture preserves capture, cooldown, storage and route handoff behavior', () => {
  assert.match(src, /ref="fileInput"/)
  assert.match(src, /accept="image\/\*"/)
  assert.match(src, /capture="environment"/)
  assert.match(src, /@change="handleFileChange"/)
  assert.match(src, /isWithinSubmitCooldown/)
  assert.match(src, /SUBMIT_COOLDOWN_MS/)
  assert.match(src, /sessionStorage\.setItem/)
  assert.match(src, /ocr_submission_id/)
  assert.match(src, /name: 'mobile-report-form'/)
})

test('OCRCapture does not treat numeric zero as an unrecognized field', () => {
  assert.match(src, /function hasDisplayValue\(value\)/)
  assert.match(src, /value !== null && value !== undefined && value !== ''/)
  assert.match(src, /displayFieldValue\(item\.value\)/)
  assert.doesNotMatch(src, /item\.value \|\| '未识别'/)
})

test('OCRCapture exposes all production OCR states in the UI', () => {
  assert.match(src, /正在加载车间模板/)
  assert.match(src, /当前班次未识别到车间模板/)
  assert.match(src, /当前车间模板未开启拍照识别/)
  assert.match(src, /template\?\.supports_ocr/)
  assert.match(src, /statusLabel/)
  assert.match(src, /shiftReadouts/)
  assert.match(src, /confidenceStats/)
})

test('OCRCapture uses the Stitch industrial blue machine-vision surface', () => {
  for (const token of [
    'data-testid="mobile-ocr-capture"',
    'ocr-vision',
    'OCR VISION',
    'SHIFT SIGNAL',
    'SCAN BAY',
    'RESULT MATRIX',
    'Teleport to="body"',
    '#00f2ff',
    'ocrVisionSweep',
    'ocrVisionScanline',
    'ocrVisionLed',
    'ocrVisionCardIn',
    'ocrVisionButtonSweep',
    'prefers-reduced-motion',
    'bottom: calc(var(--xt-tabbar-height) + 14px + env(safe-area-inset-bottom, 0px))',
    'z-index: 120',
    'pointer-events: auto',
  ]) {
    assert.match(src, new RegExp(token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
  }
  assert.doesNotMatch(src, /purple|violet|lavender/i)
})

test('OCRCapture keeps confidence colors aligned with business thresholds', () => {
  assert.match(src, /if \(confidence >= 0\.85\) return 'good'/)
  assert.match(src, /if \(confidence >= 0\.6\) return 'warn'/)
  assert.match(src, /return 'danger'/)
  assert.match(src, /\.ocr-vision__badge\.is-good/)
  assert.match(src, /\.ocr-vision__badge\.is-warn/)
  assert.match(src, /\.ocr-vision__badge\.is-danger/)
})
