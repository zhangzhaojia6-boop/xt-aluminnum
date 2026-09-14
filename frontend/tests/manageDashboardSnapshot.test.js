import test from 'node:test'
import assert from 'node:assert/strict'

function deferred() {
  let resolve, reject
  const promise = new Promise((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}

test('daily figures load before expensive secondary summaries start', async () => {
  const daily = deferred()
  const calls = []
  const { createDashboardSnapshot } = await import('../src/composables/useDashboardSnapshot.js')
  const snap = createDashboardSnapshot({
    fetchDailyImpl: () => { calls.push('daily'); return daily.promise },
    fetchImpl: async () => { calls.push('factory'); return {} },
    fetchFactoryCommandImpl: async () => { calls.push('command'); return {} },
  })
  const loaded = snap.load()
  assert.deepEqual(calls, ['daily'])
  daily.resolve({ plant_output: { daily_output: 42 } })
  await loaded
  assert.deepEqual(calls, ['daily', 'factory', 'command'])
  assert.equal(snap.leaderMetrics.value.total_output_weight, 42)
})

test('daily refresh keeps visible figures, skips duplicate requests and reads new facts', async () => {
  const update = deferred()
  let calls = 0
  let summaries = 0
  const { createDashboardSnapshot } = await import('../src/composables/useDashboardSnapshot.js')
  const snap = createDashboardSnapshot({
    fetchDailyImpl: () => ++calls === 1
      ? Promise.resolve({ plant_output: { daily_output: 42 } }) : update.promise,
    fetchImpl: async () => { summaries++; return {} },
    fetchFactoryCommandImpl: async () => ({}),
  })
  await snap.load()
  const refreshed = snap.refreshDaily()
  await snap.refreshDaily()
  assert.equal(calls, 2)
  assert.equal(snap.leaderMetrics.value.total_output_weight, 42)
  update.resolve({ plant_output: { daily_output: 53 } })
  await refreshed
  assert.equal(snap.leaderMetrics.value.total_output_weight, 53)
  assert.equal(summaries, 1)
})

test('a failed daily refresh preserves figures and reports failure until recovery', async () => {
  let fail = false
  const { createDashboardSnapshot } = await import('../src/composables/useDashboardSnapshot.js')
  const snap = createDashboardSnapshot({
    fetchDailyImpl: async () => {
      if (fail) throw new Error('offline')
      return { plant_output: { daily_output: 42 } }
    },
    fetchImpl: async () => ({}), fetchFactoryCommandImpl: async () => ({}),
  })
  await snap.load()
  const previousRefresh = snap.lastRefreshAt.value
  fail = true
  await snap.refreshDaily()
  assert.equal(snap.leaderMetrics.value.total_output_weight, 42)
  assert.equal(snap.lastRefreshAt.value, previousRefresh)
  assert.match(snap.lastError.value, /日报更新失败/)
  fail = false
  await snap.refreshDaily()
  assert.equal(snap.lastError.value, '')
})

test('a successful daily refresh clears the initial daily failure', async () => {
  let fail = true
  const { createDashboardSnapshot } = await import('../src/composables/useDashboardSnapshot.js')
  const snap = createDashboardSnapshot({
    fetchDailyImpl: async () => {
      if (fail) throw new Error('offline')
      return { plant_output: { daily_output: 42 } }
    },
    fetchImpl: async () => ({}), fetchFactoryCommandImpl: async () => ({}),
  })
  await snap.load()
  assert.match(snap.lastError.value, /日报/)
  fail = false
  await snap.refreshDaily()
  assert.equal(snap.lastError.value, '')
})

test('a background daily refresh cannot overwrite a newly selected date', async () => {
  const oldUpdate = deferred()
  let calls = 0
  const { createDashboardSnapshot } = await import('../src/composables/useDashboardSnapshot.js')
  const snap = createDashboardSnapshot({
    fetchDailyImpl: async () => ++calls === 2 ? oldUpdate.promise : { plant_output: { daily_output: calls } },
    fetchImpl: async () => ({}), fetchFactoryCommandImpl: async () => ({}),
  })
  await snap.load()
  const oldRefresh = snap.refreshDaily()
  await snap.stepDate(-1)
  oldUpdate.resolve({ plant_output: { daily_output: 99 } })
  await oldRefresh
  assert.equal(snap.leaderMetrics.value.total_output_weight, 3)
  assert.equal(snap.pending.value.daily, false)
})

test('failed production sources never substitute inbound or work in progress quantities', async () => {
  const { createDashboardSnapshot } = await import('../src/composables/useDashboardSnapshot.js')
  const snap = createDashboardSnapshot({
    fetchImpl: async () => { throw new Error('summary unavailable') },
    fetchDailyImpl: async () => { throw new Error('daily unavailable') },
    fetchFactoryCommandImpl: async () => ({
      today_output_tons: 73.6,
      storage_finished_weight: 73.6,
      wip_tons: 90,
      workshop_summary: [{ workshop_name: '冷轧', active_tons: 90, total_output_tons: 90 }],
    }),
  })
  await snap.load()
  assert.equal(snap.leaderMetrics.value.total_output_weight, null)
  assert.equal(snap.managementEstimate.value.output_tons, null)
  assert.deepEqual(snap.productionLane.value, [])
  assert.equal(snap.factoryCommandOverview.value.wip_tons, 90)
})

test('daily figures publish while summary is pending and survive its failure', async () => {
  const summary = deferred()
  const { createDashboardSnapshot } = await import('../src/composables/useDashboardSnapshot.js')
  const snap = createDashboardSnapshot({
    fetchImpl: () => summary.promise,
    fetchDailyImpl: async () => ({ plant_output: { daily_output: 81.25 } }),
    fetchFactoryCommandImpl: async () => ({ today_output_tons: 5 }),
  })
  const complete = snap.load()
  await new Promise((resolve) => setImmediate(resolve))
  assert.equal(snap.leaderMetrics.value.total_output_weight, 81.25)
  assert.equal(snap.pending.value.daily, false)
  assert.equal(snap.loading.value, true)
  summary.reject(new Error('summary unavailable'))
  await complete
  assert.equal(snap.leaderMetrics.value.total_output_weight, 81.25)
  assert.match(snap.lastError.value, /经营摘要/)
  assert.equal(snap.loading.value, false)
})

test('changing dates clears old figures and late responses cannot overwrite the selected day', async () => {
  const oldDaily = deferred()
  const newDaily = deferred()
  let calls = 0
  const { createDashboardSnapshot } = await import('../src/composables/useDashboardSnapshot.js')
  const snap = createDashboardSnapshot({
    fetchImpl: async () => ({}),
    fetchDailyImpl: () => (++calls === 1 ? oldDaily.promise : newDaily.promise),
    fetchFactoryCommandImpl: async () => ({}),
  })
  const oldLoad = snap.load()
  const newLoad = snap.stepDate(-1)
  assert.deepEqual(snap.data.value, {})
  newDaily.resolve({ plant_output: { daily_output: 42 } })
  await newLoad
  oldDaily.resolve({ plant_output: { daily_output: 99 } })
  await oldLoad
  assert.equal(snap.leaderMetrics.value.total_output_weight, 42)
  assert.equal(snap.loading.value, false)
  const refresh = snap.load()
  assert.deepEqual(snap.data.value, {})
  await refresh
})

test('useDashboardSnapshot defaults target_date to last completed production business date', async () => {
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

test('useDashboardSnapshot default changes at the 07:50 production day start', async () => {
  const fakeFetch = async (params) => {
    fakeFetch.lastParams = params
    return { target_date: params.target_date }
  }
  const mod = await import('../src/composables/useDashboardSnapshot.js')
  const before = mod.createDashboardSnapshot({ fetchImpl: fakeFetch, now: new Date('2026-05-22T23:49:00Z') })
  await before.load()
  assert.equal(fakeFetch.lastParams.target_date, '2026-05-21')

  const snap = mod.createDashboardSnapshot({ fetchImpl: fakeFetch, now: new Date('2026-05-22T23:50:00Z') })
  await snap.load()
  assert.equal(fakeFetch.lastParams.target_date, '2026-05-22')
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

test('useDashboardSnapshot keeps MES packaging output separate from finished inbound output', async () => {
  const fakeFetch = async () => ({ leader_metrics: {} })
  const fakeDailyFetch = async () => ({
    plant_output: {
      daily_output: 81.25,
      finished_inbound_output: 73.6,
      basis_label: '包装产量',
    },
  })
  const mod = await import('../src/composables/useDashboardSnapshot.js')
  const snap = mod.createDashboardSnapshot({
    fetchImpl: fakeFetch,
    fetchDailyImpl: fakeDailyFetch,
    fetchFactoryCommandImpl: async () => ({}),
    now: new Date('2026-05-23T10:00:00Z')
  })

  await snap.load()

  assert.equal(snap.leaderMetrics.value.total_output_weight, 81.25)
  assert.equal(snap.leaderMetrics.value.storage_finished_weight, 73.6)
  assert.equal(snap.managementEstimate.value.output_tons, 81.25)
  assert.equal(snap.managementEstimate.value.cost_basis_label, '包装产量')
})

test('factory command overview remains available without substituting its production definition', async () => {
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
  assert.equal(snap.leaderMetrics.value.total_output_weight, null)
  assert.equal(snap.leaderMetrics.value.today_total_output, null)
  assert.equal(snap.leaderMetrics.value.yield_rate, 92.5)
  assert.deepEqual(snap.productionLane.value, [])
  assert.equal(snap.factoryCommandOverview.value.workshop_summary[0].total_output_tons, 11.4)
})

test('useDashboardSnapshot sets lastError on fetch failure without throwing', async () => {
  const fakeFetch = async () => { throw new Error('boom') }
  const mod = await import('../src/composables/useDashboardSnapshot.js')
  const snap = mod.createDashboardSnapshot({ fetchImpl: fakeFetch, now: new Date('2026-05-23T10:00:00Z') })
  await snap.load()
  assert.ok(snap.lastError.value, 'expected lastError to be set')
  assert.equal(snap.loading.value, false)
})
