export function mapWorkshopRows(rows) {
  return [...(rows || [])]
    .map((r) => ({
      name: r.workshop_name || '-',
      today: r.total_output == null ? null : Number(r.total_output),
      monthAvg: r.target_value == null ? null : Number(r.target_value)
    }))
    .sort((a, b) => (b.today ?? -Infinity) - (a.today ?? -Infinity))
}
