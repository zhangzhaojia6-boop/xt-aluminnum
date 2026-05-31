import { test } from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

const pagePath = path.resolve('src/views/attendance/AttendanceOverview.vue')
const apiPath = path.resolve('src/api/attendance.js')
const src = fs.readFileSync(pagePath, 'utf8')
const apiSrc = fs.readFileSync(apiPath, 'utf8')

test('AttendanceOverview keeps the real attendance result and process paths', () => {
  assert.match(src, /fetchAttendanceResults/)
  assert.match(src, /processAttendance/)
  assert.match(src, /business_date:\s*businessDate\.value/)
  assert.match(src, /start_date:\s*businessDate\.value,\s*end_date:\s*businessDate\.value/)
  assert.match(apiSrc, /api\.get\(['"]\/attendance\/results['"]/)
  assert.match(apiSrc, /api\.post\(['"]\/attendance\/process['"]/)
})

test('AttendanceOverview keeps all management table fields visible', () => {
  for (const field of [
    'employee_no',
    'employee_name',
    'attendance_status',
    'check_in_time',
    'check_out_time',
    'late_minutes',
    'early_leave_minutes',
    'data_status'
  ]) {
    assert.match(src, new RegExp(field))
  }

  for (const label of ['工号', '姓名', '状态', '上班打卡', '下班打卡', '迟到\\(分\\)', '早退\\(分\\)', '数据状态', '详情']) {
    assert.match(src, new RegExp(label))
  }
})

test('AttendanceOverview keeps summary, status, and detail behavior', () => {
  for (const key of ['total', 'normal', 'abnormal', 'pending_review']) {
    assert.match(src, new RegExp(key))
  }
  assert.match(src, /ReferenceStatusTag/)
  assert.match(src, /formatStatusLabel/)
  assert.match(src, /formatFlowStatus/)
  assert.match(src, /statusTone/)
  assert.match(src, /name:\s*'attendance-detail'/)
})

test('AttendanceOverview uses the industrial blue responsive surface', () => {
  assert.match(src, /data-testid="attendance-overview-page"/)
  assert.match(src, /data-testid="attendance-overview-stats"/)
  assert.match(src, /data-testid="attendance-overview-table"/)
  assert.match(src, /data-testid="attendance-overview-mobile-list"/)
  assert.match(src, /ATTENDANCE COMMAND/)
  assert.match(src, /--attendance-cyan:\s*#00f2ff/)
  assert.match(src, /attendanceCommandSweep/)
  assert.match(src, /attendanceCommandPulse/)
  assert.match(src, /@media \(max-width: 720px\)/)
})

test('AttendanceOverview does not add forbidden product wording', () => {
  assert.doesNotMatch(src, /cyberpunk|quantum|sci-?fi/i)
})
