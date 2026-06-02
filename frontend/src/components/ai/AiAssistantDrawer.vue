<template>
  <el-drawer
    v-model="visible"
    direction="rtl"
    size="min(520px, 100vw)"
    :with-header="false"
    class="ai-assistant-drawer"
    append-to-body
  >
    <aside class="ai-assistant" data-testid="ai-assistant-drawer">
      <header class="ai-assistant__head">
        <div>
          <span>数据中枢 AI</span>
          <strong>AI 助手</strong>
        </div>
        <button type="button" aria-label="关闭 AI 助手" @click="visible = false">
          <el-icon><Close /></el-icon>
        </button>
      </header>

      <section class="ai-assistant__context" :class="{ 'is-lagging': isLagging }">
        <span>当前上下文</span>
        <strong>{{ currentContext.scope.type }} · {{ currentContext.scope.key }}</strong>
        <em v-if="isLagging">数据滞后 {{ currentContext.freshness.status }}</em>
      </section>

      <nav class="ai-assistant__tabs" aria-label="AI 助手区域">
        <button
          v-for="pane in panes"
          :key="pane.value"
          type="button"
          :class="{ 'is-active': activePane === pane.value }"
          @click="activePane = pane.value"
        >
          <el-icon><component :is="pane.icon" /></el-icon>
          <span>{{ pane.label }}</span>
        </button>
      </nav>

      <section v-if="activePane === 'conversation'" class="ai-assistant__conversation">
        <div class="ai-assistant__messages">
          <div v-if="chatStore.loadingMessages" class="ai-assistant__state">加载中</div>
          <template v-else-if="chatStore.messages.length">
            <article
              v-for="(message, index) in chatStore.messages"
              :key="`${message.timestamp}-${index}`"
              class="ai-assistant__message"
              :class="`is-${message.role}`"
            >
              <span>{{ message.role === 'user' ? '我' : 'AI' }}</span>
              <p>{{ message.content }}</p>
            </article>
          </template>
          <div v-else class="ai-assistant__state">暂无消息</div>
        </div>

        <AiEvidenceRefs :refs="latestEvidence" :missing-data="latestMissingData" />

        <form class="ai-assistant__composer" @submit.prevent="send">
          <textarea
            v-model="draft"
            rows="2"
            placeholder="问当前屏幕里的风险、证据或下一步"
            :disabled="chatStore.streaming"
            @keydown.enter.exact.prevent="send"
          />
          <el-button type="primary" :icon="Promotion" native-type="submit" :loading="chatStore.streaming" :disabled="!canSend">
            发送
          </el-button>
        </form>
      </section>

      <AiBriefingInbox v-else-if="activePane === 'briefings'" />
      <AiWatchlistPanel v-else />
    </aside>
  </el-drawer>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Bell, ChatDotRound, Close, Promotion, Star } from '@element-plus/icons-vue'

import { useAiChatStore } from '../../stores/ai-chat'
import AiBriefingInbox from './AiBriefingInbox.vue'
import AiEvidenceRefs from './AiEvidenceRefs.vue'
import AiWatchlistPanel from './AiWatchlistPanel.vue'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  context: {
    type: Object,
    default: () => ({})
  },
  initialPrompt: {
    type: String,
    default: ''
  }
})
const emit = defineEmits(['update:modelValue', 'prompt-consumed'])

const route = useRoute()
const chatStore = useAiChatStore()
const activePane = ref('conversation')
const draft = ref('')
const panes = [
  { value: 'conversation', label: '对话', icon: ChatDotRound },
  { value: 'briefings', label: '主动汇报', icon: Bell },
  { value: 'watchlist', label: '关注列表', icon: Star }
]

const visible = computed({
  get: () => props.modelValue,
  set: (value) => emit('update:modelValue', value)
})
const currentContext = computed(() => {
  const routeScope = { type: 'route', key: route.path || '/manage/today' }
  const scope = props.context?.scope || routeScope
  return {
    route: props.context?.route || route.path,
    scope,
    freshness: props.context?.freshness || {}
  }
})
const isLagging = computed(() => {
  const status = currentContext.value.freshness?.status
  return ['stale', 'offline', 'offline_or_blocked'].includes(status)
})
const canSend = computed(() => Boolean(draft.value.trim()) && !chatStore.streaming && !chatStore.loadingMessages)
const latestAssistantMessage = computed(() => {
  return [...chatStore.messages].reverse().find((message) => message.role === 'assistant') || null
})
const latestAnswer = computed(() => latestAssistantMessage.value?.payload?.answer || {})
const latestEvidence = computed(() => latestAssistantMessage.value?.toolCalls || latestAnswer.value.evidence_refs || latestAnswer.value.evidenceRefs || [])
const latestMissingData = computed(() => latestAssistantMessage.value?.missingData || latestAnswer.value.missing_data || latestAnswer.value.missingData || [])

