const SHIFT_WINDOWS = [
  { code: 'C', name: '大夜', startMinutes: 0, endMinutes: 7 * 60 + 30 },
  { code: 'A', name: '长白班', startMinutes: 7 * 60 + 30, endMinutes: 15 * 60 + 30 },
  { code: 'B', name: '小夜', startMinutes: 15 * 60 + 30, endMinutes: 23 * 60 + 30 },
  { code: 'C', name: '大夜', startMinutes: 23 * 60 + 30, endMinutes: 24 * 60 }
]

const BUSINESS_DAY_ANCHOR_MINUTES = 23 * 60 + 30

function nowInShanghai(now = new Date()) {
  const fmt = new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hour12: false
  })
  const parts = Object.fromEntries(fmt.formatToParts(now).map((p) => [p.type, p.value]))
  return {
    year: Number(parts.year),
    month: Number(parts.month),
    day: Number(parts.day),
    hour: Number(parts.hour) % 24,
    minute: Number(parts.minute)
  }
}

function totalMinutes({ hour, minute }) {
  return hour * 60 + minute
}

function formatUtcDate(anchor) {
  const yyyy = anchor.getUTCFullYear()
  const mm = String(anchor.getUTCMonth() + 1).padStart(2, '0')
  const dd = String(anchor.getUTCDate()).padStart(2, '0')
  return `${yyyy}-${mm}-${dd}`
}

export function inferShift(now = new Date()) {
  const wall = nowInShanghai(now)
  const minutes = totalMinutes(wall)
  for (const window of SHIFT_WINDOWS) {
    if (minutes >= window.startMinutes && minutes < window.endMinutes) {
      return { code: window.code, name: window.name }
    }
  }
  return SHIFT_WINDOWS[0]
}

export function inferBusinessDate(now = new Date()) {
  const wall = nowInShanghai(now)
  const minutes = totalMinutes(wall)
  const anchor = new Date(Date.UTC(wall.year, wall.month - 1, wall.day))
  if (minutes >= BUSINESS_DAY_ANCHOR_MINUTES) {
    anchor.setUTCDate(anchor.getUTCDate() + 1)
  }
  return formatUtcDate(anchor)
}

export function inferLastCompletedBusinessDate(now = new Date()) {
  const activeBusinessDate = inferBusinessDate(now)
  const anchor = new Date(`${activeBusinessDate}T00:00:00Z`)
  anchor.setUTCDate(anchor.getUTCDate() - 1)
  return formatUtcDate(anchor)
}

export function describeInferredShift(now = new Date()) {
  const shift = inferShift(now)
  const businessDate = inferBusinessDate(now)
  return { ...shift, businessDate }
}

export function isShiftMismatch(backendShiftCode, now = new Date()) {
  if (!backendShiftCode) return false
  const inferred = inferShift(now)
  const code = String(backendShiftCode).trim().toUpperCase()
  if (!['A', 'B', 'C'].includes(code)) return false
  return code !== inferred.code
}
