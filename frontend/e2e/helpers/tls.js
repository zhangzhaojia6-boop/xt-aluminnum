const LOCAL_HTTPS_HOSTS = new Set(['localhost', '127.0.0.1', '0.0.0.0', '::1', '[::1]'])

function isTruthy(value) {
  return ['1', 'true', 'yes', 'on'].includes(String(value || '').trim().toLowerCase())
}

export function isLocalHttpsBaseURL(baseURL) {
  if (!baseURL) return false
  try {
    const url = new URL(baseURL)
    const hostname = url.hostname.toLowerCase()
    return url.protocol === 'https:' && (
      LOCAL_HTTPS_HOSTS.has(hostname) ||
      hostname.endsWith('.localhost')
    )
  } catch {
    return false
  }
}

export function shouldIgnoreHttpsErrors({
  baseURL = process.env.PLAYWRIGHT_BASE_URL || 'https://localhost',
  allowInsecureTLS = process.env.PLAYWRIGHT_ALLOW_INSECURE_TLS
} = {}) {
  if (isTruthy(allowInsecureTLS)) return true
  return isLocalHttpsBaseURL(baseURL)
}
