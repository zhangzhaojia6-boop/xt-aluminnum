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
