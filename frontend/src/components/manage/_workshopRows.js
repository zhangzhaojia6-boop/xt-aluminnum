export function mapWorkshopRows(rows) {
  return [...(rows || [])]
    .map((r) => ({
      name: r.workshop_name || '-',
      today: Number(r.total_output || 0),
      compare: Number(r.compare_value || 0)
    }))
    .sort((a, b) => b.today - a.today)
}
