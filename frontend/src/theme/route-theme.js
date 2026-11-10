// 管理端和登录页用暗色科技主题；手机填报（/entry 等）保持浅色，现场强光下更好读。
// index.html 首帧前的内联脚本用同一套规则，改这里要同步改那里。
export const HUD = 'hud'
export const FORCE_LIGHT_KEY = 'xt-theme-force-light'

const DARK_PREFIXES = ['/manage', '/login', '/admin']

export function isDarkPath(path = '') {
  return DARK_PREFIXES.some((prefix) => path === prefix || path.startsWith(`${prefix}/`) || path.startsWith(`${prefix}?`))
}

function forcedLight(storage) {
  try {
    return storage?.getItem(FORCE_LIGHT_KEY) === '1'
  } catch {
    return false
  }
}

export function resolveTheme(path, storage = globalThis.localStorage) {
  return isDarkPath(path) && !forcedLight(storage) ? HUD : 'light'
}

export function applyRouteTheme(path, doc = globalThis.document, storage = globalThis.localStorage) {
  if (!doc) return
  const root = doc.documentElement
  if (resolveTheme(path, storage) === HUD) {
    root.dataset.xtTheme = HUD
    root.classList.add('dark')
  } else {
    delete root.dataset.xtTheme
    root.classList.remove('dark')
  }
}
