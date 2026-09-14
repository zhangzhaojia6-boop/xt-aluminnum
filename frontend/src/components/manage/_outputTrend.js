export function shapeTrendSeries(rawList = [], days = 14) {
  if (!Array.isArray(rawList)) return []
  const tail = rawList.slice(-days)
  return tail.map((row) => {
    const value = row.output_weight ?? row.output
    const raw = value == null ? null : Number(value)
    const tons = Number.isFinite(raw) ? raw / 1000 : null
    return {
      date: row.date,
      label: row.date ? row.date.slice(5) : '',
      output: tons == null ? null : Math.round(tons * 100) / 100
    }
  })
}

export function trendStats(series) {
  if (!series.length) return { max: 0, avg: 0, last: 0 }
  const valid = series.map((s) => s.output).filter((v) => Number.isFinite(v))
  if (!valid.length) return { max: 0, avg: 0, last: 0 }
  const sum = valid.reduce((a, b) => a + b, 0)
  return {
    max: Math.max(...valid),
    avg: sum / valid.length,
    last: series[series.length - 1].output
  }
}
