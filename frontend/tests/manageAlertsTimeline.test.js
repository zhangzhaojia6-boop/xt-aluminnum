import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createAlertsTimeline } from '../src/composables/useAlertsTimeline.js'
import { buildAlertWorkQueues } from '../src/components/manage/_alertEventNormalize.js'

function makeFakes({ fdOk = true, qOk = true, rOk = true, liveOk = true } = {}) {
  return {
    fetchFactoryDashboard: async () => {
      if (!fdOk) throw new Error('fd boom')
      return {
        exception_lane: {
          recent_items: [{ id: 'p1', occurred_at: '2026-05-19T10:23:00', summary: '产量异常' }],
          returned_items: [{ id: 'r1', occurred_at: '2026-05-19T08:15:00', summary: '退回' }]
        }
      }
    },
    fetchQualityIssues: async () => {
      if (!qOk) throw new Error('q boom')
      return [{ id: 'q1', occurred_at: '2026-05-19T11:00:00', summary: '抽检' }]
    },
    fetchReconciliationItems: async () => {
      if (!rOk) throw new Error('r boom')
      return [{ id: 'rc1', occurred_at: '2026-05-19T09:50:00', summary: '过磅' }]
    },
    fetchMesFillGaps: async () => ({
      items: [
        {
          status: 'missing_local_entry',
          workshop_name: '精整车间',
          mes_machine_name: '精整1#线',
          shift_name: '小夜班',
          tracking_card_no: 'TX-001',
          process_name: '包装',
          mes_end_time: '2026-05-19T16:20:00',
        },
        {
          status: 'matched',
          workshop_name: '精整车间',
          mes_machine_name: '精整2#线',
        },
      ],
    }),
    fetchLiveAggregation: async () => {
      if (!liveOk) throw new Error('live boom')
      return {
        overall_progress: {
          missing_cell_count: 122,
          pending_assignment: {
            entry_count: 3,
            missing_machine_count: 2,
            missing_shift_count: 1,
          },
        },
        owner_daily_status: {
          items: [
            { role_label: '电工', person_name: '张三', workshop_name: '热轧', status: 'missing' },
          ],
        },
      }
    },
  }
}

function makeEmptyFakes() {
  return {
    fetchFactoryDashboard: async () => ({}),
    fetchQualityIssues: async () => [],
    fetchReconciliationItems: async () => [],
    fetchMesFillGaps: async () => ({ items: [] }),
    fetchLiveAggregation: async () => ({}),
  }
}

test('load sends each endpoint the date parameter expected by its backend', async () => {
  const calls = []
  const t = createAlertsTimeline({
    fetchFactoryDashboard: async (params) => {
      calls.push(['factory', params])
      return {}
    },
    fetchQualityIssues: async (params) => {
      calls.push(['quality', params])
      return []
    },
    fetchReconciliationItems: async (params) => {
      calls.push(['reconciliation', params])
      return []
    },
    fetchMesFillGaps: async (params) => {
      calls.push(['mes', params])
      return { items: [] }
    },
    fetchLiveAggregation: async (params) => {
      calls.push(['live', params])
      return {}
    },
    now: new Date('2026-05-20T08:00:00')
  })

  await t.load()

  assert.deepEqual(Object.fromEntries(calls), {
    factory: { target_date: '2026-05-19' },
    quality: { business_date: '2026-05-19' },
    reconciliation: { business_date: '2026-05-19', status: 'open' },
    mes: { business_date: '2026-05-19' },
    live: { business_date: '2026-05-19' }
  })
})

test('load aggregates events from five endpoints, sorted desc', async () => {
  const t = createAlertsTimeline({ ...makeFakes(), now: new Date('2026-05-20T08:00:00') })
  await t.load()
  assert.equal(t.events.value.length, 8)
  assert.equal(t.events.value[0].domain, 'reporting')
  assert.equal(t.events.value.some((event) => event.id === 'live-missing:missing-cells'), true)
  assert.equal(t.events.value.some((event) => event.id === 'mes-fill-gap:TX-001'), true)
  assert.equal(t.events.value[t.events.value.length - 1].domain, 'reporting')
})

