import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

function source(path) {
  return readFileSync(new URL(path, import.meta.url), 'utf8')
}

test('management shell renders persistent assistant drawer', () => {
  const shell = source('../src/layout/ManageShell.vue')

  assert.match(shell, /AiAssistantDrawer/)
  assert.match(shell, /assistantOpen/)
  assert.match(shell, /AI 助手/)
})

test('assistant drawer connects context conversation evidence briefings and watchlist', () => {
  const drawer = source('../src/components/ai/AiAssistantDrawer.vue')

  assert.match(drawer, /currentContext/)
  assert.match(drawer, /conversation|messages/)
  assert.match(drawer, /AiEvidenceRefs/)
  assert.match(drawer, /AiBriefingInbox/)
  assert.match(drawer, /AiWatchlistPanel/)
  assert.match(drawer, /freshness|stale|offline/)
})

test('briefing inbox exposes unread read followed and ignored states', () => {
  const inbox = source('../src/components/ai/AiBriefingInbox.vue')

  for (const state of ['unread', 'read', 'followed', 'ignored']) {
    assert.match(inbox, new RegExp(state))
  }
  assert.match(inbox, /markBriefingRead/)
  assert.match(inbox, /followUpBriefing/)
})

test('watchlist supports factory command watch target types', () => {
  const watchlist = source('../src/components/ai/AiWatchlistPanel.vue')

  for (const type of ['workshop', 'machine', 'coil', 'process', 'alloy_spec', 'metric']) {
    assert.match(watchlist, new RegExp(type))
  }
  assert.match(watchlist, /createWatch/)
  assert.match(watchlist, /updateWatch/)
})

test('ai workstation exposes assistant inbox tabs without stale capability copy', () => {
  const workstation = source('../src/views/ai/AiWorkstation.vue')

  assert.match(workstation, /主动汇报/)
  assert.match(workstation, /关注列表/)
  assert.doesNotMatch(workstation, /预测 \/ 分析 \/ 执行/)
})

test('factory command screens offer scoped ask ai entry points', () => {
  const screens = [
    '../src/views/factory-command/FactoryOverview.vue',
    '../src/views/factory-command/ProductionFlowScreen.vue',
    '../src/views/factory-command/MachineLineScreen.vue',
    '../src/views/factory-command/CoilTrace.vue',
    '../src/views/factory-command/CostBenefitScreen.vue',
    '../src/views/factory-command/ExceptionMap.vue'
  ]

  for (const path of screens) {
    const file = source(path)
    assert.match(file, /问 AI/)
    assert.match(file, /scope:\s*\{\s*type:/)
  }
})
