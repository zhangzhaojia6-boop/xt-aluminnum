const WEIGHT_FIELD_LABELS = {
  input_weight: '投入重量',
  output_weight: '产出重量',
  scrap_weight: '废料重量',
}
const BALANCE_EPSILON = 0.000001

function numericValue(value) {
  if (value === null || value === undefined || value === '') return null
  const number = Number(value)
  return Number.isFinite(number) ? number : null
}

function fieldLabel(field) {
  return field?.label || WEIGHT_FIELD_LABELS[field?.name] || field?.name || '重量'
}

function findField(fields, name) {
  return fields.find((field) => field?.name === name && field?.type === 'number')
}

function exceeds(left, right) {
  return left - right > BALANCE_EPSILON
}

export function validateEntryWeights(form = {}, fields = []) {
  const inputField = findField(fields, 'input_weight')
  const outputField = findField(fields, 'output_weight')
  const scrapField = findField(fields, 'scrap_weight')
  const visibleWeightFields = [inputField, outputField, scrapField].filter(Boolean)
  const values = {}

  for (const field of visibleWeightFields) {
    const value = numericValue(form[field.name])
    values[field.name] = value
    if (value !== null && value < 0) {
      return `${fieldLabel(field)}不能为负数`
    }
  }

  if (
    inputField &&
    outputField &&
    values.input_weight !== null &&
    values.output_weight !== null &&
    exceeds(values.output_weight, values.input_weight)
  ) {
    return '产出重量不能大于投入重量'
  }

  if (
    inputField &&
    outputField &&
    scrapField &&
    values.input_weight !== null &&
    values.output_weight !== null &&
    values.scrap_weight !== null &&
    exceeds(values.output_weight + values.scrap_weight, values.input_weight)
  ) {
    return '产出重量和废料重量合计不能大于投入重量'
  }

  return null
}
