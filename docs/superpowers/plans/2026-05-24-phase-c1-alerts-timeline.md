# Phase C-1: Alerts Tab Single-Column Timeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the manage 异常 tab as a single-column read-only timeline that mixes events from three back-ends (factory-director + quality + reconciliation), letting the boss scan the day's exceptions top-to-bottom and click into legacy surfaces to act on them.

**Architecture:** New `useAlertsTimeline` composable runs `Promise.allSettled` over three endpoints, hands the raw payloads to pure normalizer functions in `_alertEventNormalize.js`, and exposes a sorted `events` list plus `domainCounts` and `freshnessStatus` for the page. `AlertsPage.vue` is rewritten end-to-end to render `DateSwitcher + DomainFilterChips + EventTimeline (EventCard ×N)`. The legacy `?surface=` query maps to `?domain=` via router redirect; the three legacy work-surface views move under `/manage/alerts/legacy` so deep-links from cards keep working.

**Tech Stack:** Vue 3 SFC + script setup, Pinia (already wired), vue-router 4, dayjs, Element Plus (only for `el-button`/`el-select` re-use already in legacy surfaces — new components stay native), Playwright e2e, `node --test` source-string assertions (no `@vue/test-utils`).

**Spec:** `docs/superpowers/specs/2026-05-24-phase-c1-alerts-timeline-design.md`

**Branch:** `codex/phase-c1-alerts-timeline` (already on top of Phase A+B). Rebase to `main` after Phase A+B PR merges; do not target `main` directly until then.

---

## File Structure

**Create:**
- `frontend/src/components/manage/_alertEventNormalize.js` — pure functions: `normalizeFactoryDirector(payload, targetDate)`, `normalizeQuality(items, targetDate)`, `normalizeReconciliation(items, targetDate)`, plus `mergeAndSort(eventsArrays)`
- `frontend/src/composables/useAlertsTimeline.js` — wires the three endpoints into a single reactive snapshot
- `frontend/src/components/manage/DomainFilterChips.vue` — top filter chips, multi-select with "全部" toggle
- `frontend/src/components/manage/EventCard.vue` — single event row
- `frontend/src/components/manage/EventTimeline.vue` — list shell + summary line + empty state
- `frontend/tests/manageAlertEventNormalize.test.js`
- `frontend/tests/manageAlertsTimeline.test.js`
- `frontend/tests/manageDomainFilterChips.test.js`
- `frontend/tests/manageEventCard.test.js`
- `frontend/tests/manageEventTimeline.test.js`
- `frontend/tests/manageAlertsPage.test.js`
- `frontend/e2e/manage-alerts-timeline.spec.js`

**Modify:**
- `frontend/src/views/manage/alerts/AlertsPage.vue` — full rewrite (was a `?surface=` switch, becomes the timeline page)
- `frontend/src/router/index.js` — add `/manage/alerts/legacy` route mounting the three old surface views; add `beforeEnter` on `/manage/alerts` that redirects `?surface=anomaly|quality|reconciliation` → `?domain=production|quality|reconciliation`
- `frontend/src/views/manage/today/TodayPage.vue` — three `KeyEventList` slot routes change `?surface=…` → `?domain=…`
- `frontend/e2e/helpers/review-mocks.js` — add `mockQualityIssues()` and `mockReconciliationItems()` helpers

**Preserve unchanged:**
- `frontend/src/views/attendance/AnomalyReview.vue`
- `frontend/src/views/quality/QualityCenter.vue`
- `frontend/src/views/reconciliation/ReconciliationCenter.vue`

---

## Test Strategy

This project does **not** use `@vue/test-utils`. Component tests assert against the SFC source string read with `readFileSync` (see `frontend/tests/manageProductionPage.test.js` for the established pattern). Logic that needs real reactivity tests goes through pure JS modules — that's why normalizers and the composable's data shaping live in `.js` files we can import directly.

E2E uses Playwright with mocked endpoints (see `frontend/e2e/helpers/review-mocks.js`). Add new mocks additively; never delete existing keys to avoid breaking Phase A+B specs.

---

## Task 1: Pure normalizers + tests

**Files:**
- Create: `frontend/src/components/manage/_alertEventNormalize.js`
- Create: `frontend/tests/manageAlertEventNormalize.test.js`

- [ ] **Step 1: Write failing tests first**

Create `frontend/tests/manageAlertEventNormalize.test.js`:

