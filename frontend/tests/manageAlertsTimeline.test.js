import test from 'node:test'
import assert from 'node:assert/strict'
import { createAlertsTimeline } from '../src/composables/useAlertsTimeline.js'

function makeFakes({ fdOk = true, qOk = true, rOk = true } = {}) {
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
    }
  }
}

test('load aggregates events from three endpoints, sorted desc', async () => {
  const t = createAlertsTimeline({ ...makeFakes(), now: new Date('2026-05-20T08:00:00') })
  await t.load()
  assert.equal(t.events.value.length, 4)
  assert.equal(t.events.value[0].domain, 'quality')
  assert.equal(t.events.value[t.events.value.length - 1].domain, 'reporting')
})

test('domainCounts reflects full unfiltered totals', async () => {
  const t = createAlertsTimeline({ ...makeFakes(), now: new Date('2026-05-20') })
  await t.load()
  assert.equal(t.domainCounts.value.production, 1)
  assert.equal(t.domainCounts.value.reporting, 1)
  assert.equal(t.domainCounts.value.quality, 1)
  assert.equal(t.domainCounts.value.reconciliation, 1)
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
  assert.equal(t.filteredEvents.value.length, 4)
})

test('freshnessStatus green when all 3 succeed', async () => {
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

test('freshnessStatus red when all 3 fail', async () => {
  const t = createAlertsTimeline({ ...makeFakes({ fdOk: false, qOk: false, rOk: false }), now: new Date('2026-05-20') })
  await t.load()
  assert.equal(t.freshnessStatus.value, 'red')
})

test('stepDate(-1) shifts targetDate one day earlier', async () => {
  const t = createAlertsTimeline({ ...makeFakes(), now: new Date('2026-05-20T08:00:00') })
  assert.equal(t.targetDate.value, '2026-05-19')
  t.stepDate(-1)
  assert.equal(t.targetDate.value, '2026-05-18')
})
