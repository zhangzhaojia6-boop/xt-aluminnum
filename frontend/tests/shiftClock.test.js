import test from 'node:test'
import assert from 'node:assert/strict'

import { inferShift, inferBusinessDate, inferLastCompletedBusinessDate, isShiftMismatch } from '../src/utils/shiftClock.js'

function shanghaiInstant(year, month, day, hour, minute) {
  const utc = Date.UTC(year, month - 1, day, hour - 8, minute)
  return new Date(utc)
}

test('shiftClock: 07:30 falls into A 长白班', () => {
  const now = shanghaiInstant(2026, 5, 26, 7, 30)
  assert.equal(inferShift(now).code, 'A')
})

test('shiftClock: 15:29 still A 长白班', () => {
  const now = shanghaiInstant(2026, 5, 26, 15, 29)
  assert.equal(inferShift(now).code, 'A')
})

test('shiftClock: 15:30 enters B 小夜', () => {
  const now = shanghaiInstant(2026, 5, 26, 15, 30)
  assert.equal(inferShift(now).code, 'B')
  assert.equal(inferShift(now).name, '小夜班')
})

test('shiftClock: 23:29 still B 小夜', () => {
  const now = shanghaiInstant(2026, 5, 26, 23, 29)
  assert.equal(inferShift(now).code, 'B')
})

test('shiftClock: 23:30 enters C 大夜', () => {
  const now = shanghaiInstant(2026, 5, 26, 23, 30)
  assert.equal(inferShift(now).code, 'C')
  assert.equal(inferShift(now).name, '大夜班')
})

test('shiftClock: 02:30 still C 大夜', () => {
  const now = shanghaiInstant(2026, 5, 27, 2, 30)
  assert.equal(inferShift(now).code, 'C')
})

test('shiftClock: 07:29 still C 大夜', () => {
  const now = shanghaiInstant(2026, 5, 27, 7, 29)
  assert.equal(inferShift(now).code, 'C')
})

test('shiftClock: business date starts at the 07:30 anchor', () => {
  const before = shanghaiInstant(2026, 5, 26, 7, 29)
  assert.equal(inferBusinessDate(before), '2026-05-25')
  const after = shanghaiInstant(2026, 5, 26, 7, 30)
  assert.equal(inferBusinessDate(after), '2026-05-26')
})

test('shiftClock: business date for 02:30 dawn = active business day', () => {
  const dawn = shanghaiInstant(2026, 5, 27, 2, 30)
  assert.equal(inferBusinessDate(dawn), '2026-05-26')
})

test('shiftClock: last completed business date changes at 07:30', () => {
  assert.equal(inferLastCompletedBusinessDate(shanghaiInstant(2026, 5, 27, 7, 29)), '2026-05-25')
  assert.equal(inferLastCompletedBusinessDate(shanghaiInstant(2026, 5, 27, 7, 30)), '2026-05-26')
  assert.equal(inferLastCompletedBusinessDate(shanghaiInstant(2026, 5, 27, 23, 30)), '2026-05-26')
})

test('shiftClock: mismatch detection ignores empty / non-ABC codes', () => {
  const now = shanghaiInstant(2026, 5, 26, 10, 0)
  assert.equal(isShiftMismatch('', now), false)
  assert.equal(isShiftMismatch(null, now), false)
  assert.equal(isShiftMismatch('long_day', now), false)
})

test('shiftClock: mismatch flags B during A window', () => {
  const morning = shanghaiInstant(2026, 5, 26, 10, 0)
  assert.equal(isShiftMismatch('A', morning), false)
  assert.equal(isShiftMismatch('B', morning), true)
  assert.equal(isShiftMismatch('C', morning), true)
})