test('load calls daily production as the sixth endpoint with target_date', async () => {
  const calls = []
  const t = createAlertsTimeline({
    ...makeEmptyFakes(),
    fetchDailyProduction: async (params) => {
      calls.push(params)
      return { fact_closure: { critical_fields: [] } }
    },
    now: new Date('2026-05-20T08:00:00'),
  })

  await t.load()

  assert.deepEqual(calls, [{ target_date: '2026-05-19' }])
})

test('daily fact alerts preserve real traces routes and the selected target date', async () => {
  const t = createAlertsTimeline({
    ...makeEmptyFakes(),
    fetchDailyProduction: async () => ({
      fact_closure: { critical_fields: [] },
      fact_conflicts: [{
        id: 'conflict-1',
        field: 'total_output_daily',
        status: 'mismatch',
        summary: '总产量来源冲突',
        trace_id: 'trace-conflict',
        target_date: '2026-05-19',
      }],
      fact_missing: [{
        id: 'missing-1',
        field: 'finished_inbound_daily',
        status: 'missing',
        summary: '成品入库缺少可信来源',
        trace_id: null,
        target_date: '2026-05-19',
      }],
      hermes_failures: [{
        id: 'run-1',
        agent_code: 'factory_dispatch',
        status: 'failed',
        occurred_at: '2026-05-19T11:00:00+08:00',
        trace_id: 'trace-hermes',
        target_date: '2026-05-19',
      }],
      dingtalk_inbound_failures: [{
        id: 'run-2',
        agent_code: 'factory_dispatch',
        status: 'failed',
        occurred_at: '2026-05-19T10:00:00+08:00',
        trace_id: 'trace-dingtalk',
        target_date: '2026-05-19',
      }],
    }),
    now: new Date('2026-05-20T08:00:00'),
  })

  await t.load()

  assert.equal(t.events.value.length, 4)
  assert.deepEqual(t.events.value.map((event) => event.targetDate), Array(4).fill('2026-05-19'))
  assert.equal(t.events.value.find((event) => event.id === 'fact-conflict:conflict-1').traceId, 'trace-conflict')
  assert.equal(
    t.events.value.find((event) => event.id === 'fact-conflict:conflict-1').detailRoute,
    '/manage/alerts?trace_id=trace-conflict'
  )
  assert.equal(t.events.value.find((event) => event.id === 'fact-missing:missing-1').traceId, '')
  assert.equal(t.events.value.find((event) => event.id === 'hermes-failure:run-1').traceId, 'trace-hermes')
  assert.equal(t.events.value.find((event) => event.id === 'dingtalk-failure:run-2').traceId, 'trace-dingtalk')
})

test('daily closure does not create alerts when explicit alert arrays are absent', async () => {
  const t = createAlertsTimeline({
    ...makeEmptyFakes(),
    fetchDailyProduction: async () => ({
      fact_closure: {
        critical_fields: [
          { field: 'total_output_daily', status: 'missing' },
          { field: 'finished_inbound_daily', status: 'needs_evidence', trace_id: 'trace-closure-only' },
        ],
      },
    }),
    now: new Date('2026-05-20T08:00:00'),
  })

  await t.load()

  assert.deepEqual(t.events.value, [])
})