watch(
  () => props.modelValue,
  async (open) => {
    if (!open || chatStore.conversations.length) return
    try {
      await chatStore.loadConversations()
    } catch {
      ElMessage.error(chatStore.lastError || '加载对话失败')
    }
  },
  { immediate: true }
)

watch(
  () => [props.modelValue, props.initialPrompt],
  async ([open, prompt]) => {
    const text = String(prompt || '').trim()
    if (!open || !text || chatStore.streaming) return
    activePane.value = 'conversation'
    draft.value = text
    emit('prompt-consumed')
    await send()
  }
)

async function send() {
  const text = draft.value.trim()
  if (!text || chatStore.streaming) return
  draft.value = ''
  try {
    await chatStore.sendMessage(text, {
      scope: currentContext.value.scope,
      intent: 'factory_status'
    })
  } catch {
    ElMessage.error(chatStore.lastError || '发送失败')
  }
}
</script>

<style scoped>
.ai-assistant {
  --ai-drawer-accent: #00f2ff;
  --ai-drawer-line: rgba(0, 242, 255, 0.18);
  --ai-drawer-panel: rgba(6, 29, 51, 0.82);
  --ai-drawer-panel-strong: rgba(2, 12, 25, 0.94);
  --ai-drawer-muted: rgba(185, 223, 235, 0.68);
  position: relative;
  min-height: 100%;
  display: grid;
  grid-template-rows: auto auto auto minmax(0, 1fr);
  gap: 12px;
  padding: 14px;
  overflow: hidden;
  background:
    radial-gradient(circle at 14% 0%, rgba(0, 242, 255, 0.22), transparent 30%),
    radial-gradient(circle at 88% 16%, rgba(0, 118, 255, 0.18), transparent 32%),
    linear-gradient(145deg, #06101f 0%, #071b31 46%, #020b15 100%);
  color: rgba(225, 253, 255, 0.94);
}

:global(.ai-assistant-drawer.el-drawer) {
  border-left: 1px solid rgba(0, 242, 255, 0.22);
  background: #020b15;
  box-shadow: -28px 0 72px rgba(0, 18, 42, 0.5);
}

:global(.ai-assistant-drawer .el-drawer__body) {
  padding: 0;
  background: #020b15;
}

.ai-assistant::before,
.ai-assistant::after {
  position: absolute;
  inset: 0;
  pointer-events: none;
  content: "";
}

.ai-assistant::before {
  opacity: 0.2;
  background:
    linear-gradient(rgba(0, 242, 255, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 242, 255, 0.08) 1px, transparent 1px);
  background-size: 32px 32px;
}

.ai-assistant::after {
  background: linear-gradient(110deg, transparent 8%, rgba(0, 242, 255, 0.11), transparent 58%);
  transform: translateX(-120%);
  animation: aiDrawerSweep 7.5s linear infinite;
}

.ai-assistant__head,
.ai-assistant__context,
.ai-assistant__tabs,
.ai-assistant__composer,
.ai-assistant__conversation {
  position: relative;
  z-index: 1;
}

.ai-assistant__head,
.ai-assistant__context,
.ai-assistant__tabs,
.ai-assistant__composer {
  display: flex;
  align-items: center;
}

.ai-assistant__head {
  justify-content: space-between;
  gap: 12px;
  padding: 12px;
  border: 1px solid var(--ai-drawer-line);
  border-radius: 14px;
  background: linear-gradient(90deg, rgba(8, 43, 74, 0.78), rgba(2, 12, 25, 0.82));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06);
}

.ai-assistant__head div {
  display: grid;
  gap: 2px;
}

.ai-assistant__head span,
.ai-assistant__context span,
.ai-assistant__context em {
  color: var(--ai-drawer-muted);
  font-size: 12px;
  font-style: normal;
  font-weight: 850;
  letter-spacing: 0.08em;
}

.ai-assistant__head strong {
  color: rgba(225, 253, 255, 0.98);
  font-family: var(--xt-font-number);
  font-size: 22px;
  line-height: 1.2;
  letter-spacing: -0.02em;
  text-shadow: 0 0 22px rgba(0, 242, 255, 0.2);
}

.ai-assistant__head button {
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border: 0;
  border-radius: 10px;
  background: rgba(0, 242, 255, 0.08);
  color: rgba(185, 223, 235, 0.86);
  cursor: pointer;
  transition:
    background-color var(--xt-motion-fast) var(--xt-ease),
    color var(--xt-motion-fast) var(--xt-ease),
    transform var(--xt-motion-fast) var(--xt-ease);
}

.ai-assistant__head button:active {
  transform: scale(0.96);
}

@media (hover: hover) {
  .ai-assistant__head button:hover {
    background: rgba(0, 242, 255, 0.16);
    color: #e1fdff;
  }
}

.ai-assistant__context {
  align-items: flex-start;
  flex-direction: column;
  gap: 4px;
  padding: 10px;
  border: 1px solid var(--ai-drawer-line);
  border-radius: 12px;
  background: var(--ai-drawer-panel);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.05),
    0 12px 32px rgba(0, 18, 42, 0.24);
}

