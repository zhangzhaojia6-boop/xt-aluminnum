export const AI_ASSISTANT_OPEN_EVENT = 'xt:open-ai-assistant'

export function openAiAssistant({ question = '', scope = null, freshness = null } = {}) {
  window.dispatchEvent(
    new CustomEvent(AI_ASSISTANT_OPEN_EVENT, {
      detail: {
        question,
        scope,
        freshness
      }
    })
  )
}

export function buildAssistantScope({ path = '', query = {} } = {}, scope = null) {
  const base = scope || { type: 'route', key: path || '/manage/today' }
  const businessDate = typeof query?.target_date === 'string' ? query.target_date : ''
  return businessDate && !base.business_date ? { ...base, business_date: businessDate } : base
}
