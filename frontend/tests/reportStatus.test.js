import test from 'node:test'
import assert from 'node:assert/strict'

import { requestErrorMessage } from '../src/utils/reportStatus.js'

test('requestErrorMessage maps locked field tamper errors to operator copy', () => {
  assert.equal(
    requestErrorMessage({ response: { data: { detail: 'locked_field_tampered' } } }, '提交失败'),
    '扫码带出的卷号、合金或规格已变化，请重新扫码后提交'
  )
})
