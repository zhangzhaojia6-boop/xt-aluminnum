import test from 'node:test'
import assert from 'node:assert/strict'

import {
  buildDynamicDraftKey,
  findRestorableDraftKey
} from '../src/composables/useLocalDraft.js'
import { isRetryableNetworkError } from '../src/composables/useRetryQueue.js'

test('buildDynamicDraftKey includes workshop shift date machineId and tracking card', () => {
  assert.equal(
    buildDynamicDraftKey({
      workshopId: 2,
      shiftId: 3,
      businessDate: '2026-03-28',
      machineId: 37,
      trackingCardNo: 'ra260001'
    }),
    'draft:2:3:2026-03-28:37:RA260001'
  )
})

test('findRestorableDraftKey prefers exact match then latest prefix match', () => {
  const exact = findRestorableDraftKey(
    [
      { key: 'draft:2:3:2026-03-28:37:RA260001', savedAt: '2026-03-28T08:00:00.000Z' },
      { key: 'draft:2:3:2026-03-28:37:RA260002', savedAt: '2026-03-28T08:05:00.000Z' }
    ],
    {
      workshopId: 2,
      shiftId: 3,
      businessDate: '2026-03-28',
      machineId: 37,
      trackingCardNo: 'RA260001'
    }
  )
  const latestPrefix = findRestorableDraftKey(
    [
      { key: 'draft:2:3:2026-03-28:37:RA260001', savedAt: '2026-03-28T08:00:00.000Z' },
      { key: 'draft:2:3:2026-03-28:37:RA260002', savedAt: '2026-03-28T08:05:00.000Z' }
    ],
    {
      workshopId: 2,
      shiftId: 3,
      businessDate: '2026-03-28',
      machineId: 37,
      trackingCardNo: ''
    }
  )

  assert.equal(exact, 'draft:2:3:2026-03-28:37:RA260001')
  assert.equal(latestPrefix, 'draft:2:3:2026-03-28:37:RA260002')
})

test('isRetryableNetworkError only treats transport failures as retryable', () => {
  assert.equal(isRetryableNetworkError({ code: 'ERR_NETWORK' }), true)
  assert.equal(isRetryableNetworkError({ message: 'Network Error' }), true)
  assert.equal(isRetryableNetworkError({ response: { status: 400 } }), false)
  assert.equal(isRetryableNetworkError({ response: { status: 500 } }), false)
})
