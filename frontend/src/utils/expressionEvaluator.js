const SAFE_EXPRESSION_PATTERN = /^[A-Za-z0-9_+\-*/().%\s]+$/

function operatorPrecedence(operator) {
  if (operator === '+' || operator === '-') return 1
  if (operator === '*' || operator === '/' || operator === '%') return 2
  return 0
}

function applyMathOperator(values, operator) {
  if (values.length < 2) return false
  const right = Number(values.pop())
  const left = Number(values.pop())
  let result = null

  if (operator === '+') result = left + right
  else if (operator === '-') result = left - right
  else if (operator === '*') result = left * right
  else if (operator === '/') result = right === 0 ? null : left / right
  else if (operator === '%') result = right === 0 ? null : left % right

  if (result === null || !Number.isFinite(result)) return false
  values.push(result)
  return true
}

export function safeEvaluate(expression, variables) {
  const source = String(expression || '').trim()
  if (!source || !SAFE_EXPRESSION_PATTERN.test(source)) return null

  const tokens = source.match(/[A-Za-z_][A-Za-z0-9_]*|\d+(?:\.\d+)?|[()+\-*/%]/g) || []
  if (!tokens.length) return null

  const values = []
  const operators = []
  let previousTokenType = 'start'

  for (const token of tokens) {
    if (/^\d+(?:\.\d+)?$/.test(token)) {
      values.push(Number(token))
      previousTokenType = 'value'
      continue
    }

    if (/^[A-Za-z_][A-Za-z0-9_]*$/.test(token)) {
      values.push(Number(variables[token] ?? 0))
      previousTokenType = 'value'
      continue
    }

    if (token === '(') {
      operators.push(token)
      previousTokenType = '('
      continue
    }

    if (token === ')') {
      while (operators.length && operators[operators.length - 1] !== '(') {
        if (!applyMathOperator(values, operators.pop())) return null
      }
      if (operators.length === 0 || operators.pop() !== '(') return null
      previousTokenType = 'value'
      continue
    }

    if ('+-*/%'.includes(token)) {
      if (token === '-' && (previousTokenType === 'start' || previousTokenType === 'operator' || previousTokenType === '(')) {
        values.push(0)
      }

      while (
        operators.length &&
        operators[operators.length - 1] !== '(' &&
        operatorPrecedence(operators[operators.length - 1]) >= operatorPrecedence(token)
      ) {
        if (!applyMathOperator(values, operators.pop())) return null
      }
      operators.push(token)
      previousTokenType = 'operator'
      continue
    }

    return null
  }

  while (operators.length) {
    const operator = operators.pop()
    if (operator === '(' || operator === ')') return null
    if (!applyMathOperator(values, operator)) return null
  }

  if (values.length !== 1) return null
  const finalValue = Number(values[0])
  return Number.isFinite(finalValue) ? finalValue : null
}