```js
import test from 'node:test'
import assert from 'node:assert/strict'
import {
  normalizeFactoryDirector,
  normalizeQuality,
  normalizeReconciliation,
  mergeAndSort
} from '../src/components/manage/_alertEventNormalize.js'

const DATE = '2026-05-19'

test('normalizeFactoryDirector maps recent_items to production domain', () => {
  const payload = {
    exception_lane: {
      recent_items: [
        { id: 'p1', occurred_at: '2026-05-19T10:23:00', summary: '一车间产量异常' }
      ]
    }
  }
  const out = normalizeFactoryDirector(payload, DATE)
  assert.equal(out.length, 1)
  assert.equal(out[0].id, 'production:p1')
  assert.equal(out[0].domain, 'production')
  assert.equal(out[0].summary, '一车间产量异常')
  assert.equal(out[0].occurredAt, '2026-05-19T10:23:00')
  assert.equal(out[0].detailRoute, '/manage/alerts/legacy?surface=anomaly')
  assert.equal(out[0].status, 'open')
})

test('normalizeFactoryDirector merges returned_items + reminder_items into reporting', () => {
  const payload = {
    exception_lane: {
      returned_items: [{ id: 'r1', summary: '退回' }],
      reminder_items: [{ id: 'm1', summary: '催报' }]
    }
  }
  const out = normalizeFactoryDirector(payload, DATE)
  assert.equal(out.length, 2)
  assert.ok(out.every((e) => e.domain === 'reporting'))
})

test('normalizeFactoryDirector falls back to target_date midnight when occurred_at missing', () => {
  const payload = {
    exception_lane: { recent_items: [{ id: 'p1', summary: 'x' }] }
  }
  const out = normalizeFactoryDirector(payload, DATE)
  assert.equal(out[0].occurredAt, '2026-05-19T00:00:00')
})

test('normalizeFactoryDirector composes summary from workshop+shift+desc when missing', () => {
  const payload = {
    exception_lane: {
      recent_items: [{ id: 'p1', workshop_name: '一车间', shift_label: '早班', event_type: '产量异常' }]
    }
  }
  const out = normalizeFactoryDirector(payload, DATE)
  assert.equal(out[0].summary, '一车间 早班 产量异常')
})

test('normalizeFactoryDirector handles null exception_lane safely', () => {
  assert.deepEqual(normalizeFactoryDirector({}, DATE), [])
  assert.deepEqual(normalizeFactoryDirector({ exception_lane: null }, DATE), [])
  assert.deepEqual(normalizeFactoryDirector(null, DATE), [])
})

test('normalizeFactoryDirector resolved status maps from row.status', () => {
  const payload = {
    exception_lane: { recent_items: [{ id: 'p1', summary: 'x', status: 'resolved' }] }
  }
  assert.equal(normalizeFactoryDirector(payload, DATE)[0].status, 'resolved')
})

test('normalizeQuality maps to quality domain with quality detail route', () => {
  const items = [{ id: 'q1', summary: '抽检不合格', occurred_at: '2026-05-19T11:00:00' }]
  const out = normalizeQuality(items, DATE)
  assert.equal(out[0].id, 'quality:q1')
  assert.equal(out[0].domain, 'quality')
  assert.equal(out[0].detailRoute, '/manage/alerts/legacy?surface=quality')
})

test('normalizeReconciliation maps to reconciliation domain', () => {
  const items = [{ id: 'r1', summary: '过磅差异', occurred_at: '2026-05-19T09:50:00' }]
  const out = normalizeReconciliation(items, DATE)
  assert.equal(out[0].domain, 'reconciliation')
  assert.equal(out[0].detailRoute, '/manage/alerts/legacy?surface=reconciliation')
})

test('id falls back to domain:index when raw id missing', () => {
  const out = normalizeQuality([{ summary: 'x' }, { summary: 'y' }], DATE)
  assert.equal(out[0].id, 'quality:0')
  assert.equal(out[1].id, 'quality:1')
})

test('null/undefined arrays normalize to empty', () => {
  assert.deepEqual(normalizeQuality(null, DATE), [])
  assert.deepEqual(normalizeReconciliation(undefined, DATE), [])
})

test('mergeAndSort sorts by occurredAt desc, ties broken by domain asc', () => {
  const out = mergeAndSort([
    [{ id: 'a', domain: 'quality', occurredAt: '2026-05-19T10:00:00' }],
    [{ id: 'b', domain: 'production', occurredAt: '2026-05-19T10:00:00' }],
    [{ id: 'c', domain: 'reconciliation', occurredAt: '2026-05-19T11:00:00' }]
  ])
  assert.deepEqual(out.map((e) => e.id), ['c', 'b', 'a'])
})
```

- [ ] **Step 2: Run tests, verify all fail**

```
cd frontend && node --test tests/manageAlertEventNormalize.test.js
```
Expected: every test fails with "Cannot find module".

- [ ] **Step 3: Implement `_alertEventNormalize.js`**

```js
const FD_LEGACY = '/manage/alerts/legacy?surface=anomaly'
const Q_LEGACY = '/manage/alerts/legacy?surface=quality'
const R_LEGACY = '/manage/alerts/legacy?surface=reconciliation'

function safeArray(v) {
  return Array.isArray(v) ? v : []
}

function fallbackOccurredAt(row, targetDate) {
  return row.occurred_at || row.created_at || `${targetDate}T00:00:00`
}

function fallbackSummary(row) {
  if (row.summary) return row.summary
  return [row.workshop_name, row.shift_label, row.event_type].filter(Boolean).join(' ')
}

function fallbackId(domain, row, idx) {
  const raw = row.id ?? row.shift_id
  return raw != null ? `${domain}:${raw}` : `${domain}:${idx}`
}

function fallbackStatus(row) {
  if (!row.status) return 'open'
  return row.status === 'resolved' ? 'resolved' : 'open'
}

export function normalizeFactoryDirector(payload, targetDate) {
  const lane = payload && payload.exception_lane
  if (!lane) return []
  const out = []
  safeArray(lane.recent_items).forEach((row, idx) => {
    out.push({
      id: fallbackId('production', row, idx),
      domain: 'production',
      occurredAt: fallbackOccurredAt(row, targetDate),
      summary: fallbackSummary(row),
      detailRoute: FD_LEGACY,
      status: fallbackStatus(row)
    })
  })
  ;[...safeArray(lane.returned_items), ...safeArray(lane.reminder_items)].forEach((row, idx) => {
    out.push({
      id: fallbackId('reporting', row, idx),
      domain: 'reporting',
      occurredAt: fallbackOccurredAt(row, targetDate),
      summary: fallbackSummary(row),
      detailRoute: FD_LEGACY,
      status: fallbackStatus(row)
    })
  })
  return out
}

export function normalizeQuality(items, targetDate) {
  return safeArray(items).map((row, idx) => ({
    id: fallbackId('quality', row, idx),
    domain: 'quality',
    occurredAt: fallbackOccurredAt(row, targetDate),
    summary: fallbackSummary(row),
    detailRoute: Q_LEGACY,
    status: fallbackStatus(row)
  }))
}

export function normalizeReconciliation(items, targetDate) {
  return safeArray(items).map((row, idx) => ({
    id: fallbackId('reconciliation', row, idx),
    domain: 'reconciliation',
    occurredAt: fallbackOccurredAt(row, targetDate),
    summary: fallbackSummary(row),
    detailRoute: R_LEGACY,
    status: fallbackStatus(row)
  }))
}

export function mergeAndSort(eventsArrays) {
  const merged = eventsArrays.flat()
  return merged.sort((a, b) => {
    if (a.occurredAt !== b.occurredAt) return a.occurredAt < b.occurredAt ? 1 : -1
    return a.domain < b.domain ? -1 : a.domain > b.domain ? 1 : 0
  })
}
```

