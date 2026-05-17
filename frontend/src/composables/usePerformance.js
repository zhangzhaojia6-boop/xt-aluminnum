import { onMounted } from 'vue'

/**
 * Performance Monitoring Composable
 * Tracks LCP, FID, CLS, etc.
 */
export function usePerformance(routeName) {
  const reportPerf = (metric) => {
    console.log(`[PerfMonitor][${routeName}]`, metric)
    // Send to backend telemetry
    // fetch('/api/telemetry/perf', { method: 'POST', body: JSON.stringify(metric) })
  }

  onMounted(() => {
    if (typeof PerformanceObserver === 'undefined') return

    // Track Largest Contentful Paint
    const lcpObserver = new PerformanceObserver((entryList) => {
      const entries = entryList.getEntries()
      const lastEntry = entries[entries.length - 1]
      reportPerf({
        metric: 'LCP',
        value: lastEntry.renderTime || lastEntry.loadTime,
        route: routeName
      })
    })
    lcpObserver.observe({ type: 'largest-contentful-paint', buffered: true })

    // Track First Input Delay
    const fidObserver = new PerformanceObserver((entryList) => {
      entryList.getEntries().forEach((entry) => {
        reportPerf({
          metric: 'FID',
          value: entry.processingStart - entry.startTime,
          route: routeName
        })
      })
    })
    fidObserver.observe({ type: 'first-input', buffered: true })

    // Track Layout Shift
    let clsValue = 0
    const clsObserver = new PerformanceObserver((entryList) => {
      for (const entry of entryList.getEntries()) {
        if (!entry.hadRecentInput) {
          clsValue += entry.value
          reportPerf({
            metric: 'CLS_STEP',
            value: clsValue,
            route: routeName
          })
        }
      }
    })
    clsObserver.observe({ type: 'layout-shift', buffered: true })
  })
}
