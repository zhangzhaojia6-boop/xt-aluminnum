import { reportFrontendError } from '../api/telemetry.js'

export function installErrorMonitor(app) {
  app.config.errorHandler = (err, _instance, info) => {
    reportFrontendError({
      message: err?.message || String(err),
      stack: err?.stack,
      info,
      url: typeof location !== 'undefined' ? location.href : '',
    })
    if (typeof console !== 'undefined' && console.error) {
      console.error('[vue]', err)
    }
  }

  if (typeof window === 'undefined') return

  window.addEventListener('unhandledrejection', (e) => {
    const reason = e?.reason
    reportFrontendError({
      message: reason?.message || String(reason || 'unhandled_rejection'),
      stack: reason?.stack,
      info: 'unhandled_rejection',
      url: location.href,
    })
  })

  window.addEventListener(
    'error',
    (e) => {
      if (!e || e.message === 'Script error.') return
      reportFrontendError({
        message: e.message,
        stack: e.error?.stack,
        info: 'window_error',
        url: location.href,
      })
    },
    true,
  )
}
