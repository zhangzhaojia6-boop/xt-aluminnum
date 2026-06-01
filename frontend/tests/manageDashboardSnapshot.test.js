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

test('useDashboardSnapshot does not treat missing energy as zero', async () => {
  const fakeFetch = async () => ({ leader_summary: { metrics: { energy_per_ton: 0 } } })
  const fakeDailyFetch = async () => ({
    energy: { data_available: false },
    plant_output: { daily_output: 10, energy_per_ton: null }
  })
  const mod = await import('../src/composables/useDashboardSnapshot.js')
  const snap = mod.createDashboardSnapshot({
    fetchImpl: fakeFetch,
    fetchDailyImpl: fakeDailyFetch,
    now: new Date('2026-05-23T10:00:00Z')
  })
  await snap.load()
  assert.equal(snap.leaderMetrics.value.energy_per_ton, null)
})

test('useDashboardSnapshot falls back to factory command MES extended overview for management pages', async () => {
  const fakeFetch = async () => ({ leader_metrics: {} })
  const fakeDailyFetch = async () => ({})
  const fakeFactoryCommandFetch = async (params) => {
    fakeFactoryCommandFetch.lastParams = params
    return {
    source: 'mes_extended',
    freshness: { source: 'mes_extended', status: 'fresh', lag_seconds: 60 },
    wip_tons: 13.5,
    today_output_tons: 6.2,
    stock_tons: 8.5,
    total_input_tons: 20,
    total_output_tons: 18.5,
    yield_rate: 92.5,
    workshop_summary: [
      { workshop_name: '在线退火分厂', total_output_tons: 11.4, total_input_tons: 12, yield_rate: 95 },
      { workshop_name: '冷轧', total_output_tons: 7.1, total_input_tons: 8, yield_rate: 88.75 }
    ]
    }
  }
  const mod = await import('../src/composables/useDashboardSnapshot.js')
  const snap = mod.createDashboardSnapshot({
    fetchImpl: fakeFetch,
    fetchDailyImpl: fakeDailyFetch,
    fetchFactoryCommandImpl: fakeFactoryCommandFetch,
    now: new Date('2026-05-23T10:00:00Z')
  })

  await snap.load()

  assert.equal(snap.factoryCommandOverview.value.source, 'mes_extended')
  assert.equal(fakeFactoryCommandFetch.lastParams.target_date, '2026-05-22')
  assert.equal(snap.leaderMetrics.value.total_output_weight, 6.2)
  assert.equal(snap.leaderMetrics.value.today_total_output, 6.2)
  assert.equal(snap.leaderMetrics.value.yield_rate, 92.5)
  assert.equal(snap.productionLane.value.length, 2)
  assert.equal(snap.productionLane.value[0].workshop_name, '在线退火分厂')
  assert.equal(snap.productionLane.value[0].total_output, 11.4)
})

test('useDashboardSnapshot sets lastError on fetch failure without throwing', async () => {
  const fakeFetch = async () => { throw new Error('boom') }
  const mod = await import('../src/composables/useDashboardSnapshot.js')
  const snap = mod.createDashboardSnapshot({ fetchImpl: fakeFetch, now: new Date('2026-05-23T10:00:00Z') })
  await snap.load()
  assert.ok(snap.lastError.value, 'expected lastError to be set')
  assert.equal(snap.loading.value, false)
})
