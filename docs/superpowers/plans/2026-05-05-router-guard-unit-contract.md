# Router Guard Unit Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close audit item F11 by giving the router guard a fast unit-tested decision layer for fill-only, admin, compact-client, and DingTalk runtime auth-code behavior.

**Architecture:** Extract the pure guard rules from `frontend/src/router/index.js` into `frontend/src/router/guardRules.js`. Keep `installRouterGuards` responsible for Vue Router registration, profile fetching, and `document.title`, while the new helper decides whether navigation is allowed or redirected.

**Tech Stack:** Vue Router 4 runtime wiring, native Node.js test runner for pure guard decisions.

---

### Task 1: Add Red Tests For Guard Decisions

**Files:**
- Create: `frontend/tests/routerGuardRules.test.js`
- Create: `frontend/src/router/guardRules.js`

- [x] **Step 1: Write failing tests**

```js
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  resolveGuardDecision,
  resolveRuntimeAuthCode,
} from '../src/router/guardRules.js'

function route(overrides = {}) {
  return {
    name: 'review-overview-home',
    fullPath: '/manage/overview?x=1',
    query: {},
    meta: { requiresAuth: true, zone: 'manage', access: 'review' },
    matched: [],
    ...overrides,
  }
}

function auth(overrides = {}) {
  return {
    token: 'token',
    user: { id: 1 },
    role: 'manager',
    isFillOnlyRole: false,
    canAccessFillSurface: false,
    canAccessReviewSurface: true,
    canAccessReviewDesk: true,
    adminSurface: false,
    defaultSurface: 'review',
    ...overrides,
  }
}

test('resolveGuardDecision redirects fill-only users away from manage routes', () => {
  assert.deepEqual(
    resolveGuardDecision({ to: route(), auth: auth({ isFillOnlyRole: true, canAccessFillSurface: true, canAccessReviewSurface: false }) }),
    { name: 'mobile-entry' }
  )
})

test('resolveGuardDecision blocks non-admin users from admin access', () => {
  assert.deepEqual(
    resolveGuardDecision({ to: route({ meta: { requiresAuth: true, zone: 'manage', access: 'admin' } }), auth: auth({ defaultSurface: 'review' }) }),
    { name: 'review-overview-home' }
  )
})

test('resolveGuardDecision sends compact fill-capable users to entry unless desktop is requested', () => {
  const compactAuth = auth({ canAccessFillSurface: true, canAccessReviewSurface: true })
  assert.deepEqual(resolveGuardDecision({ to: route(), auth: compactAuth, compactClient: true }), { name: 'mobile-entry' })
  assert.equal(resolveGuardDecision({ to: route({ query: { desktop: '1' } }), auth: compactAuth, compactClient: true }), true)
})

test('resolveGuardDecision allows runtime auth code into mobile entry before token exists', () => {
  assert.equal(
    resolveGuardDecision({
      to: route({ name: 'mobile-entry', fullPath: '/entry?authCode=abc', query: { authCode: 'abc' }, meta: { requiresAuth: true, zone: 'entry', access: 'entry' } }),
      auth: auth({ token: '', user: null, canAccessFillSurface: true }),
      hasRuntimeAuthCode: true,
    }),
    true
  )
  assert.equal(resolveRuntimeAuthCode({ auth_code: 'dt-code' }), 'dt-code')
})
```

- [x] **Step 2: Run red test**

Run: `cd frontend; node --test tests/routerGuardRules.test.js`

Expected: FAIL because `frontend/src/router/guardRules.js` does not exist yet.

### Task 2: Extract Guard Rules And Wire Router

**Files:**
- Modify: `frontend/src/router/guardRules.js`
- Modify: `frontend/src/router/index.js`

- [x] **Step 1: Implement pure guard helper**

Move the current helper logic for runtime auth code, compact detection, DingTalk detection, mobile preference, landing selection, and guard redirects into `guardRules.js`.

- [x] **Step 2: Call helper from `installRouterGuards`**

Keep profile fetching inside `installRouterGuards`, then call `resolveGuardDecision(...)`. Set `document.title` only when the decision is `true`, matching the existing allowed-navigation behavior.

- [x] **Step 3: Run unit tests**

Run: `cd frontend; node --test tests/routerGuardRules.test.js`

Expected: PASS.

### Task 3: Close Audit Item And Verify

**Files:**
- Modify: `docs/audits/2026-05-02-cleanup-round2-test-audit.md`

- [x] **Step 1: Move F11 to fixed list**

Add `R27` describing the extracted guard rules and unit coverage. Remove F11 from the pending table.

- [x] **Step 2: Run regression checks**

Run:
- `npm --prefix frontend run test:unit`
- `npm --prefix frontend run build`
- `python -m pytest backend/tests/test_mobile_entry_copy_consistency.py -q`
- `git diff --check`

Expected: all commands pass.

Verification note: moving landing logic from `router/index.js` to `router/guardRules.js` required updating one backend static contract test to inspect the new guard file. Focused backend contract, frontend unit tests, frontend build, diff check, and backend full pytest passed.

- [x] **Step 3: Review diff and commit**

Review `git diff`, ensure the change is limited to guard rules/tests/audit/plan, then commit with:

```bash
git add docs/superpowers/plans/2026-05-05-router-guard-unit-contract.md frontend/tests/routerGuardRules.test.js frontend/src/router/guardRules.js frontend/src/router/index.js docs/audits/2026-05-02-cleanup-round2-test-audit.md
git commit -m "test: 覆盖路由守卫决策"
```
