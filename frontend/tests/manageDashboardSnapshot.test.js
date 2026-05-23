import test from 'node:test'
import assert from 'node:assert/strict'

test('useDashboardSnapshot defaults target_date to yesterday in YYYY-MM-DD', async () => {
  const fakeFetch = async (params) => {
    fakeFetch.lastParams = params
    return { target_date: params.target_date, leader_metrics: { total_output_weight: 10 } }
  }
  const mod = await import('../src/composables/useDashboardSnapshot.js')
  const snap = mod.createDashboardSnapshot({ fetchImpl: fakeFetch, now: new Date('2026-05-23T10:00:00Z') })
  await snap.load()
  assert.equal(fakeFetch.lastParams.target_date, '2026-05-22')
  assert.equal(snap.leaderMetrics.value.total_output_weight, 10)
})

test('useDashboardSnapshot stepDate(-1) goes one day back and reloads', async () => {
  const calls = []
  const fakeFetch = async (params) => { calls.push(params.target_date); return {} }
  const mod = await import('../src/composables/useDashboardSnapshot.js')
  const snap = mod.createDashboardSnapshot({ fetchImpl: fakeFetch, now: new Date('2026-05-23T10:00:00Z') })
  await snap.load()
  await snap.stepDate(-1)
  assert.deepEqual(calls, ['2026-05-22', '2026-05-21'])
})

test('useDashboardSnapshot freshness reads analysis_handoff.freshness.freshness_status', async () => {
  const fakeFetch = async () => ({ analysis_handoff: { freshness: { freshness_status: 'green' } } })
  const mod = await import('../src/composables/useDashboardSnapshot.js')
  const snap = mod.createDashboardSnapshot({ fetchImpl: fakeFetch, now: new Date('2026-05-23T10:00:00Z') })
  await snap.load()
  assert.equal(snap.freshnessStatus.value, 'green')
})
