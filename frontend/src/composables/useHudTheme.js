import { onBeforeUnmount, onMounted } from 'vue'

const THEME_KEY = 'xt-theme-preference'
const HUD = 'hud'

export function applyHudTheme(doc = document) {
  doc.documentElement.dataset.xtTheme = HUD
}

export function clearHudTheme(doc = document) {
  delete doc.documentElement.dataset.xtTheme
}

export function isHudActive(doc = document) {
  return doc.documentElement.dataset.xtTheme === HUD
}

export function readHudPreference() {
  try {
    return localStorage.getItem(THEME_KEY) === HUD
  } catch {
    return false
  }
}

export function writeHudPreference(enabled) {
  try {
    if (enabled) localStorage.setItem(THEME_KEY, HUD)
    else localStorage.removeItem(THEME_KEY)
  } catch {
    /* ignore quota / SSR */
  }
  if (typeof document !== 'undefined') {
    if (enabled) applyHudTheme()
    else clearHudTheme()
  }
}

export function useHudTheme(options = {}) {
  if (typeof document !== 'undefined') {
    if (options.force || readHudPreference()) applyHudTheme()
    else clearHudTheme()
  }
  onMounted(() => {
    if (options.force || readHudPreference()) applyHudTheme()
  })
  onBeforeUnmount(() => {
    clearHudTheme()
  })
}