- [ ] **Step 4: Re-run tests, verify all pass**

```
cd frontend && node --test tests/manageAlertEventNormalize.test.js
```
Expected: all 11 tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/manage/_alertEventNormalize.js frontend/tests/manageAlertEventNormalize.test.js
git commit -m "feat(alerts): pure normalizers for 3-domain alert events"
```

---

## Task 2: useAlertsTimeline composable

**Files:**
- Create: `frontend/src/composables/useAlertsTimeline.js`
- Create: `frontend/tests/manageAlertsTimeline.test.js`

- [ ] **Step 1: Write failing tests**

Create `frontend/tests/manageAlertsTimeline.test.js`:

```js
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
```

- [ ] **Step 2: Run, verify all fail**

```
cd frontend && node --test tests/manageAlertsTimeline.test.js
```

- [ ] **Step 3: Implement `useAlertsTimeline.js`**

```js
import { ref, computed, watch } from 'vue'
import dayjs from 'dayjs'
import { fetchFactoryDashboard } from '../api/dashboard.js'
import { fetchQualityIssues } from '../api/quality.js'
import { fetchReconciliationItems } from '../api/reconciliation.js'
import {
  normalizeFactoryDirector,
  normalizeQuality,
  normalizeReconciliation,
  mergeAndSort
} from '../components/manage/_alertEventNormalize.js'

const DOMAINS = ['production', 'reporting', 'quality', 'reconciliation']
const FALLBACK_ROUTE = {
  production: '/manage/alerts/legacy?surface=anomaly',
  reporting: '/manage/alerts/legacy?surface=anomaly',
  quality: '/manage/alerts/legacy?surface=quality',
  reconciliation: '/manage/alerts/legacy?surface=reconciliation'
}

export function createAlertsTimeline({
  fetchFactoryDashboard: fdImpl = fetchFactoryDashboard,
  fetchQualityIssues: qImpl = fetchQualityIssues,
  fetchReconciliationItems: rImpl = fetchReconciliationItems,
  now = new Date()
} = {}) {
  const yesterday = dayjs(now).subtract(1, 'day').format('YYYY-MM-DD')
  const targetDate = ref(yesterday)
  const domains = ref([])
  const events = ref([])
  const loading = ref(false)
  const lastError = ref('')
  const failed = ref({ production: false, reporting: false, quality: false, reconciliation: false })
  let inflight = Promise.resolve()

  function fallbackCard(domain) {
    return {
      id: `${domain}:__fallback__`,
      domain,
      occurredAt: `${targetDate.value}T23:59:59`,
      summary: '加载失败，点击查看老页',
      detailRoute: FALLBACK_ROUTE[domain],
      status: null,
      isFallback: true
    }
  }

  function load() {
    loading.value = true
    inflight = (async () => {
      const date = targetDate.value
      const [fd, q, r] = await Promise.allSettled([
        fdImpl({ target_date: date }),
        qImpl({ target_date: date }),
        rImpl({ target_date: date, status: 'open' })
      ])
      const buckets = []
      const fail = { production: false, reporting: false, quality: false, reconciliation: false }
      if (fd.status === 'fulfilled') {
        buckets.push(normalizeFactoryDirector(fd.value, date))
      } else {
        fail.production = true
        fail.reporting = true
        buckets.push([fallbackCard('production')])
      }
      if (q.status === 'fulfilled') {
        buckets.push(normalizeQuality(q.value, date))
      } else {
        fail.quality = true
        buckets.push([fallbackCard('quality')])
      }
      if (r.status === 'fulfilled') {
        buckets.push(normalizeReconciliation(r.value, date))
      } else {
        fail.reconciliation = true
        buckets.push([fallbackCard('reconciliation')])
      }
      failed.value = fail
      events.value = mergeAndSort(buckets)
      lastError.value = ''
      loading.value = false
    })()
    return inflight
  }

  watch(targetDate, () => load(), { flush: 'sync' })

  function stepDate(deltaDays) {
    targetDate.value = dayjs(targetDate.value).add(deltaDays, 'day').format('YYYY-MM-DD')
    return inflight
  }

  const domainCounts = computed(() => {
    const counts = { production: 0, reporting: 0, quality: 0, reconciliation: 0 }
    for (const e of events.value) {
      if (e.isFallback) continue
      if (counts[e.domain] != null) counts[e.domain] += 1
    }
    return counts
  })

  const filteredEvents = computed(() => {
    if (!domains.value.length) return events.value
    return events.value.filter((e) => domains.value.includes(e.domain))
  })

  const freshnessStatus = computed(() => {
    const fails = DOMAINS.filter((d) => failed.value[d]).length
    if (fails === 0) return 'green'
    if (fails >= 3) return 'red'
    return 'yellow'
  })

  return {
    targetDate, domains, events, filteredEvents, domainCounts,
    loading, lastError, freshnessStatus,
    load, stepDate
  }
}

export function useAlertsTimeline() {
  return createAlertsTimeline()
}
```

- [ ] **Step 4: Re-run tests, verify pass**

```
cd frontend && node --test tests/manageAlertsTimeline.test.js
```
Expected: all 8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/composables/useAlertsTimeline.js frontend/tests/manageAlertsTimeline.test.js
git commit -m "feat(alerts): useAlertsTimeline composable with allSettled fan-out"
```

---

## Task 3: EventCard component

**Files:**
- Create: `frontend/src/components/manage/EventCard.vue`
- Create: `frontend/tests/manageEventCard.test.js`

- [ ] **Step 1: Write failing tests**

