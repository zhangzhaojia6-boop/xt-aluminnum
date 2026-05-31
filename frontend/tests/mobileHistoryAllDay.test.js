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
