import { apiBaseUrl } from './index.js'

const ERRORS_URL = `${apiBaseUrl}/telemetry/errors`
const PERF_URL = `${apiBaseUrl}/telemetry/perf`

function postBeacon(url, payload) {
  if (typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
    try {
      const blob = new Blob([JSON.stringify(payload)], { type: 'application/json' })
      if (navigator.sendBeacon(url, blob)) return
    } catch (_) {
      // fall through to fetch
    }
  }
  if (typeof fetch === 'function') {
    fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      keepalive: true,
      credentials: 'same-origin',
    }).catch(() => {})
  }
}

export function reportFrontendError(payload) {
  const userAgent = typeof navigator !== 'undefined' ? navigator.userAgent : null
  postBeacon(ERRORS_URL, {
    message: String(payload?.message || 'unknown_error'),
    stack: payload?.stack || null,
    url: payload?.url || (typeof location !== 'undefined' ? location.href : ''),
    info: payload?.info || null,
    user_agent: userAgent,
  })
}

export function reportFrontendPerf(payload) {
  if (!payload || typeof payload.value !== 'number' || !Number.isFinite(payload.value)) return
  const userAgent = typeof navigator !== 'undefined' ? navigator.userAgent : null
  postBeacon(PERF_URL, {
    route: String(payload.route || 'unknown'),
    metric: String(payload.metric || 'unknown'),
    value: payload.value,
    user_agent: userAgent,
  })
}