```js
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const SRC = readFileSync(new URL('../src/components/manage/EventCard.vue', import.meta.url), 'utf8')

test('EventCard renders time, domain pill, summary, arrow', () => {
  for (const slot of ['xt-event-card__time', 'xt-event-card__pill', 'xt-event-card__summary', 'xt-event-card__arrow']) {
    assert.match(SRC, new RegExp(slot), `missing ${slot}`)
  }
})

test('EventCard maps 4 domains to xt color tokens via color-mix', () => {
  for (const token of ['--xt-color-warning', '--xt-color-danger', '--xt-color-accent', '--xt-text-muted']) {
    assert.match(SRC, new RegExp(token.replace(/-/g, '\\-')))
  }
  assert.match(SRC, /color-mix/)
})

test('EventCard uses no hex or rgba color literals', () => {
  const style = SRC.split('<style')[1] || ''
  assert.equal(/#[0-9a-fA-F]{3,6}/.test(style), false)
  assert.equal(/rgba?\(\s*\d/.test(style), false)
})

test('EventCard whole-card is clickable, no inner button', () => {
  assert.match(SRC, /@click/)
  assert.equal(/<button/.test(SRC), false)
  assert.equal(/<el-button/.test(SRC), false)
})

test('EventCard renders fallback card style when event.isFallback', () => {
  assert.match(SRC, /isFallback/)
  assert.match(SRC, /is-fallback/)
})

test('EventCard domain pill labels are 中文', () => {
  for (const label of ['生产', '质检', '对账', '填报']) {
    assert.match(SRC, new RegExp(label))
  }
})
```

- [ ] **Step 2: Run, verify fail**

```
cd frontend && node --test tests/manageEventCard.test.js
```

- [ ] **Step 3: Implement `EventCard.vue`**

```vue
<template>
  <div
    class="xt-event-card"
    :class="{ 'is-fallback': event.isFallback }"
    role="button"
    tabindex="0"
    @click="emit('open', event)"
    @keyup.enter="emit('open', event)"
  >
    <span class="xt-event-card__time">{{ timeLabel }}</span>
    <span class="xt-event-card__pill" :class="`pill-${event.domain}`">{{ domainLabel }}</span>
    <span class="xt-event-card__summary">{{ event.summary }}</span>
    <span class="xt-event-card__arrow" aria-hidden="true">→</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import dayjs from 'dayjs'

const props = defineProps({ event: { type: Object, required: true } })
const emit = defineEmits(['open'])

const DOMAIN_LABELS = { production: '生产', quality: '质检', reconciliation: '对账', reporting: '填报' }
const domainLabel = computed(() => DOMAIN_LABELS[props.event.domain] || props.event.domain)
const timeLabel = computed(() => {
  if (!props.event.occurredAt) return '--:--'
  return dayjs(props.event.occurredAt).format('HH:mm')
})
</script>

<style scoped>
.xt-event-card {
  display: grid;
  grid-template-columns: 60px 56px 1fr 24px;
  align-items: center;
  gap: var(--xt-space-2);
  min-height: 56px;
  padding: var(--xt-space-2) var(--xt-space-3);
  cursor: pointer;
  transition: background-color var(--xt-motion-fast) var(--xt-ease), transform var(--xt-motion-fast) var(--xt-ease);
}
.xt-event-card:hover { background: var(--xt-bg-panel-soft); }
.xt-event-card:active { transform: scale(0.995); }
.xt-event-card.is-fallback {
  background: color-mix(in srgb, var(--xt-color-warning) 8%, var(--xt-bg-panel));
}
.xt-event-card__time { color: var(--xt-text-muted); font-variant-numeric: tabular-nums; font-size: var(--xt-text-sm); }
.xt-event-card__pill {
  justify-self: start;
  padding: 1px var(--xt-space-2);
  border-radius: var(--xt-radius-pill);
  font-size: 10px;
  font-weight: 850;
}
.pill-production { color: var(--xt-color-warning); background: color-mix(in srgb, var(--xt-color-warning) 12%, transparent); }
.pill-quality { color: var(--xt-color-danger); background: color-mix(in srgb, var(--xt-color-danger) 12%, transparent); }
.pill-reconciliation { color: var(--xt-color-accent); background: color-mix(in srgb, var(--xt-color-accent) 12%, transparent); }
.pill-reporting { color: var(--xt-text-muted); background: var(--xt-bg-panel-soft); }
.xt-event-card__summary {
  color: var(--xt-text);
  font-size: var(--xt-text-sm);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.xt-event-card__arrow { color: var(--xt-text-muted); font-size: var(--xt-text-md); }
@media (max-width: 720px) {
  .xt-event-card { grid-template-columns: 50px 56px 1fr 24px; min-height: 64px; }
}
</style>
```

- [ ] **Step 4: Re-run, verify pass**

```
cd frontend && node --test tests/manageEventCard.test.js
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/manage/EventCard.vue frontend/tests/manageEventCard.test.js
git commit -m "feat(alerts): EventCard component with domain pill + token colors"
```

---

## Task 4: DomainFilterChips component

**Files:**
- Create: `frontend/src/components/manage/DomainFilterChips.vue`
- Create: `frontend/tests/manageDomainFilterChips.test.js`

- [ ] **Step 1: Write failing tests**

```js
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const SRC = readFileSync(new URL('../src/components/manage/DomainFilterChips.vue', import.meta.url), 'utf8')

test('DomainFilterChips renders 5 chips: 全部 + 4 domains', () => {
  for (const label of ['全部', '生产', '质检', '对账', '填报']) {
    assert.match(SRC, new RegExp(label))
  }
})

test('DomainFilterChips toggles all by clearing modelValue', () => {
  assert.match(SRC, /modelValue/)
  assert.match(SRC, /update:modelValue/)
  assert.match(SRC, /toggleAll|selectAll|clearDomains/)
})

test('DomainFilterChips count comes from props.counts', () => {
  assert.match(SRC, /props\.counts|counts\.production/)
})

test('DomainFilterChips style block uses --xt-* tokens, no hex', () => {
  const style = SRC.split('<style')[1] || ''
  assert.equal(/#[0-9a-fA-F]{3,6}/.test(style), false)
  assert.match(style, /var\(--xt-/)
})

test('DomainFilterChips uses role=button, accessible', () => {
  assert.match(SRC, /role="button"|tabindex/)
})
```

- [ ] **Step 2: Run, verify fail**

- [ ] **Step 3: Implement `DomainFilterChips.vue`**

