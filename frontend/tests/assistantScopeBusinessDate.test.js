import test from 'node:test'
import assert from 'node:assert/strict'

import { buildAssistantScope } from '../src/utils/assistantLauncher.js'

test('assistant scope inherits the daily report business date from the route', () => {
  const scope = buildAssistantScope({ path: '/manage/today', query: { target_date: '2026-10-29' } })

  assert.deepEqual(scope, { type: 'route', key: '/manage/today', business_date: '2026-10-29' })
})

test('assistant scope keeps an explicit launcher scope and adds the route date', () => {
  const scope = buildAssistantScope(
    { path: '/manage/today', query: { target_date: '2026-10-29' } },
    { type: 'machine', key: '冷轧:01' }
  )

  assert.deepEqual(scope, { type: 'machine', key: '冷轧:01', business_date: '2026-10-29' })
})

test('assistant scope without a selected date stays route scoped', () => {
  assert.deepEqual(buildAssistantScope({ path: '/manage/live', query: {} }), { type: 'route', key: '/manage/live' })
})
