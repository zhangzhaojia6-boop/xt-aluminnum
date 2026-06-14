import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const routerSrc = readFileSync(new URL('../src/router/index.js', import.meta.url), 'utf8')
const navSrc = readFileSync(new URL('../src/config/manage-navigation.js', import.meta.url), 'utf8')
const apiSrc = readFileSync(new URL('../src/api/agent-management.js', import.meta.url), 'utf8')
const pageSrc = readFileSync(new URL('../src/views/manage/admin/AgentManagementPage.vue', import.meta.url), 'utf8')

test('AgentManagementPage is reachable from an admin-only manage route', () => {
  assert.match(routerSrc, /const AgentManagementPage = \(\) => import\('\.\.\/views\/manage\/admin\/AgentManagementPage\.vue'\)/)
  assert.match(routerSrc, /path: 'admin\/agents'/)
  assert.match(routerSrc, /name: 'admin-agent-management'/)
  assert.match(routerSrc, /access: 'admin'/)
})

test('AgentManagementPage is exposed in admin navigation only', () => {
  assert.match(navSrc, /title: '通讯治理'/)
  assert.match(navSrc, /path: '\/manage\/admin\/agents'/)
  assert.match(navSrc, /access: 'admin'/)
})

test('AgentManagementPage reads the safe overview endpoint', () => {
  assert.match(apiSrc, /fetchAgentManagementOverview/)
  assert.match(apiSrc, /fetchAgentKnowledgeEntries/)
  assert.match(apiSrc, /askAgentKnowledge/)
  assert.match(apiSrc, /dispatchAgentOutboxMessage/)
  assert.match(apiSrc, /fetchAgentOutboxLogs/)
  assert.match(apiSrc, /api\.get\('\/agent-management\/overview'/)
  assert.match(apiSrc, /api\.get\('\/agent-management\/knowledge'/)
  assert.match(apiSrc, /api\.post\('\/agent-management\/knowledge\/answer'/)
  assert.match(apiSrc, /api\.post\(`\/agent-management\/outbox\/\$\{outboxMessageId\}\/dispatch`/)
  assert.match(apiSrc, /api\.get\(`\/agent-management\/outbox\/\$\{outboxMessageId\}\/logs`/)
  assert.doesNotMatch(apiSrc, /put|delete/i)
})

test('AgentManagementPage presents the four governance loops without secret fields', () => {
  assert.match(pageSrc, /data-testid="agent-management-page"/)
  assert.match(pageSrc, /data-visual-pass="stitch-industrial-blue-governance"/)
  for (const text of ['通讯治理台', '智能体状态', '通道治理', '最近事件', '多模态证据', '待审核操作', '发件箱', '知识口径']) {
    assert.match(pageSrc, new RegExp(text))
  }
  assert.match(pageSrc, /channel_key_masked/)
  assert.match(pageSrc, /executionStateLabel/)
  assert.match(pageSrc, /真实执行/)
  assert.doesNotMatch(pageSrc, /secret_ref/)
  assert.doesNotMatch(pageSrc, /radial-gradient/)
  assert.doesNotMatch(pageSrc, /purple|violet|lila/i)
})

test('AgentManagementPage includes loading, empty and error states', () => {
  for (const text of ['读取中', '暂无记录', '读取失败']) {
    assert.match(pageSrc, new RegExp(text))
  }
})

test('AgentManagementPage can dispatch outbox messages and inspect external logs', () => {
  assert.match(pageSrc, /dispatchAgentOutboxMessage/)
  assert.match(pageSrc, /fetchAgentOutboxLogs/)
  assert.match(pageSrc, /handleDispatchOutbox/)
  assert.match(pageSrc, /loadOutboxLogs/)
  assert.match(pageSrc, /执行分发/)
  assert.match(pageSrc, /外发日志/)
  assert.match(pageSrc, /channel_key_masked/)
  assert.doesNotMatch(pageSrc, /channel_key[^_]/)
})

test('AgentManagementPage renders dead-letter outbox status in Chinese', () => {
  assert.match(pageSrc, /dead_letter:\s*'死信'/)
  assert.match(pageSrc, /retrying:\s*'重试中'/)
})
