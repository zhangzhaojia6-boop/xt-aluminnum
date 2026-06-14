import { existsSync, readFileSync } from 'node:fs'
import test from 'node:test'
import assert from 'node:assert/strict'

function source(path) {
  return readFileSync(new URL(path, import.meta.url), 'utf8')
}

test('communication channels page has a manage route and navigation entry', () => {
  const router = source('../src/router/index.js')
  const navigation = source('../src/config/manage-navigation.js')

  assert.match(router, /const CommunicationChannelsPage = \(\) => import\('\.\.\/views\/manage\/channels\/CommunicationChannelsPage\.vue'\)/)
  assert.match(router, /path: 'channels'/)
  assert.match(router, /name: 'manage-channels'/)
  assert.match(router, /canonical: '\/manage\/channels'/)
  assert.match(navigation, /通讯通道/)
  assert.match(navigation, /\/manage\/channels/)
})

test('communication channels page reads masked channel data only', () => {
  const apiPath = new URL('../src/api/agent-management.js', import.meta.url)
  const pagePath = new URL('../src/views/manage/channels/CommunicationChannelsPage.vue', import.meta.url)
  assert.equal(existsSync(apiPath), true)
  assert.equal(existsSync(pagePath), true)

  const api = source('../src/api/agent-management.js')
  const page = source('../src/views/manage/channels/CommunicationChannelsPage.vue')

  assert.match(api, /fetchCommunicationChannels/)
  assert.match(api, /\/agent-management\/overview/)
  assert.match(api, /outbox: overview\?\.outbox/)
  assert.match(page, /data-testid="communication-channels-page"/)
  assert.match(page, /fetchCommunicationChannels/)
  assert.match(page, /fetchAgentOutboxLogs/)
  assert.match(page, /channel_key_masked/)
  assert.match(page, /dry_run/)
  assert.match(page, /真实发送/)
  assert.match(page, /演练模式/)
  assert.doesNotMatch(page, new RegExp(['se', 'cret_ref'].join('')))
  assert.doesNotMatch(page, /channel_key[^_]/)
})

test('communication channels page explains safe routing without fake channel data', () => {
  const page = source('../src/views/manage/channels/CommunicationChannelsPage.vue')

  for (const text of ['通讯通道中心', '通道清单', '绑定数量', '通道状态', '发件箱统一分发']) {
    assert.match(page, new RegExp(text))
  }
  assert.doesNotMatch(page, new RegExp(['假数据', '示例群', '机器人头像', '霓虹', `web${'hook'}`].join('|')))
})

test('communication channels page exposes outbox log inspection without sending messages', () => {
  const api = source('../src/api/agent-management.js')
  const page = source('../src/views/manage/channels/CommunicationChannelsPage.vue')

  assert.match(api, /fetchAgentOutboxLogs/)
  assert.match(api, /\/agent-management\/outbox\/\$\{outboxMessageId\}\/logs/)
  assert.match(api, /runCommunicationDryRunSmoke/)
  assert.match(api, /\/agent-management\/outbox\/dry-run-smoke/)
  assert.match(page, /runCommunicationDryRunSmoke/)
  for (const text of ['最近外发任务', '外发日志', '查看日志', '投递状态', '返回结果']) {
    assert.match(page, new RegExp(text))
  }
  assert.match(page, /运行演练自检/)
  assert.match(page, /演练自检/)
  assert.doesNotMatch(page, /立即发送|测试发送|创建通道|编辑通道/)
})