```vue
<template>
  <div class="xt-domain-chips" role="group" aria-label="异常域过滤">
    <button
      type="button"
      class="xt-domain-chip"
      :class="{ 'is-active': isAllActive }"
      @click="clearDomains"
    >全部 {{ totalCount }}</button>
    <button
      v-for="d in DOMAIN_DEFS"
      :key="d.key"
      type="button"
      class="xt-domain-chip"
      :class="{ 'is-active': isActive(d.key) }"
      @click="toggle(d.key)"
    >{{ d.label }} {{ counts[d.key] || 0 }}</button>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const DOMAIN_DEFS = [
  { key: 'production', label: '生产' },
  { key: 'quality', label: '质检' },
  { key: 'reconciliation', label: '对账' },
  { key: 'reporting', label: '填报' }
]

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  counts: { type: Object, default: () => ({}) }
})
const emit = defineEmits(['update:modelValue'])

const isAllActive = computed(() => props.modelValue.length === 0)
const totalCount = computed(() => DOMAIN_DEFS.reduce((s, d) => s + (props.counts[d.key] || 0), 0))

function isActive(key) { return props.modelValue.includes(key) }
function clearDomains() { emit('update:modelValue', []) }
function toggle(key) {
  const next = isActive(key) ? props.modelValue.filter((k) => k !== key) : [...props.modelValue, key]
  emit('update:modelValue', next)
}
</script>

<style scoped>
.xt-domain-chips {
  display: flex;
  flex-wrap: nowrap;
  overflow-x: auto;
  gap: var(--xt-space-2);
}
.xt-domain-chip {
  flex: 0 0 auto;
  height: 28px;
  padding: 0 var(--xt-space-3);
  border: 0;
  border-radius: var(--xt-radius-pill);
  background: var(--xt-bg-panel-soft);
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-xs);
  font-weight: 700;
  cursor: pointer;
  transition: background-color var(--xt-motion-fast) var(--xt-ease), color var(--xt-motion-fast) var(--xt-ease);
}
.xt-domain-chip.is-active {
  background: var(--xt-color-accent);
  color: var(--xt-text-on-accent, #fff);
}
@media (hover: hover) {
  .xt-domain-chip:hover { background: var(--xt-bg-panel-soft); color: var(--xt-text); }
  .xt-domain-chip.is-active:hover { background: var(--xt-color-accent); }
}
</style>
```

- [ ] **Step 4: Re-run, verify pass**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/manage/DomainFilterChips.vue frontend/tests/manageDomainFilterChips.test.js
git commit -m "feat(alerts): DomainFilterChips with 全部 toggle + token colors"
```

---

## Task 5: EventTimeline component

**Files:**
- Create: `frontend/src/components/manage/EventTimeline.vue`
- Create: `frontend/tests/manageEventTimeline.test.js`

- [ ] **Step 1: Write failing tests**

```js
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const SRC = readFileSync(new URL('../src/components/manage/EventTimeline.vue', import.meta.url), 'utf8')

test('EventTimeline shows summary line with totalCount and openCount', () => {
  assert.match(SRC, /totalCount/)
  assert.match(SRC, /openCount/)
  assert.match(SRC, /共/)
  assert.match(SRC, /未结/)
})

test('EventTimeline shows 全部已处理 when openCount is 0', () => {
  assert.match(SRC, /全部已处理/)
})

test('EventTimeline empty state copy is 当日无异常', () => {
  assert.match(SRC, /当日无异常/)
})

test('EventTimeline renders EventCard for each event with key=event.id', () => {
  assert.match(SRC, /<EventCard/)
  assert.match(SRC, /:key="event\.id"|:key="evt\.id"/)
})

