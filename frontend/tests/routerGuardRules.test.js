import test from 'node:test'
import assert from 'node:assert/strict'

import {
  resolveGuardDecision,
  resolveRuntimeAuthCode,
} from '../src/router/guardRules.js'

function route(overrides = {}) {
  return {
    name: 'manage-today',
    fullPath: '/manage/today?x=1',
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
    { name: 'manage-today' }
  )
})

test('resolveGuardDecision lands factory users on production and workshop users on workshop dashboard', () => {
  const loginRoute = route({
    name: 'login',
    fullPath: '/login',
    meta: { requiresAuth: false, zone: 'public', access: 'public' },
  })

  assert.deepEqual(
    resolveGuardDecision({
      to: loginRoute,
      auth: auth({ canAccessReviewSurface: false, canAccessFactoryDashboard: true }),
    }),
    { name: 'manage-production' }
  )
  assert.deepEqual(
    resolveGuardDecision({
      to: loginRoute,
      auth: auth({ canAccessReviewSurface: false, canAccessWorkshopDashboard: true }),
    }),
    { name: 'manage-workshop-dashboard' }
  )
})

test('resolveGuardDecision keeps workshop directors inside own dashboard', () => {
  assert.deepEqual(
    resolveGuardDecision({
      to: route(),
      auth: auth({ isWorkshopDirector: true }),
    }),
    { name: 'manage-workshop-dashboard' }
  )
  assert.equal(
    resolveGuardDecision({
      to: route({ name: 'manage-workshop-dashboard', meta: { requiresAuth: true, zone: 'manage', access: 'workshop_dashboard' } }),
      auth: auth({ isWorkshopDirector: true, canAccessWorkshopDashboard: true }),
    }),
    true
  )
})

test('resolveGuardDecision keeps compact review users on the mobile management allowlist', () => {
  const compactAuth = auth({ canAccessFillSurface: true, canAccessReviewSurface: true })

  assert.equal(
    resolveGuardDecision({ to: route({ name: 'manage-live' }), auth: compactAuth, compactClient: true }),
    true
  )
  assert.equal(
    resolveGuardDecision({ to: route({ name: 'manage-today' }), auth: compactAuth, compactClient: true }),
    true
  )
  assert.deepEqual(
    resolveGuardDecision({ to: route({ name: 'manage-production' }), auth: compactAuth, compactClient: true }),
    { name: 'manage-today' }
  )
  assert.deepEqual(
    resolveGuardDecision({ to: route({ name: 'manage-daily-report' }), auth: compactAuth, compactClient: true }),
    { name: 'manage-today' }
  )
  assert.deepEqual(
    resolveGuardDecision({ to: route({ name: 'admin-ops-reliability', meta: { requiresAuth: true, zone: 'manage', access: 'admin' } }), auth: auth({ adminSurface: true, canAccessFillSurface: true }), compactClient: true }),
    { name: 'manage-today' }
  )
})

test('resolveGuardDecision keeps compact workshop directors inside the workshop dashboard', () => {
  const directorAuth = auth({
    isWorkshopDirector: true,
    canAccessFillSurface: true,
    canAccessWorkshopDashboard: true,
  })

  assert.deepEqual(
    resolveGuardDecision({ to: route({ name: 'manage-live' }), auth: directorAuth, compactClient: true }),
    { name: 'manage-workshop-dashboard' }
  )
  assert.equal(
    resolveGuardDecision({
      to: route({ name: 'manage-workshop-dashboard', meta: { requiresAuth: true, zone: 'manage', access: 'workshop_dashboard' } }),
      auth: directorAuth,
      compactClient: true,
    }),
    true
  )
})

test('resolveGuardDecision sends compact fill-only users to entry', () => {
  const compactAuth = auth({ canAccessFillSurface: true, canAccessReviewSurface: true })
  const fillOnlyAuth = auth({
    isFillOnlyRole: true,
    canAccessFillSurface: true,
    canAccessReviewSurface: false,
  })

  assert.deepEqual(
    resolveGuardDecision({ to: route(), auth: fillOnlyAuth, compactClient: true }),
    { name: 'mobile-entry' }
  )
  assert.deepEqual(
    resolveGuardDecision({
      to: route({
        name: 'admin-ops-reliability',
        query: { desktop: '1' },
        meta: { requiresAuth: true, zone: 'manage', access: 'admin' },
      }),
      auth: compactAuth,
      compactClient: true,
    }),
    { name: 'manage-today' }
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
