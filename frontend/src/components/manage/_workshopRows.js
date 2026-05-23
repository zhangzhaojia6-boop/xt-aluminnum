export function mapWorkshopRows(rows) {
  return [...(rows || [])]
    .map((r) => ({
      name: r.workshop_name || '-',
      today: Number(r.total_output || 0),
      monthAvg: r.target_value == null ? null : Number(r.target_value)
    }))
    .sort((a, b) => b.today - a.today)
}
