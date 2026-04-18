import test from 'node:test'
import assert from 'node:assert/strict'

import { SUBMIT_COOLDOWN_MS, isWithinSubmitCooldown, remainingSubmitCooldown } from '../src/utils/submitGuard.js'

test('isWithinSubmitCooldown blocks submits within the cooldown window', () => {
  assert.equal(isWithinSubmitCooldown(1_000, 1_000 + SUBMIT_COOLDOWN_MS - 1), true)
})

test('isWithinSubmitCooldown allows submits once the cooldown expires', () => {
  assert.equal(isWithinSubmitCooldown(1_000, 1_000 + SUBMIT_COOLDOWN_MS), false)
})

test('remainingSubmitCooldown reports the remaining lock time and clamps at zero', () => {
  assert.equal(remainingSubmitCooldown(5_000, 6_000), 2_000)
  assert.equal(remainingSubmitCooldown(5_000, 8_000), 0)
})