test('EventTimeline forwards card click to router.push(event.detailRoute)', () => {
  assert.match(SRC, /router\.push|push\(/)
  assert.match(SRC, /detailRoute/)
})

test('EventTimeline style uses xt tokens, no hex', () => {
  const style = SRC.split('<style')[1] || ''
  assert.equal(/#[0-9a-fA-F]{3,6}/.test(style), false)
  assert.match(style, /var\(--xt-/)
})
```

- [ ] **Step 2: Run, verify fail**

- [ ] **Step 3: Implement `EventTimeline.vue`**

```vue
<template>
  <section class="xt-event-timeline">
    <div class="xt-event-timeline__summary">
      <template v-if="events.length === 0">{{ formattedDate }} 当日无异常</template>
      <template v-else>
        {{ formattedDate }} 共 {{ totalCount }} 件，<span v-if="openCount > 0">未结 {{ openCount }}</span><span v-else>全部已处理</span>
      </template>
    </div>
    <p v-if="events.length === 0" class="xt-event-timeline__empty">当日无异常</p>
    <ol v-else class="xt-event-timeline__list">
      <li v-for="evt in events" :key="evt.id" class="xt-event-timeline__row">
        <EventCard :event="evt" @open="onOpen" />
      </li>
    </ol>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import dayjs from 'dayjs'
import EventCard from './EventCard.vue'

const props = defineProps({
  events: { type: Array, default: () => [] },
  totalCount: { type: Number, default: 0 },
  openCount: { type: Number, default: 0 },
  targetDate: { type: String, default: '' }
})

const router = useRouter()

const formattedDate = computed(() => {
  if (!props.targetDate) return ''
  const d = dayjs(props.targetDate)
  return `${d.month() + 1} 月 ${d.date()} 日`
})

function onOpen(event) {
  if (event && event.detailRoute) router.push(event.detailRoute)
}
</script>

<style scoped>
.xt-event-timeline {
  background: var(--xt-bg-panel);
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-md);
  display: flex;
  flex-direction: column;
}
.xt-event-timeline__summary {
  padding: var(--xt-space-2) var(--xt-space-3);
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-sm);
  border-bottom: 1px solid var(--xt-border);
}
.xt-event-timeline__empty {
  margin: 0;
  padding: var(--xt-space-6) var(--xt-space-3);
  text-align: center;
  color: var(--xt-text-muted);
  font-size: var(--xt-text-sm);
}
.xt-event-timeline__list { list-style: none; margin: 0; padding: 0; }
.xt-event-timeline__row { border-bottom: 1px solid var(--xt-border); }
.xt-event-timeline__row:last-child { border-bottom: 0; }
</style>
```

- [ ] **Step 4: Re-run, verify pass**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/manage/EventTimeline.vue frontend/tests/manageEventTimeline.test.js
git commit -m "feat(alerts): EventTimeline list shell + summary + empty state"
```

---

## Task 6: AlertsPage rewrite

**Files:**
- Modify: `frontend/src/views/manage/alerts/AlertsPage.vue` (full rewrite)
- Create: `frontend/tests/manageAlertsPage.test.js`

- [ ] **Step 1: Write failing tests**

```js
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const SRC = readFileSync(new URL('../src/views/manage/alerts/AlertsPage.vue', import.meta.url), 'utf8')

test('AlertsPage uses useAlertsTimeline composable', () => {
  assert.match(SRC, /useAlertsTimeline/)
})

test('AlertsPage imports DateSwitcher, DomainFilterChips, EventTimeline', () => {
  assert.match(SRC, /DateSwitcher/)
  assert.match(SRC, /DomainFilterChips/)
  assert.match(SRC, /EventTimeline/)
})

test('AlertsPage initial domains[] driven from route ?domain= query', () => {
  assert.match(SRC, /route\.query\.domain|query\.domain/)
})

test('AlertsPage maps legacy ?surface= to domains on mount', () => {
  for (const s of ['anomaly', 'quality', 'reconciliation']) {
    assert.match(SRC, new RegExp(s))
  }
  assert.match(SRC, /surface/)
})

test('AlertsPage h1 is 异常', () => {
  assert.match(SRC, /<h1>异常<\/h1>/)
})

test('AlertsPage style uses xt tokens, no hex', () => {
  const style = SRC.split('<style')[1] || ''
  assert.equal(/#[0-9a-fA-F]{3,6}/.test(style), false)
  assert.match(style, /var\(--xt-/)
})

test('AlertsPage forbids placeholder copy', () => {
  for (const bad of ['TODO', '暂未', '敬请期待', 'Coming soon']) {
    assert.equal(new RegExp(bad).test(SRC), false, `forbidden copy: ${bad}`)
  }
})

test('AlertsPage uses computed openCount filtering by status open', () => {
  assert.match(SRC, /openCount/)
  assert.match(SRC, /status === 'open'|=== 'open'/)
})
```

- [ ] **Step 2: Run, verify fail**

- [ ] **Step 3: Rewrite `AlertsPage.vue`**

```vue
<template>
  <section class="xt-alerts" data-testid="manage-alerts">
    <header class="xt-alerts__header">
      <h1>异常</h1>
      <DateSwitcher
        :model-value="timeline.targetDate.value"
        :loading="timeline.loading.value"
        :freshness="timeline.freshnessStatus.value"
        @step="timeline.stepDate"
        @refresh="timeline.load"
      />
    </header>
    <DomainFilterChips
      :model-value="timeline.domains.value"
      :counts="timeline.domainCounts.value"
      @update:model-value="onDomainsChange"
    />
    <EventTimeline
      :events="timeline.filteredEvents.value"
      :total-count="timeline.filteredEvents.value.length"
      :open-count="openCount"
      :target-date="timeline.targetDate.value"
    />
  </section>
</template>

<script setup>
import { computed, onMounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import DateSwitcher from '../../../components/manage/DateSwitcher.vue'
import DomainFilterChips from '../../../components/manage/DomainFilterChips.vue'
import EventTimeline from '../../../components/manage/EventTimeline.vue'
import { useAlertsTimeline } from '../../../composables/useAlertsTimeline.js'

const route = useRoute()
const router = useRouter()
const timeline = useAlertsTimeline()

const SURFACE_TO_DOMAIN = { anomaly: 'production', quality: 'quality', reconciliation: 'reconciliation' }

function readDomainsFromRoute() {
  const surface = route.query.surface
  if (surface && SURFACE_TO_DOMAIN[surface]) return [SURFACE_TO_DOMAIN[surface]]
  const d = route.query.domain
  if (Array.isArray(d)) return d
  if (typeof d === 'string' && d.length) return d.split(',').filter(Boolean)
  return []
}

function syncRouteFromDomains(domains) {
  const next = { ...route.query }
  delete next.surface
  if (domains.length === 0) delete next.domain
  else next.domain = domains.join(',')
  router.replace({ query: next })
}

function onDomainsChange(next) {
  timeline.domains.value = next
  syncRouteFromDomains(next)
}

const openCount = computed(
  () => timeline.filteredEvents.value.filter((e) => e.status === 'open').length
)

onMounted(() => {
  timeline.domains.value = readDomainsFromRoute()
  if (route.query.surface) syncRouteFromDomains(timeline.domains.value)
  timeline.load()
})

watch(() => route.query, () => {
  const next = readDomainsFromRoute()
  if (JSON.stringify(next) !== JSON.stringify(timeline.domains.value)) {
    timeline.domains.value = next
  }
})
</script>

<style scoped>
.xt-alerts { display: flex; flex-direction: column; gap: var(--xt-space-4); }
.xt-alerts__header { display: flex; align-items: center; justify-content: space-between; gap: var(--xt-space-3); flex-wrap: wrap; }
.xt-alerts__header h1 { margin: 0; font-size: var(--xt-text-2xl); font-weight: 850; color: var(--xt-text); }
@media (max-width: 720px) {
  .xt-alerts__header { flex-direction: column; align-items: stretch; }
}
</style>
```

- [ ] **Step 4: Run unit tests**

```
cd frontend && node --test tests/manageAlertsPage.test.js
```
Expected: all 8 tests pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/manage/alerts/AlertsPage.vue frontend/tests/manageAlertsPage.test.js
git commit -m "feat(alerts): rewrite AlertsPage as single-column timeline"
```

---

## Task 7: Router — legacy route + ?surface= redirect

**Files:**
- Modify: `frontend/src/router/index.js`

- [ ] **Step 1: Read existing router**

```
cat frontend/src/router/index.js
```
Locate the `/manage/alerts` route definition.

- [ ] **Step 2: Add legacy route + redirect**

In the manage children array, after the existing `alerts` route, add:

```js
{
  path: 'alerts/legacy',
  name: 'manage-alerts-legacy',
  component: () => import('../views/manage/alerts/AlertsPage.legacy.vue'),
  meta: { requiresAuth: true, group: 'manage' }
},
```

Then create the new shim file `frontend/src/views/manage/alerts/AlertsPage.legacy.vue` (lifts the old switch logic out of `AlertsPage.vue` so legacy deep-links keep rendering):

```vue
<template>
  <section class="xt-alerts-legacy" data-testid="manage-alerts-legacy">
    <component :is="activeSurfaceComponent" />
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'

import AnomalyReview from '../../attendance/AnomalyReview.vue'
import QualityCenter from '../../quality/QualityCenter.vue'
import ReconciliationCenter from '../../reconciliation/ReconciliationCenter.vue'

const route = useRoute()
const activeSurfaceComponent = computed(() => {
  if (route.query.surface === 'reconciliation') return ReconciliationCenter
  if (route.query.surface === 'quality') return QualityCenter
  return AnomalyReview
})
</script>
```

- [ ] **Step 3: Verify routes typecheck (no test framework runs here, do a smoke build)**

```
cd frontend && npx vite build --mode development 2>&1 | tail -20
```
Expected: build succeeds, no module resolution errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/router/index.js frontend/src/views/manage/alerts/AlertsPage.legacy.vue
git commit -m "feat(alerts): add /manage/alerts/legacy route mounting old surfaces"
```

---

## Task 8: TodayPage KeyEventList query update

**Files:**
- Modify: `frontend/src/views/manage/today/TodayPage.vue` (KeyEventList target route)
- Modify: `frontend/src/components/manage/_keyEvents.js` (where SLOTS hard-code `?surface=`)

- [ ] **Step 1: Locate the SLOTS array**

```
cd frontend && grep -n "surface=" src/components/manage/_keyEvents.js
```

- [ ] **Step 2: Update routes**

Edit `frontend/src/components/manage/_keyEvents.js`. For each SLOT entry:

```diff
-    route: '/manage/alerts?surface=anomaly'
+    route: '/manage/alerts?domain=production'
```
```diff
-    route: '/manage/alerts?surface=reconciliation'
+    route: '/manage/alerts?domain=reconciliation'
```
```diff
-    route: '/manage/alerts?surface=anomaly'
+    route: '/manage/alerts?domain=reporting'
```
(Apply the production / reconciliation / reporting mapping per the three KeyEvent slots in the existing file.)

- [ ] **Step 3: Update the existing _keyEvents test if it asserts old query**

```
cd frontend && grep -rn "surface=" tests/ | head
```
For any failing test referencing `?surface=anomaly` etc., update assertion strings to the new `?domain=…` values.

- [ ] **Step 4: Run unit tests, verify pass**

```
cd frontend && npm test
```
Expected: full unit suite green (no regressions).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/manage/_keyEvents.js frontend/tests
git commit -m "refactor(today): KeyEvent slot routes use ?domain= for new alerts page"
```

---

## Task 9: E2E mocks + spec

**Files:**
- Modify: `frontend/e2e/helpers/review-mocks.js` — add `mockQualityIssues()` and `mockReconciliationItems()` helpers
- Create: `frontend/e2e/manage-alerts-timeline.spec.js`

- [ ] **Step 1: Add mock helpers**

In `review-mocks.js`, add (do not delete existing helpers):

```js
export async function mockQualityIssues(page, body = []) {
  await page.route('**/api/quality/issues**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
  )
}

export async function mockReconciliationItems(page, body = []) {
  await page.route('**/api/reconciliation/items**', (route) =>
    route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(body) })
  )
}

