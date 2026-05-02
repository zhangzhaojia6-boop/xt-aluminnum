export function computeReadonlyValue(expression, formValues, unit) {
  if (!expression) return '—'
  try {
    const expr = expression.replace(/[a-z_]+/g, (m) => {
      const v = Number(formValues[m])
      return isNaN(v) ? '0' : String(v)
    })
    const val = Function(`"use strict"; return (${expr})`)()
    if (!isFinite(val)) return '—'
    return unit === '%' ? val.toFixed(1) + '%' : val.toFixed(1) + (unit ? ' ' + unit : '')
  } catch {
    return '—'
  }
}
