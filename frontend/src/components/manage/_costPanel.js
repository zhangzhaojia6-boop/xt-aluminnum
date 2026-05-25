// Compose 14d energy-per-ton from /dashboard/timeseries (kg + kWh per day).
// Backend has no historical cost stream, so the panel pairs:
//   - top: 今日估算成本 (from management_estimate)
//   - bottom: 近 14 日吨能耗 (kWh/吨, from timeseries)
export function shapeEnergyTrend(rawList = [], days = 14) {
  if (!Array.isArray(rawList)) return []
  const tail = rawList.slice(-days)
  return tail.map((row) => {
    const kg = Number(row.output_weight ?? row.output ?? 0)
    const kwh = Number(row.energy ?? 0)
    const tons = Number.isFinite(kg) ? kg / 1000 : 0
    const epT = (tons > 0 && Number.isFinite(kwh)) ? kwh / tons : null
    return {
      date: row.date,
      label: row.date ? row.date.slice(5) : '',
      tons: Math.round(tons * 100) / 100,
      energy: Math.round(kwh),
      energyPerTon: epT == null ? null : Math.round(epT * 10) / 10
    }
  })
}

export function energyTrendStats(series = []) {
  const valid = series.map((s) => s.energyPerTon).filter((v) => Number.isFinite(v))
  if (!valid.length) return { avg: 0, last: 0, min: 0, max: 0 }
  const sum = valid.reduce((a, b) => a + b, 0)
  const last = series[series.length - 1]
  return {
    avg: sum / valid.length,
    last: last && Number.isFinite(last.energyPerTon) ? last.energyPerTon : 0,
    min: Math.min(...valid),
    max: Math.max(...valid)
  }
}