test('missing canonical capability becomes a system fallback without business counts', async () => {
  const t = createAlertsTimeline({
    ...makeEmptyFakes(),
    fetchDailyProduction: async () => ({
      fact_closure_available: false,
      fact_closure_capability: {
        status: 'missing',
        agent_failure_audit: 'unavailable',
      },
      fact_missing: [],
      fact_conflicts: [],
      hermes_failures: [],
      dingtalk_inbound_failures: [],
    }),
    now: new Date('2026-05-20T08:00:00'),
  })

  await t.load()

  assert.equal(t.events.value.length, 1)
  assert.equal(t.events.value[0].isFallback, true)
  assert.equal(t.events.value[0].status, null)
  assert.equal(t.events.value[0].traceId, '')
  assert.equal(t.events.value[0].detailRoute, '/manage/today?section=daily-report')
  assert.deepEqual(t.domainCounts.value, {
    production: 0,
    reporting: 0,
    quality: 0,
    reconciliation: 0,
    mes: 0,
  })
  const businessEvents = t.events.value.filter((event) => !event.isFallback)
  const capabilityEvents = t.events.value.filter((event) => event.isFallback)
  const queueCount = buildAlertWorkQueues(t.events.value)
    .reduce((sum, queue) => sum + queue.count, 0)
  assert.equal(businessEvents.length, 0)
  assert.equal(businessEvents.filter((event) => event.status === 'open').length, 0)
  assert.equal(queueCount, 0)
  assert.equal(capabilityEvents.length, 1)
  assert.equal(capabilityEvents[0].summary, '当日事实闭包不可用')
})

test('available canonical capability does not create a system fallback', async () => {
  const t = createAlertsTimeline({
    ...makeEmptyFakes(),
    fetchDailyProduction: async () => ({
      fact_closure_available: true,
      fact_closure_capability: {
        status: 'available',
        agent_failure_audit: 'unavailable',
      },
      fact_missing: [],
      fact_conflicts: [],
      hermes_failures: [],
      dingtalk_inbound_failures: [],
    }),
    now: new Date('2026-05-20T08:00:00'),
  })

  await t.load()

  assert.deepEqual(t.events.value, [])
})

test('daily fact alert detail never exposes derived or unknown sources', async () => {
  const t = createAlertsTimeline({
    ...makeEmptyFakes(),
    fetchDailyProduction: async () => ({
      fact_closure_available: true,
      fact_missing: [
        {
          id: 'missing-derived-source',
          field: 'total_output_daily',
          source: 'output_skill',
          status: 'needs_evidence',
          target_date: '2026-05-19',
        },
        {
          id: 'missing-unknown-source',
          field: 'finished_inbound_daily',
          source: 'invented_unapproved_source',
          status: 'needs_evidence',
          target_date: '2026-05-19',
        },
      ],
    }),
    now: new Date('2026-05-20T08:00:00'),
  })

  await t.load()

  assert.equal(t.events.value.length, 2)
  for (const event of t.events.value) assert.match(event.detail, /暂无可信来源/)
  assert.doesNotMatch(JSON.stringify(t.events.value), /output_skill|invented_unapproved_source/)
})

test('initial trace query filters the timeline to matching real events', async () => {
  const t = createAlertsTimeline({
    ...makeEmptyFakes(),
    traceId: 'trace-hermes',
    fetchDailyProduction: async () => ({
      hermes_failures: [
        { id: 'run-1', status: 'failed', trace_id: 'trace-hermes', target_date: '2026-05-19' },
        { id: 'run-2', status: 'failed', trace_id: 'trace-other', target_date: '2026-05-19' },
      ],
    }),
    now: new Date('2026-05-20T08:00:00'),
  })

  await t.load()

  assert.deepEqual(t.filteredEvents.value.map((event) => event.traceId), ['trace-hermes'])
})

test('daily endpoint failure adds a visible non-business fallback and lastError', async () => {
  const t = createAlertsTimeline({
    ...makeEmptyFakes(),
    fetchDailyProduction: async () => {
      throw new Error('daily boom')
    },
    now: new Date('2026-05-20T08:00:00'),
  })

  await t.load()

  assert.equal(t.freshnessStatus.value, 'yellow')
  assert.equal(t.events.value.length, 1)
  assert.equal(t.events.value[0].isFallback, true)
  assert.equal(t.events.value[0].status, null)
  assert.equal(t.events.value[0].traceId, '')
  assert.equal(t.events.value[0].detailRoute, '/manage/today?section=daily-report')
  assert.match(t.lastError.value, /事实|日报/)
  assert.equal(t.domainCounts.value.reporting, 0)
  assert.equal(
    buildAlertWorkQueues(t.events.value).reduce((sum, queue) => sum + queue.count, 0),
    0
  )
})

