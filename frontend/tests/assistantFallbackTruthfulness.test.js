import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const source = readFileSync(new URL('../src/api/assistant.js', import.meta.url), 'utf8')
const workbenchSource = readFileSync(
  new URL('../src/components/review/ReviewAssistantWorkbench.vue', import.meta.url),
  'utf8'
)
const dockSource = readFileSync(
  new URL('../src/components/review/ReviewAssistantDock.vue', import.meta.url),
  'utf8'
)

test('assistant fallback does not present mock mode as online capability', () => {
  const fallbackStart = source.indexOf('export function buildAssistantFallback()')
  const fallbackEnd = source.indexOf('export const assistantCapabilityFallback')
  assert.notEqual(fallbackStart, -1)
  assert.notEqual(fallbackEnd, -1)

  const fallbackSource = source.slice(fallbackStart, fallbackEnd)

  assert.match(fallbackSource, /connected:\s*false/)
  assert.match(fallbackSource, /capabilities:\s*\[\]/)
  const integrationStatuses = [
    ...fallbackSource.matchAll(/\{\s*key:\s*'[^']+',\s*label:\s*'[^']+',\s*status:\s*'([^']+)'/g)
  ].map((match) => match[1])
  assert.deepEqual(integrationStatuses, ['planned', 'planned', 'planned'])
  assert.match(fallbackSource, /value:\s*'未联通'/)
  assert.doesNotMatch(fallbackSource, /entrypoint:\s*'\/api\/v1\/assistant\/query'/)
  assert.doesNotMatch(fallbackSource, /entrypoint:\s*'\/api\/v1\/assistant\/generate-image'/)
  assert.doesNotMatch(fallbackSource, /value:\s*'在线'/)

  assert.match(workbenchSource, /connectedIntegrationCount/)
  assert.match(workbenchSource, /capabilityState\.value\.connected !== true/)
  assert.match(workbenchSource, /item\?\.status === 'live'/)

  assert.match(dockSource, /function countLiveIntegrations/)
  assert.match(dockSource, /props\.capabilities\?\.connected === true/)
  assert.match(dockSource, /value: connected \? '在线' : '未联通'/)
  assert.doesNotMatch(dockSource, /hasAutomation \? '在线' : '在线'/)
})
