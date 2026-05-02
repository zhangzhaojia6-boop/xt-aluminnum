import test from 'node:test'
import assert from 'node:assert/strict'

import { DEFAULT_ALLOY_GRADES, loadCoilEntryStartup } from '../src/utils/coilEntryStartup.js'

test('loadCoilEntryStartup keeps bootstrap usable when alloy options fail', async () => {
  const calls = []
  const result = await loadCoilEntryStartup({
    fetchMobileBootstrap: async () => {
      calls.push('bootstrap')
      return { workshop_name: '一车间' }
    },
    fetchCurrentShift: async () => {
      calls.push('shift')
      return { business_date: '2026-05-02', shift_id: 7 }
    },
    fetchFieldOptions: async (key) => {
      calls.push(key)
      throw new Error('config unavailable')
    },
  })

  assert.deepEqual(result.bootstrap, { workshop_name: '一车间' })
  assert.deepEqual(result.currentShift, { business_date: '2026-05-02', shift_id: 7 })
  assert.deepEqual(result.alloyGrades, DEFAULT_ALLOY_GRADES)
  assert.deepEqual(calls.sort(), ['alloy-grades', 'bootstrap', 'shift'])
})

test('loadCoilEntryStartup uses configured alloy options when available', async () => {
  const result = await loadCoilEntryStartup({
    fetchMobileBootstrap: async () => ({ workshop_name: '二车间' }),
    fetchCurrentShift: async () => ({ business_date: '2026-05-02', shift_id: 8 }),
    fetchFieldOptions: async () => [{ label: '6063', value: '6063' }],
  })

  assert.deepEqual(result.alloyGrades, [{ label: '6063', value: '6063' }])
})
