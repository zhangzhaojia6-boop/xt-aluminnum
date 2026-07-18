const SHIFT_WINDOWS = [
  { code: 'A', name: '长白班', startMinutes: 7 * 60 + 30, endMinutes: 15 * 60 + 30 },
  { code: 'B', name: '小夜班', startMinutes: 15 * 60 + 30, endMinutes: 23 * 60 + 30 },
  { code: 'C', name: '大夜班', startMinutes: 23 * 60 + 30, endMinutes: 24 * 60 },
  { code: 'C', name: '大夜班', startMinutes: 0, endMinutes: 7 * 60 + 30 }
]

const BUSINESS_DAY_ANCHOR_MINUTES = 7 * 60 + 50
const OWNER_DAILY_ANCHOR_MINUTES = 9 * 60 + 30

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
  return inferBusinessDateAtAnchor(BUSINESS_DAY_ANCHOR_MINUTES, now)
}

export function inferOwnerDailyBusinessDate(now = new Date()) {
  return inferBusinessDateAtAnchor(OWNER_DAILY_ANCHOR_MINUTES, now)
}

export function ownerDailyBusinessDateOptions(latestBusinessDate) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(latestBusinessDate || ''))
  if (!match) return []
  const anchor = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3])))
  if (formatUtcDate(anchor) !== latestBusinessDate) return []
  return Array.from({ length: 8 }, (_, index) => {
    const candidate = new Date(anchor)
    candidate.setUTCDate(candidate.getUTCDate() - index)
    return formatUtcDate(candidate)
  })
}

function inferBusinessDateAtAnchor(anchorMinutes, now = new Date()) {
  const wall = nowInShanghai(now)
  const minutes = totalMinutes(wall)
  const anchor = new Date(Date.UTC(wall.year, wall.month - 1, wall.day))
  if (minutes < anchorMinutes) {
    anchor.setUTCDate(anchor.getUTCDate() - 1)
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
