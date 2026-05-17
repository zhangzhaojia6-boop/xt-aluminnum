import { onBeforeUnmount, onMounted } from 'vue'
import { reportFrontendPerf } from '../api/telemetry.js'

export function usePerformance(routeName) {
  const observers = []

  function safeObserve(type, handler) {
    if (typeof PerformanceObserver === 'undefined') return
    try {
      const observer = new PerformanceObserver(handler)
      observer.observe({ type, buffered: true })
      observers.push(observer)
    } catch (_) {
      // unsupported entry type — skip silently
    }
  }

  onMounted(() => {
    safeObserve('largest-contentful-paint', (entryList) => {
      const entries = entryList.getEntries()
      const last = entries[entries.length - 1]
      if (!last) return
      const value = last.renderTime || last.loadTime || last.startTime
      reportFrontendPerf({ route: routeName, metric: 'LCP', value })
    })

    safeObserve('first-input', (entryList) => {
      for (const entry of entryList.getEntries()) {
        reportFrontendPerf({
          route: routeName,
          metric: 'FID',
          value: entry.processingStart - entry.startTime,
        })
      }
    })

    let clsValue = 0
    safeObserve('layout-shift', (entryList) => {
      for (const entry of entryList.getEntries()) {
        if (!entry.hadRecentInput) clsValue += entry.value
      }
    })

    if (typeof window !== 'undefined') {
      const flushCls = () => {
        if (clsValue <= 0) return
        reportFrontendPerf({ route: routeName, metric: 'CLS', value: clsValue })
        clsValue = 0
      }
      window.addEventListener('pagehide', flushCls, { once: true })
    }
  })

  onBeforeUnmount(() => {
    while (observers.length) {
      const observer = observers.pop()
      try {
        observer.disconnect()
      } catch (_) {
        // ignore
      }
    }
  })
}
