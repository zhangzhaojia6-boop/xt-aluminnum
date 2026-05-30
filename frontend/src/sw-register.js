import { registerSW } from 'virtual:pwa-register'

export function installSW() {
  if ('serviceWorker' in navigator) {
    let refreshing = false
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      if (refreshing) return
      refreshing = true
      window.location.reload()
    })

    const updateSW = registerSW({
      immediate: true,
      onNeedRefresh() {
        updateSW(true)
      },
      onOfflineReady() {
        console.log('App ready to work offline')
      },
      onRegistered(registration) {
        console.log('SW registered:', registration)
        registration?.update?.()
        
        // Background Sync support check
        if (registration && 'sync' in registration) {
          console.log('Background Sync is supported')
        }
      }
    })
  }
}