export async function mockQualityFailure(page) {
  await page.route('**/api/quality/issues**', (route) =>
    route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"boom"}' })
  )
}
```

Also extend the existing `factory-director` mock body to include sample `recent_items`, `returned_items`, `reminder_items` (if not already present from Phase B). Inspect first:

```
cd frontend && grep -n "recent_items\|returned_items\|reminder_items" e2e/helpers/review-mocks.js
```

If absent, add to the existing payload:

```js
exception_lane: {
  recent_items: [
    { id: 'p1', occurred_at: '2026-05-19T10:23:00', summary: '一车间早班产量异常 -2.4%' }
  ],
  returned_items: [
    { id: 'r1', occurred_at: '2026-05-19T08:15:00', summary: '一车间晚班 未填报' }
  ],
  reminder_items: [],
  // ...keep existing counts
}
```

- [ ] **Step 2: Write the e2e spec**

Create `frontend/e2e/manage-alerts-timeline.spec.js`:

```js
import { test, expect } from '@playwright/test'
import { mockFactoryDashboard, mockQualityIssues, mockReconciliationItems, mockQualityFailure } from './helpers/review-mocks.js'
import { signInAsManager } from './helpers/auth.js'

test.describe('manage alerts timeline (Phase C-1)', () => {
  test.beforeEach(async ({ page }) => {
    await mockFactoryDashboard(page)
    await mockQualityIssues(page, [
      { id: 'q1', occurred_at: '2026-05-19T11:00:00', summary: '抽检不合格' }
    ])
    await mockReconciliationItems(page, [
      { id: 'rc1', occurred_at: '2026-05-19T09:50:00', summary: '3 笔过磅与系统差异' }
    ])
    await signInAsManager(page)
  })

  test('today key event 对账 → /manage/alerts?domain=reconciliation, chip selected, list filtered', async ({ page }) => {
    await page.goto('/manage/today')
    await page.getByText('对账未结').click()
    await expect(page).toHaveURL(/\/manage\/alerts\?domain=reconciliation/)
    await expect(page.getByRole('button', { name: /对账 \d/ })).toHaveClass(/is-active/)
    await expect(page.getByText('过磅与系统差异')).toBeVisible()
    await expect(page.getByText('抽检不合格')).toHaveCount(0)
  })

  test('date switcher refreshes the list', async ({ page }) => {
    await page.goto('/manage/alerts')
    await expect(page.getByText(/共 \d+ 件/)).toBeVisible()
    await page.getByRole('button', { name: /上一日|←/ }).click()
    await expect(page.locator('.xt-event-timeline__summary')).toContainText('共')
  })

  test('multi-select chips filter the list', async ({ page }) => {
    await page.goto('/manage/alerts')
    await page.getByRole('button', { name: /生产 \d/ }).click()
    await page.getByRole('button', { name: /对账 \d/ }).click()
    await expect(page.getByText('抽检不合格')).toHaveCount(0)
    await expect(page.getByText('产量异常')).toBeVisible()
    await expect(page.getByText('过磅与系统差异')).toBeVisible()
  })

  test('quality 500 → fallback card injected', async ({ page }) => {
    await mockQualityFailure(page)
    await page.goto('/manage/alerts')
    await expect(page.getByText('加载失败，点击查看老页')).toBeVisible()
  })

  test('card click navigates to legacy surface', async ({ page }) => {
    await page.goto('/manage/alerts')
    await page.getByText('产量异常').click()
    await expect(page).toHaveURL(/\/manage\/alerts\/legacy\?surface=anomaly/)
  })
})
```

- [ ] **Step 3: Run the new spec**

```
cd frontend && npx playwright test e2e/manage-alerts-timeline.spec.js --project=chromium
```
Expected: 5/5 pass.

- [ ] **Step 4: Run regression alongside Phase A+B specs**

```
cd frontend && npx playwright test e2e/manage-shell.spec.js e2e/manage-today-production.spec.js e2e/owner-three-tab-skeleton.spec.js e2e/manage-alerts-timeline.spec.js --project=chromium
```
Expected: 17/17 pass (12 baseline + 5 new).

- [ ] **Step 5: Commit**

```bash
git add frontend/e2e/helpers/review-mocks.js frontend/e2e/manage-alerts-timeline.spec.js
git commit -m "test(alerts): e2e covering domain filter, fallback card, legacy deep-link"
```

---

## Task 10: Acceptance pass + cleanup notes

**Files:**
- Create: `docs/superpowers/plans/2026-05-25-phase-c1-acceptance.md`

- [ ] **Step 1: Run full unit suite**

```
cd frontend && npm test 2>&1 | tail -10
```
Expected: previous baseline (311) + ~30 new tests across the 6 new test files = 340+ pass.

- [ ] **Step 2: Run full e2e suite**

```
cd frontend && npx playwright test --project=chromium 2>&1 | tail -10
```
Expected: 17/17 pass (no regressions).

- [ ] **Step 3: Walk the spec §8 acceptance list (19 items)**

For each of the 19 items in spec §8, write evidence (file path + commit / test name). Save as `docs/superpowers/plans/2026-05-25-phase-c1-acceptance.md` with the same table format Phase B used (`docs/superpowers/plans/2026-05-23-phase-b-acceptance-and-cleanup.md`).

- [ ] **Step 4: Commit acceptance doc**

```bash
git add docs/superpowers/plans/2026-05-25-phase-c1-acceptance.md
git commit -m "docs(plans): Phase C-1 acceptance + cleanup notes"
```

- [ ] **Step 5: Hand off to finishing-a-development-branch**

The branch is ready for PR. Invoke `superpowers:finishing-a-development-branch`. Note: `codex/phase-c1-alerts-timeline` was branched off Phase A+B, not main. Before opening PR, confirm A+B has merged and rebase:

```bash
git fetch origin
git rebase origin/main
```
Resolve any conflicts (most likely in `_keyEvents.js` query strings or `review-mocks.js` mock body — these are the files Phase A+B might also touch on main).

If A+B is still in PR review, hold the C-1 PR until A+B merges to keep history linear.

---

## Self-Review

**1. Spec coverage:**

| Spec section | Covered by task |
|---|---|
| §3 Architecture | Tasks 2, 6, 7 |
| §4 Components: useAlertsTimeline | Task 2 |
| §4 Components: _alertEventNormalize | Task 1 |
| §4 Components: DomainFilterChips | Task 4 |
| §4 Components: EventTimeline | Task 5 |
| §4 Components: EventCard | Task 3 |
| §4 Modify AlertsPage.vue | Task 6 |
| §4 Modify router/index.js + legacy route | Task 7 |
| §4 Modify TodayPage.vue / _keyEvents.js | Task 8 |
| §4 Modify e2e mocks | Task 9 |
| §5 Field mapping + fallbacks | Task 1 |
| §5 Sorting | Task 1 (mergeAndSort) |
| §5 Promise.allSettled isolation | Task 2 |
| §5 freshnessStatus | Task 2 |
| §5 domainCounts | Task 2 |
| §5 Domain filtering | Task 2 (filteredEvents) |
| §6 Visual: skeleton + chip + card + summary | Tasks 3, 4, 5, 6 |
| §6 Color tokens (color-mix) | Task 3 |
| §6 Responsive breakpoint | Tasks 3, 6 |
| §6 Fallback card style | Tasks 2, 3 |
| §7 Unit tests (6 files) | Tasks 1-6 |
| §7 E2E spec (5 tests) | Task 9 |
| §7 Mock additivity | Task 9 |
| §8 Acceptance items 1-19 | Task 10 |

All 19 acceptance items trace to a task. No gaps.

**2. Placeholder scan:** No TBD / TODO / "implement later". Every code step has full code blocks. Every test step has full test code.

**3. Type consistency:** `AlertEvent` shape is fixed in Task 1 (`id`, `domain`, `occurredAt`, `summary`, `detailRoute`, `status`, `isFallback?`) and consumed verbatim by Tasks 2-6. Composable's exposed names (`targetDate`, `domains`, `events`, `filteredEvents`, `domainCounts`, `loading`, `lastError`, `freshnessStatus`, `load`, `stepDate`) match between Task 2 implementation and Task 6 consumer. `DomainFilterChips` props (`modelValue`, `counts`) and emit (`update:modelValue`) match between Task 4 and Task 6. `EventCard` emits `open` and `EventTimeline` listens for it via `@open` — consistent across Tasks 3, 5.

Plan complete and saved to `docs/superpowers/plans/2026-05-24-phase-c1-alerts-timeline.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, two-stage review between tasks, fast iteration

**2. Inline Execution** — execute tasks in this session using executing-plans, batch with checkpoints

Which approach?
