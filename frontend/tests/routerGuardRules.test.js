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
    resolveGuardDecision({
      to: route(),
      auth: auth({
        isFillOnlyRole: true,
        canAccessFillSurface: true,
        canAccessReviewSurface: false,
      }),
    }),
    { name: 'mobile-entry' }
  )
})

test('resolveGuardDecision blocks non-admin users from admin access', () => {
  assert.deepEqual(
    resolveGuardDecision({
      to: route({ meta: { requiresAuth: true, zone: 'manage', access: 'admin' } }),
      auth: auth({ defaultSurface: 'review' }),
    }),
    { name: 'review-overview-home' }
  )
})

test('resolveGuardDecision sends compact fill-capable users to entry unless desktop is requested', () => {
  const compactAuth = auth({ canAccessFillSurface: true, canAccessReviewSurface: true })
  assert.deepEqual(
    resolveGuardDecision({ to: route(), auth: compactAuth, compactClient: true }),
    { name: 'mobile-entry' }
  )
  assert.equal(
    resolveGuardDecision({ to: route({ query: { desktop: '1' } }), auth: compactAuth, compactClient: true }),
    true
  )
})

test('resolveGuardDecision allows runtime auth code into mobile entry before token exists', () => {
  assert.equal(
    resolveGuardDecision({
      to: route({
        name: 'mobile-entry',
        fullPath: '/entry?authCode=abc',
        query: { authCode: 'abc' },
        meta: { requiresAuth: true, zone: 'entry', access: 'entry' },
      }),
      auth: auth({ token: '', user: null, canAccessFillSurface: true }),
      hasRuntimeAuthCode: true,
    }),
    true
  )
  assert.equal(resolveRuntimeAuthCode({ auth_code: 'dt-code' }), 'dt-code')
})
