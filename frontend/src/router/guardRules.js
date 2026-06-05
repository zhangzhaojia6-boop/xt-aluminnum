export function resolveRuntimeAuthCode(query = {}) {
  const candidates = [query.authCode, query.auth_code, query.code]
  return candidates.find((value) => typeof value === 'string' && value.trim()) || ''
}

export function isCompactClient(windowRef = globalThis.window) {
  if (!windowRef) return false
  const userAgent = windowRef.navigator?.userAgent || ''
  const matchesViewport = typeof windowRef.matchMedia === 'function' && windowRef.matchMedia('(max-width: 900px)').matches
  return matchesViewport || /MicroMessenger|wxwork|DingTalk|iPhone|iPad|Android|Mobile/i.test(userAgent)
}

export function isDingTalkRuntimeClient(windowRef = globalThis.window) {
  if (!windowRef) return false
  const userAgent = windowRef.navigator?.userAgent || ''
  return Boolean(windowRef.dd) || /DingTalk/i.test(userAgent)
}

export function resolveRouteAccess(to = {}) {
  const matchedAccess = [...(to.matched || [])].reverse().find((record) => record.meta?.access)?.meta.access
  return to.meta?.access || matchedAccess
}

function configLanding(authStore) {
  if (authStore.adminSurface) return { name: 'admin-ops-reliability' }
  return { name: 'login' }
}

function reviewLanding(authStore) {
  if (authStore.isWorkshopDirector) return { name: 'manage-workshop-dashboard' }
  if (authStore.canAccessReviewSurface) return { name: 'manage-today' }
  if (authStore.canAccessFactoryDashboard) return { name: 'manage-production' }
  if (authStore.canAccessWorkshopDashboard) return { name: 'manage-workshop-dashboard' }
  const config = configLanding(authStore)
  if (config.name !== 'login') return config
  return { name: 'login' }
}

function adminLanding(authStore) {
  if (authStore.adminSurface) return { name: 'admin-ops-reliability' }
  return { name: 'login' }
}

function defaultLanding(authStore, compactClient) {
  if (compactClient && authStore.isWorkshopDirector && authStore.canAccessWorkshopDashboard) return { name: 'manage-workshop-dashboard' }
  if (compactClient && (authStore.canAccessReviewSurface || authStore.adminSurface)) return { name: 'manage-today' }
  if (compactClient && authStore.canAccessFillSurface) return { name: 'mobile-entry' }
  if (authStore.canAccessFillSurface && !authStore.canAccessReviewSurface) return { name: 'mobile-entry' }
  if (authStore.defaultSurface === 'admin') return adminLanding(authStore)
  if (authStore.defaultSurface === 'review') return reviewLanding(authStore)
  const review = reviewLanding(authStore)
  if (review.name !== 'login') return review
  if (authStore.canAccessFillSurface) return { name: 'mobile-entry' }
  return { name: 'login' }
}

function prefersMobileSurface(authStore, to, compactClient) {
  if (!compactClient || !authStore.canAccessFillSurface) return false
  if (to.meta.zone === 'entry' || to.name === 'login') return false
  if (typeof to.query?.desktop === 'string' && to.query.desktop === '1') return false
  if (authStore.canAccessReviewSurface || authStore.adminSurface) return false
  return to.meta.zone === 'manage' || to.meta.zone === 'review' || to.meta.zone === 'desktop'
}

const COMPACT_MANAGE_ROUTE_NAMES = new Set(['manage-live', 'manage-today'])

function prefersDesktopOverride(to) {
  return typeof to.query?.desktop === 'string' && to.query.desktop === '1'
}

function resolveCompactManageDecision(authStore, to, access, compactClient) {
  if (!compactClient || to.meta.zone !== 'manage') return null
  if (prefersDesktopOverride(to)) return null
  if (authStore.isWorkshopDirector) {
    return access === 'workshop_dashboard' ? true : { name: 'manage-workshop-dashboard' }
  }
  if (authStore.canAccessReviewSurface || authStore.adminSurface) {
    return COMPACT_MANAGE_ROUTE_NAMES.has(to.name) ? true : { name: 'manage-today' }
  }
  return null
}

export function resolveGuardDecision({
  to,
  auth,
  access = resolveRouteAccess(to),
  hasRuntimeAuthCode = false,
  compactClient = false,
  profileReady = true,
}) {
  if (auth.token && to.name === 'login') {
    return defaultLanding(auth, compactClient)
  }

  if (access === 'public') {
    return true
  }

  if (to.meta.requiresAuth && !auth.token) {
    if (hasRuntimeAuthCode) return true
    return { name: 'login', query: { redirect: to.fullPath } }
  }

  if (!auth.token) {
    return true
  }

  if (!profileReady) {
    return null
  }

  if (auth.isFillOnlyRole && to.meta.zone !== 'entry' && to.name !== 'login') {
    return { name: 'mobile-entry' }
  }

  const compactManageDecision = resolveCompactManageDecision(auth, to, access, compactClient)
  if (compactManageDecision !== null) {
    return compactManageDecision
  }

  if (prefersMobileSurface(auth, to, compactClient)) {
    return { name: 'mobile-entry' }
  }

  if (to.meta.zone === 'entry' && !auth.canAccessFillSurface) {
    return auth.canAccessReviewSurface ? reviewLanding(auth) : { name: 'login' }
  }
  if (auth.isWorkshopDirector && to.meta.zone === 'manage' && access !== 'workshop_dashboard' && access !== 'admin') {
    return { name: 'manage-workshop-dashboard' }
  }
  if ((to.meta.zone === 'review' || to.meta.zone === 'manage') && access !== 'admin' && !auth.canAccessReviewSurface) {
    return auth.canAccessFillSurface ? { name: 'mobile-entry' } : { name: 'login' }
  }
  if (access === 'admin' && !auth.adminSurface) {
    return defaultLanding(auth, compactClient)
  }
  if (to.meta.zone === 'desktop' && !auth.adminSurface) {
    return defaultLanding(auth, compactClient)
  }

  if (access === 'entry' && !auth.canAccessFillSurface) {
    return defaultLanding(auth, compactClient)
  }
  if (access === 'review' && !auth.canAccessReviewSurface) {
    return defaultLanding(auth, compactClient)
  }
  if (access === 'review' && !auth.canAccessReviewDesk) {
    return defaultLanding(auth, compactClient)
  }
  if (access === 'review_surface' && !auth.canAccessReviewSurface) {
    return defaultLanding(auth, compactClient)
  }
  if (access === 'desktop_config' && !auth.adminSurface) {
    return defaultLanding(auth, compactClient)
  }
  if (access === 'manager' && !(auth.isAdmin || auth.isManager)) {
    return defaultLanding(auth, compactClient)
  }
  if (access === 'admin_strict' && !auth.isAdmin) {
    return defaultLanding(auth, compactClient)
  }
  if (access === 'factory_dashboard' && !auth.canAccessFactoryDashboard) {
    return defaultLanding(auth, compactClient)
  }
  if (access === 'workshop_dashboard' && !auth.canAccessWorkshopDashboard) {
    return defaultLanding(auth, compactClient)
  }
  if (access === 'statistics_dashboard' && !auth.canAccessStatisticsDashboard) {
    return defaultLanding(auth, compactClient)
  }

  return true
}
