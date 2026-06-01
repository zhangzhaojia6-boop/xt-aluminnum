import test from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'

function source(path) {
  return readFileSync(new URL(path, import.meta.url), 'utf8')
}

test('management shell renders persistent assistant drawer', () => {
  const shell = source('../src/layout/ManageShell.vue')

  assert.match(shell, /AiAssistantDrawer/)
  assert.match(shell, /assistantOpen/)
  assert.match(shell, /AI_ASSISTANT_OPEN_EVENT/)
  assert.match(shell, /initial-prompt/)
  assert.match(shell, /openAssistantFromTopbar/)
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
  assert.match(drawer, /prompt-consumed/)
  assert.match(drawer, /activePane\.value = 'conversation'/)
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

test('ai workstation aligns to the cyber industrial visual system without changing chat wiring', () => {
  const workstation = source('../src/views/ai/AiWorkstation.vue')

  assert.match(workstation, /data-testid="ai-workstation-page"/)
  assert.match(workstation, /COMMAND AI/)
  assert.match(workstation, /aiStats/)
  assert.match(workstation, /runtimeText/)
  assert.match(workstation, /事实约束 LLM/)
  assert.match(workstation, /规则兜底/)
  assert.match(workstation, /store\.sendMessage/)
  assert.match(workstation, /store\.loadConversations/)
  assert.match(workstation, /store\.loadRuntime/)
  assert.match(workstation, /AiBriefingInbox/)
  assert.match(workstation, /AiWatchlistPanel/)
  assert.match(workstation, /--ai-accent:\s*#00f2ff/)
  assert.match(workstation, /aiSweep/)
  assert.match(workstation, /aiPulse/)
  assert.match(workstation, /:deep\(\.ai-conversations\)/)
  assert.match(workstation, /:deep\(\.ai-message__bubble\)/)
  assert.match(workstation, /:deep\(\.xt-ai-action-card\)/)
})

test('current management shell uses canonical assistant label and route context', () => {
  const shell = source('../src/layout/ManageShell.vue')
  const drawer = source('../src/components/ai/AiAssistantDrawer.vue')

  assert.match(shell, /AI 助手/)
  assert.match(drawer, /\/manage\/today/)
  assert.doesNotMatch(shell, /AI 总控中心/)
  assert.doesNotMatch(shell, /review-brain-center/)
  assert.doesNotMatch(drawer, /\/manage\/overview/)
})

test('retired factory command screens are no longer AI entry surfaces', () => {
  const retiredScreens = [
    '../src/views/factory-command/FactoryOverview.vue',
    '../src/views/factory-command/ProductionFlowScreen.vue',
    '../src/views/factory-command/MachineLineScreen.vue',
    '../src/views/factory-command/CoilTrace.vue',
    '../src/views/factory-command/CostBenefitScreen.vue',
    '../src/views/factory-command/ExceptionMap.vue'
  ]

  for (const path of retiredScreens) {
    assert.equal(existsSync(new URL(path, import.meta.url)), false, `${path} should be deleted`)
  }

  const destination = source('../src/views/factory-command/DestinationScreen.vue')
  assert.doesNotMatch(destination, /问 AI/)
})
