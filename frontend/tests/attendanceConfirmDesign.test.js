import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const src = readFileSync(new URL('../src/views/mobile/AttendanceConfirm.vue', import.meta.url), 'utf8')

test('AttendanceConfirm keeps the real attendance confirmation data path', () => {
  for (const token of [
    'fetchCurrentShift',
    'fetchEquipment',
    'fetchAttendanceDraft',
    'submitAttendanceConfirmation',
    'enqueuePendingRequest',
    'isWithinSubmitCooldown',
    "url: '/attendance/confirm'",
  ]) {
    assert.match(src, new RegExp(token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
  }
})

test('AttendanceConfirm keeps the mobile role flow and removes canceled foreman wording', () => {
  assert.match(src, /data-testid="attendance-confirm"/)
  assert.match(src, /现场负责人/)
  assert.match(src, /差异原因/)
  assert.match(src, /提交确认/)
  assert.doesNotMatch(src, /班长/)
})

test('AttendanceConfirm uses industrial blue motion without changing business fields', () => {
  for (const token of [
    'attendance-radar',
    'ATTENDANCE RADAR',
    'SHIFT SIGNAL',
    'CONTROL BAY',
    'PERSONNEL TRACE',
    'attendanceStateTone',
    'anomalyCount',
    'attendanceSeq(index)',
    'attendanceToneClass(row)',
    '#00f2ff',
    'attendanceRadarScan',
    'attendanceRadarLed',
    'attendanceRadarCardIn',
    'prefers-reduced-motion',
  ]) {
    assert.match(src, new RegExp(token.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')))
  }
  assert.doesNotMatch(src, /purple|violet|lavender/i)
})