test('domainCounts reflects full unfiltered totals', async () => {
  const t = createAlertsTimeline({ ...makeFakes(), now: new Date('2026-05-20') })
  await t.load()
  assert.equal(t.domainCounts.value.production, 1)
  assert.equal(t.domainCounts.value.quality, 1)
  assert.equal(t.domainCounts.value.reconciliation, 1)
  assert.equal(t.domainCounts.value.mes, 1)
  assert.equal(t.domainCounts.value.reporting, 4)
})

test('filteredEvents respects domains[]', async () => {
  const t = createAlertsTimeline({ ...makeFakes(), now: new Date('2026-05-20') })
  await t.load()
  t.domains.value = ['production', 'reconciliation']
  assert.equal(t.filteredEvents.value.length, 2)
  assert.ok(t.filteredEvents.value.every((e) => ['production', 'reconciliation'].includes(e.domain)))
})

test('empty domains[] means all', async () => {
  const t = createAlertsTimeline({ ...makeFakes(), now: new Date('2026-05-20') })
  await t.load()
  t.domains.value = []
  assert.equal(t.filteredEvents.value.length, 8)
})

test('MES fill gaps appear as concrete alert events with workshop machine shift and card', async () => {
  const t = createAlertsTimeline({ ...makeFakes(), now: new Date('2026-05-20T08:00:00') })
  await t.load()

  const event = t.events.value.find((item) => item.id === 'mes-fill-gap:TX-001')
  assert.equal(event.domain, 'mes')
  assert.equal(event.summary, 'MES有工序本地未填：精整车间 · 精整1#线 · 小夜班')
  assert.match(event.detail, /TX-001/)
  assert.match(event.detail, /包装/)
  assert.equal(event.status, 'open')
})

test('freshnessStatus green when all endpoints succeed', async () => {
  const t = createAlertsTimeline({ ...makeFakes(), now: new Date('2026-05-20') })
  await t.load()
  assert.equal(t.freshnessStatus.value, 'green')
})

test('freshnessStatus yellow when one endpoint fails, fallback card injected', async () => {
  const t = createAlertsTimeline({ ...makeFakes({ qOk: false }), now: new Date('2026-05-20') })
  await t.load()
  assert.equal(t.freshnessStatus.value, 'yellow')
  const fallbacks = t.events.value.filter((e) => e.isFallback)
  assert.equal(fallbacks.length, 1)
  assert.equal(fallbacks[0].domain, 'quality')
})

test('freshnessStatus red when most endpoints fail', async () => {
  const t = createAlertsTimeline({ ...makeFakes({ fdOk: false, qOk: false, rOk: false, liveOk: false }), now: new Date('2026-05-20') })
  await t.load()
  assert.equal(t.freshnessStatus.value, 'red')
})

test('stepDate(-1) shifts targetDate one day earlier', async () => {
  const t = createAlertsTimeline({ ...makeFakes(), now: new Date('2026-05-20T08:00:00') })
  assert.equal(t.targetDate.value, '2026-05-19')
  t.stepDate(-1)
  assert.equal(t.targetDate.value, '2026-05-18')
})

test('AlertsPage reads trace_id into the existing timeline filter', () => {
  const src = readFileSync(new URL('../src/views/manage/alerts/AlertsPage.vue', import.meta.url), 'utf8')
  assert.match(src, /route\.query\.trace_id/)
  assert.match(src, /timeline\.setTraceId/)
})
