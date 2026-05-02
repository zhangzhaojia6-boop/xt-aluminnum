function cleanText(value) {
  return String(value ?? '').trim()
}

function numericValue(value) {
  if (value === null || value === undefined || value === '') return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

export function validateCoilEntryForm(form = {}) {
  if (!cleanText(form.tracking_card_no)) {
    return '请填写卷号'
  }

  const inputWeight = numericValue(form.input_weight)
  const outputWeight = numericValue(form.output_weight)
  if (inputWeight === null || outputWeight === null) {
    return '请填写投入和产出重量'
  }
  if (inputWeight <= 0) {
    return '投入重量必须大于 0'
  }
  if (outputWeight <= 0) {
    return '产出重量必须大于 0'
  }
  if (outputWeight > inputWeight) {
    return '产出重量不能大于投入重量'
  }

  return null
}
