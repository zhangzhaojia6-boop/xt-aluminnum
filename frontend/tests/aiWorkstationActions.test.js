import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const apiSource = readFileSync(new URL('../src/api/ai-assistant.js', import.meta.url), 'utf8')
const storeSource = readFileSync(new URL('../src/stores/assistant.js', import.meta.url), 'utf8')
const inboxSource = readFileSync(new URL('../src/components/ai/AiBriefingInbox.vue', import.meta.url), 'utf8')

test('assistant action api and store wire one click execution', () => {
  assert.match(apiSource, /executeAssistantAction/)
  assert.match(apiSource, /\/assistant\/actions/)
  assert.match(apiSource, /\/ai\/runtime/)
  assert.match(apiSource, /skipAuthLogout:\s*true/)
  assert.match(storeSource, /executeBriefingAction/)
  assert.match(storeSource, /executeAssistantAction/)
})

test('briefing inbox renders suggested action buttons for manager roles', () => {
  assert.match(inboxSource, /suggested_actions/)
  assert.match(inboxSource, /data-testid="assistant-action-button"/)
  assert.match(inboxSource, /canExecuteActions/)
  assert.match(inboxSource, /handleExecuteAction/)
  assert.match(inboxSource, /:disabled="Boolean\(executingKey\)"/)
})
