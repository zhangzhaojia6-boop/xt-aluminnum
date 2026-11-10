// 主题由路由决定（src/theme/route-theme.js）；这里只保存用户偏好，不改页面。
const THEME_KEY = 'xt-theme-preference'
const HUD = 'hud'

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
}