.ai-assistant__context strong {
  max-width: 100%;
  overflow: hidden;
  color: #74f5ff;
  font-size: 13px;
  font-weight: 900;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ai-assistant__context.is-lagging {
  border-color: rgba(255, 171, 0, 0.34);
  background: rgba(68, 42, 8, 0.62);
}

.ai-assistant__tabs {
  gap: 6px;
  padding: 5px;
  border: 1px solid var(--ai-drawer-line);
  border-radius: 12px;
  background: rgba(1, 16, 31, 0.72);
  box-shadow: inset 0 0 0 1px rgba(0, 242, 255, 0.05);
}

.ai-assistant__tabs button {
  min-width: 0;
  min-height: 36px;
  display: inline-flex;
  flex: 1;
  align-items: center;
  justify-content: center;
  gap: 6px;
  border: 0;
  border-radius: 9px;
  background: transparent;
  color: rgba(185, 223, 235, 0.76);
  font-size: 13px;
  font-weight: 850;
  cursor: pointer;
  transition:
    background-color var(--xt-motion-fast) var(--xt-ease),
    color var(--xt-motion-fast) var(--xt-ease),
    transform var(--xt-motion-fast) var(--xt-ease);
}

.ai-assistant__tabs button:active {
  transform: scale(0.96);
}

.ai-assistant__tabs button.is-active {
  background: linear-gradient(180deg, rgba(0, 242, 255, 0.18), rgba(0, 118, 255, 0.08));
  color: #e1fdff;
  box-shadow: inset 0 0 0 1px rgba(0, 242, 255, 0.24), 0 0 22px rgba(0, 242, 255, 0.12);
}

.ai-assistant__conversation {
  min-height: 0;
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto auto;
  gap: 10px;
}

.ai-assistant__messages {
  min-height: 240px;
  display: grid;
  align-content: start;
  gap: 8px;
  overflow-y: auto;
  padding: 10px;
  border: 1px solid var(--ai-drawer-line);
  border-radius: 12px;
  background:
    linear-gradient(90deg, rgba(0, 242, 255, 0.07) 1px, transparent 1px),
    linear-gradient(rgba(0, 242, 255, 0.05) 1px, transparent 1px),
    rgba(2, 12, 25, 0.78);
  background-size: 30px 30px;
  box-shadow: inset 0 0 0 1px rgba(0, 242, 255, 0.04);
}

.ai-assistant__message {
  max-width: 86%;
  display: grid;
  gap: 4px;
  justify-self: start;
  padding: 9px 10px;
  border: 1px solid rgba(0, 242, 255, 0.14);
  border-radius: 12px;
  background: rgba(7, 29, 51, 0.86);
  color: rgba(225, 253, 255, 0.9);
}

.ai-assistant__message.is-user {
  justify-self: end;
  border-color: rgba(0, 242, 255, 0.3);
  background: linear-gradient(180deg, rgba(0, 118, 255, 0.86), rgba(0, 64, 128, 0.9));
  color: #fff;
}

.ai-assistant__message span {
  font-size: 11px;
  font-weight: 900;
  opacity: 0.78;
}

.ai-assistant__message p {
  margin: 0;
  font-size: 13px;
  line-height: 1.55;
  white-space: pre-wrap;
}

.ai-assistant__state {
  align-self: center;
  justify-self: center;
  color: var(--ai-drawer-muted);
  font-size: 13px;
}

.ai-assistant__composer {
  align-items: flex-end;
  gap: 8px;
  padding: 10px;
  border: 1px solid var(--ai-drawer-line);
  border-radius: 12px;
  background: var(--ai-drawer-panel-strong);
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.05),
    0 12px 32px rgba(0, 18, 42, 0.24);
}

.ai-assistant__composer textarea {
  min-width: 0;
  min-height: 48px;
  flex: 1;
  resize: vertical;
  border: 0;
  background: transparent;
  color: rgba(225, 253, 255, 0.94);
  font: inherit;
  font-size: 13px;
  line-height: 1.55;
  outline: none;
}

.ai-assistant__composer textarea::placeholder {
  color: rgba(185, 223, 235, 0.48);
}

.ai-assistant__composer :deep(.el-button--primary) {
  border: 0;
  background: linear-gradient(135deg, #00f2ff, #0b63f6);
  color: #00192f;
  font-weight: 900;
  box-shadow: 0 0 22px rgba(0, 242, 255, 0.22);
}

@keyframes aiDrawerSweep {
  to {
    transform: translateX(120%);
  }
}

@media (max-width: 520px) {
  .ai-assistant {
    padding: 10px;
  }

  .ai-assistant__composer {
    align-items: stretch;
    flex-direction: column;
  }

  .ai-assistant__composer :deep(.el-button) {
    width: 100%;
  }
}
</style>
