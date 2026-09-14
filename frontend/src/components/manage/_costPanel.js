// Compose 14d energy-per-ton from /dashboard/timeseries (kg + kWh per day).
// Backend has no historical cost stream, so the panel pairs:
//   - top: 今日估算成本 (from management_estimate)
//   - bottom: 近 14 日吨能耗 (kWh/吨, from timeseries)
export function shapeEnergyTrend(rawList = [], days = 14) {
  if (!Array.isArray(rawList)) return []
  const tail = rawList.slice(-days)
  return tail.map((row) => {
    const output = row.output_weight ?? row.output
    const kg = output == null ? null : Number(output)
    const kwh = row.energy == null ? null : Number(row.energy)
    const tons = Number.isFinite(kg) ? kg / 1000 : null
    const epT = (tons > 0 && Number.isFinite(kwh)) ? kwh / tons : null
    return {
      date: row.date,
      label: row.date ? row.date.slice(5) : '',
      tons: tons == null ? null : Math.round(tons * 100) / 100,
      energy: Number.isFinite(kwh) ? Math.round(kwh) : null,
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
    last: last && Number.isFinite(last.energyPerTon) ? last.energyPerTon : null,
    min: Math.min(...valid),
    max: Math.max(...valid)
  }
}
