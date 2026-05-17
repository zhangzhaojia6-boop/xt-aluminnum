/**
 * Frontend Error Monitoring Plugin
 * Captures Vue errors and global unhandled rejections
 */

function reportError(errorData) {
  console.error('[ErrorMonitor]', errorData)
  // In a real scenario, this would POST to /api/telemetry/errors
  // For now, we log to console in a structured way
  if (window.reportPerf) {
    window.reportPerf({
      type: 'error',
      ...errorData,
      timestamp: new Date().toISOString()
    })
  }
}

export function installErrorMonitor(app) {
  app.config.errorHandler = (err, instance, info) => {
    reportError({
      message: err.message,
      stack: err.stack,
      info,
      url: location.href,
      type: 'vue_error'
    })
  }

  window.addEventListener('unhandledrejection', (e) => {
    reportError({
      message: e.reason?.message || 'Unhandled Rejection',
      stack: e.reason?.stack,
      url: location.href,
      type: 'unhandled_rejection'
    })
  })

  window.addEventListener('error', (e) => {
    if (e.message === 'Script error.') return
    reportError({
      message: e.message,
      stack: e.error?.stack,
      url: location.href,
      type: 'window_error'
    })
  }, true)
}
