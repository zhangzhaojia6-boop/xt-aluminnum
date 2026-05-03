function cleanText(value) {
  return String(value ?? '').trim()
}

function flowSource(value) {
  const source = cleanText(value)
  if (source === 'manual' || source === 'manual_pending_match' || source === 'ambiguous_match') return 'manual_pending_match'
  return source || 'mes_projection'
}

function flowValue(source, snakeKey, camelKey) {
  return cleanText(source?.[snakeKey] ?? source?.[camelKey])
}

function hasExternalFlow(flow = {}) {
  return flowSource(flow.flow_source ?? flow.source) !== 'manual_pending_match'
}

export function validateFlowSelection(flow = {}) {
  const hasFlow = Object.values(flow || {}).some((value) => cleanText(value))
  if (!hasFlow) return null
  const currentProcess = flowValue(flow, 'current_process', 'currentProcess')
  const nextWorkshop = flowValue(flow, 'next_workshop', 'nextWorkshop')
  const nextProcess = flowValue(flow, 'next_process', 'nextProcess')
  if (currentProcess && (!nextWorkshop || !nextProcess)) {
    return '请填写下道车间和工序'
  }
  return null
}

export function resolveFlowFieldState(flow = {}) {
  const external = hasExternalFlow(flow)
  return {
    previous: {
      locked: external && Boolean(flowValue(flow, 'previous_process', 'previousProcess'))
    },
    current: {
      locked: external && Boolean(flowValue(flow, 'current_process', 'currentProcess'))
    },
    next: {
      locked: external && Boolean(flowValue(flow, 'next_process', 'nextProcess'))
    }
  }
}

export function buildFlowPayload(flow = {}) {
  const routeValues = [
    flowValue(flow, 'previous_workshop', 'previousWorkshop'),
    flowValue(flow, 'previous_process', 'previousProcess'),
    flowValue(flow, 'current_workshop', 'currentWorkshop'),
    flowValue(flow, 'current_process', 'currentProcess'),
    flowValue(flow, 'next_workshop', 'nextWorkshop'),
    flowValue(flow, 'next_process', 'nextProcess')
  ]
  if (!routeValues.some(Boolean)) {
    return { extra_payload: {} }
  }
  const normalized = {
    previous_workshop: routeValues[0],
    previous_process: routeValues[1],
    current_workshop: routeValues[2],
    current_process: routeValues[3],
    next_workshop: routeValues[4],
    next_process: routeValues[5],
    flow_source: flowSource(flow.flow_source ?? flow.source),
    flow_confirmed_at: cleanText(flow.flow_confirmed_at ?? flow.confirmed_at) || new Date().toISOString()
  }
  const compact = Object.fromEntries(Object.entries(normalized).filter(([, value]) => value !== ''))
  return {
    extra_payload: {
      flow: compact
    }
  }
}
