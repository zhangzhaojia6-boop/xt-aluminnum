import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const src = readFileSync(new URL('../src/layout/EntryShell.vue', import.meta.url), 'utf8')
const mobileEntrySrc = readFileSync(new URL('../src/views/mobile/MobileEntry.vue', import.meta.url), 'utf8')
const unifiedEntrySrc = readFileSync(new URL('../src/views/mobile/UnifiedEntryForm.vue', import.meta.url), 'utf8')
const attendanceSrc = readFileSync(new URL('../src/views/mobile/AttendanceConfirm.vue', import.meta.url), 'utf8')
const consumableSrc = readFileSync(new URL('../src/views/mobile/ConsumableEntry.vue', import.meta.url), 'utf8')

test('EntryShell bottom navigation points operators to active fill and all-day history pages', () => {
  assert.match(src, /path: '\/entry\/fill', label: '录入'/)
  assert.match(src, /path: '\/entry\/history', label: '历史'/)
  assert.doesNotMatch(src, /path: '\/entry\/report', label: '录入'/)
  assert.doesNotMatch(src, /path: '\/entry\/profile', label: '我的'/)
})

test('EntryShell applies the cyber industrial mobile visual shell without changing routes', () => {
  assert.match(src, /--entry-cyan:\s*#00f2ff/)
  assert.match(src, /radial-gradient\(circle at 18% 0%/)
  assert.match(src, /\.xt-entry :deep\(\.mobile-shell\)/)
  assert.match(src, /@keyframes xtEntryScan/)
  assert.match(src, /\.xt-entry :deep\(\.mobile-history-item\)/)
  assert.match(src, /\.xt-entry :deep\(\.mobile-attendance-card\)/)
  assert.match(src, /@keyframes xtEntryButtonSweep/)
})

test('mobile entry and unified form keep real controls while adopting industrial motion', () => {
  assert.match(mobileEntrySrc, /data-testid="mobile-go-report"/)
  assert.match(mobileEntrySrc, /07:30 起算/)
  assert.doesNotMatch(mobileEntrySrc, /23:30 起算/)
  assert.match(mobileEntrySrc, /@keyframes mobileEntryButtonSweep/)
  assert.match(unifiedEntrySrc, /fetchEntryFields/)
  assert.match(unifiedEntrySrc, /Array\.isArray\(coils\)\s*\?\s*coils\s*:\s*\[\]/)
  assert.match(unifiedEntrySrc, /@keyframes ueSubmitSweep/)
})

test('mobile auxiliary role pages keep APIs while sharing the industrial entry shell', () => {
  assert.match(attendanceSrc, /fetchAttendanceDraft/)
  assert.match(attendanceSrc, /submitAttendanceConfirmation/)
  assert.doesNotMatch(attendanceSrc, /班长/)
  assert.match(attendanceSrc, /现场负责人/)
  assert.match(consumableSrc, /fetchConsumableWorkshops/)
  assert.match(consumableSrc, /upsertDailyConsumableLog/)
  assert.match(consumableSrc, /rgba\(0,\s*242,\s*255,\s*0\.08\)/)
})
