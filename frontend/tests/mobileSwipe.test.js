import assert from 'node:assert/strict'
import test from 'node:test'

import { clampSwipeOffset, resolveSwipeSnapIndex } from '../src/utils/mobileSwipe.js'

test('resolveSwipeSnapIndex snaps to next page when drag crosses threshold', () => {
  assert.equal(resolveSwipeSnapIndex({ currentIndex: 0, deltaX: -140, pageWidth: 320, pageCount: 4 }), 1)
})

test('resolveSwipeSnapIndex keeps current page when drag is too short', () => {
  assert.equal(resolveSwipeSnapIndex({ currentIndex: 1, deltaX: -30, pageWidth: 320, pageCount: 4 }), 1)
})

test('clampSwipeOffset applies damped edge resistance', () => {
  assert.equal(clampSwipeOffset({ offset: 40, min: -640, max: 0 }), 16)
})
