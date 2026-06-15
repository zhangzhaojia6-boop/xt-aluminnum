import test from 'node:test'
import assert from 'node:assert/strict'

import { formatExternalLogResult } from '../src/utils/externalLogDisplay.js'

test('formatExternalLogResult prefers detail but keeps provider message id', () => {
  assert.equal(
    formatExternalLogResult({
      detail: 'dingtalk_sent',
      provider_message_id: 'msg-001',
      response_payload: { errcode: 0 }
    }),
    'dingtalk_sent / 消息ID：msg-001 / 回执码：0'
  )
})

test('formatExternalLogResult falls back to provider payload result ids', () => {
  assert.equal(
    formatExternalLogResult({
      response_payload: { result: { messageId: 'nested-msg-002' } }
    }),
    '消息ID：nested-msg-002'
  )
})

test('formatExternalLogResult shows redacted sensitive values without leaking text', () => {
  assert.equal(
    formatExternalLogResult({
      response_payload: {
        access_token: '***',
        errcode: 88,
        errmsg: 'invalid token'
      }
    }),
    '回执码：88 / 回执：invalid token'
  )
})
