import { registerSW } from 'virtual:pwa-register'

export function installSW() {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.addEventListener('controllerchange', () => {
      console.log('SW controller changed; keeping current dashboard session alive')
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
