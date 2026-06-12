import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const src = readFileSync(new URL('../src/views/mobile/ShiftReportHistory.vue', import.meta.url), 'utf8')

test('ShiftReportHistory defaults to full business day history', () => {
  assert.match(src, /inferBusinessDate/)
  assert.match(src, /const businessDate = ref\(inferBusinessDate\(\)\)/)
  assert.match(src, /fetchMobileHistory\(\{\s*business_date: businessDate\.value,\s*all_day: true,\s*limit: 30,/)
})

test('ShiftReportHistory gives operators a date-level history control', () => {
  assert.match(src, /<el-date-picker/)
  assert.match(src, /value-format="YYYY-MM-DD"/)
  assert.match(src, /@change="load"/)
  assert.match(src, /按整日查看有权限的录入记录/)
})

test('ShiftReportHistory renders machine operator all-day coil entries', () => {
  assert.match(src, /historyItemKey\(item\)/)
  assert.match(src, /item\?\.source_type === 'mobile_coil'/)
  assert.match(src, /item\.tracking_card_no/)
  assert.match(src, /item\.input_weight/)
  assert.match(src, /item\.scrap_weight/)
  assert.match(src, /主操逐卷/)
  assert.match(src, /录入人：/)
})

test('ShiftReportHistory keeps the all-day record contract visible in the UI', () => {
  assert.match(src, /data-testid="entry-history-page"/)
  assert.match(src, /data-testid="entry-history-record"/)
  assert.match(src, /整日记录/)
  assert.match(src, /记录时间线/)
  assert.match(src, /visibleCountLabel/)
  assert.match(src, /historySeq\(index\)/)
  assert.match(src, /historyToneClass\(item\)/)
})

test('ShiftReportHistory uses the stable industrial blue mobile surface', () => {
  assert.match(src, /#00f2ff/)
  assert.match(src, /data-visual-pass="stitch-image2-second-pass-mobile"/)
  assert.doesNotMatch(src, /animation:\s*[^;{}]*(infinite|linear infinite|ease-in-out infinite)/)
  assert.doesNotMatch(src, /historyLog(Scan|Orbit|Led)/)
  assert.match(src, /overflow-wrap:\s*anywhere/)
  assert.match(src, /touch-action:\s*manipulation/)
  assert.doesNotMatch(src, /#[a-fA-F0-9]{0,2}8b5cf6|purple|violet|lavender/i)
})

test('ShiftReportHistory protects mobile header from narrow date controls', () => {
  assert.match(src, /\.mobile-top\s*\{\s*grid-template-columns:\s*minmax\(0,\s*1fr\)/)
  assert.match(src, /\.header-actions\s*\{[\s\S]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s+auto/)
  assert.match(src, /@media \(max-width:\s*480px\)/)
  assert.match(src, /\.mobile-inline-action\s*\{[\s\S]*min-height:\s*44px/)
})
