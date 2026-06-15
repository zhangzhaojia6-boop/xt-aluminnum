const MESSAGE_ID_KEYS = ['provider_message_id', 'messageId', 'message_id', 'msgId', 'msg_id', 'openMsgId', 'open_msg_id']
const REQUEST_ID_KEYS = ['request_id', 'requestId', 'requestID', 'requestid']

function firstText(...values) {
  for (const value of values) {
    if (value !== undefined && value !== null && String(value).trim() !== '') {
      return String(value).trim()
    }
  }
  return ''
}

function findMessageId(payload = {}) {
  if (!payload || typeof payload !== 'object') return ''
  for (const key of MESSAGE_ID_KEYS) {
    const value = firstText(payload[key])
    if (value) return value
  }
  if (payload.result && typeof payload.result === 'object') {
    return findMessageId(payload.result)
  }
  return ''
}

function findRequestId(payload = {}) {
  if (!payload || typeof payload !== 'object') return ''
  for (const key of REQUEST_ID_KEYS) {
    const value = firstText(payload[key])
    if (value) return value
  }
  if (payload.result && typeof payload.result === 'object') {
    return findRequestId(payload.result)
  }
  return ''
}

export function formatExternalLogResult(item = {}) {
  const payload = item.response_payload && typeof item.response_payload === 'object' ? item.response_payload : {}
  const detail = firstText(item.detail)
  const messageId = firstText(item.provider_message_id, findMessageId(payload))
  const requestId = findRequestId(payload)
  const receiptCode = firstText(payload.errcode, payload.code, payload.status_code)
  const receiptText = firstText(payload.errmsg, payload.message, payload.msg)

  const parts = []
  if (detail) parts.push(detail)
  if (messageId) parts.push(`消息ID：${messageId}`)
  if (requestId) parts.push(`请求号：${requestId}`)
  if (receiptCode) parts.push(`回执码：${receiptCode}`)
  if (receiptText) parts.push(`回执：${receiptText}`)
  return parts.length ? parts.join(' / ') : '无返回信息'
}
