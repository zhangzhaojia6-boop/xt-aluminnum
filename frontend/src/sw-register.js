import { registerSW } from 'virtual:pwa-register'

export function installSW() {
  if ('serviceWorker' in navigator) {
    const updateSW = registerSW({
      onNeedRefresh() {
        // Here we could show a HUD-styled notification to the user
        if (confirm('新内容可用，是否刷新？')) {
          updateSW(true)
        }
      },
      onOfflineReady() {
        console.log('App ready to work offline')
      },
      onRegistered(registration) {
        console.log('SW registered:', registration)
        
        // Background Sync support check
        if (registration && 'sync' in registration) {
          console.log('Background Sync is supported')
        }
      }
    })
  }
}
