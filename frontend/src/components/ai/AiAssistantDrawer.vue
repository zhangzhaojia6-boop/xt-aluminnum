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
  const routeScope = { type: 'route', key: route.path || '/manage/overview' }
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
  min-height: 100%;
  display: grid;
  grid-template-rows: auto auto auto minmax(0, 1fr);
  gap: 12px;
  padding: 14px;
  background: linear-gradient(180deg, #fff, var(--xt-bg-panel-soft));
  color: var(--xt-text);
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
}

.ai-assistant__head div {
  display: grid;
  gap: 2px;
}

.ai-assistant__head span,
.ai-assistant__context span,
.ai-assistant__context em {
  color: var(--xt-text-muted);
  font-size: 12px;
  font-style: normal;
  font-weight: 850;
}

.ai-assistant__head strong {
  color: var(--xt-text);
  font-size: 20px;
  line-height: 1.2;
  letter-spacing: 0;
}

.ai-assistant__head button {
  width: 40px;
  height: 40px;
  display: grid;
  place-items: center;
  border: 0;
  border-radius: 8px;
  background: var(--xt-bg-panel-soft);
  color: var(--xt-text-secondary);
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
    background: #fff;
    color: var(--xt-text);
  }
}

.ai-assistant__context {
  align-items: flex-start;
  flex-direction: column;
  gap: 4px;
  padding: 10px;
  border-radius: 8px;
  background: #fff;
  box-shadow:
    inset 0 0 0 1px rgba(43, 93, 178, 0.1),
    0 8px 24px rgba(25, 62, 118, 0.06);
}

.ai-assistant__context strong {
  max-width: 100%;
  overflow: hidden;
  color: var(--xt-primary);
  font-size: 13px;
  font-weight: 900;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ai-assistant__context.is-lagging {
  background: rgba(255, 247, 237, 0.94);
}

.ai-assistant__tabs {
  gap: 6px;
  padding: 5px;
  border-radius: 8px;
  background: var(--xt-bg-panel-soft);
  box-shadow: inset 0 0 0 1px rgba(43, 93, 178, 0.1);
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
  border-radius: 6px;
  background: transparent;
  color: var(--xt-text-secondary);
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
  background: #fff;
  color: var(--xt-primary);
  box-shadow: 0 4px 16px rgba(25, 62, 118, 0.08);
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
  border-radius: 8px;
  background:
    linear-gradient(90deg, rgba(15, 23, 42, 0.026) 1px, transparent 1px),
    linear-gradient(rgba(15, 23, 42, 0.02) 1px, transparent 1px),
    #fff;
  background-size: 30px 30px;
  box-shadow: inset 0 0 0 1px rgba(43, 93, 178, 0.1);
}

.ai-assistant__message {
  max-width: 86%;
  display: grid;
  gap: 4px;
  justify-self: start;
  padding: 9px 10px;
  border-radius: 8px;
  background: var(--xt-bg-panel-soft);
}

.ai-assistant__message.is-user {
  justify-self: end;
  background: var(--xt-primary);
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
  color: var(--xt-text-muted);
  font-size: 13px;
}

.ai-assistant__composer {
  align-items: flex-end;
  gap: 8px;
  padding: 10px;
  border-radius: 8px;
  background: #fff;
  box-shadow:
    inset 0 0 0 1px rgba(43, 93, 178, 0.1),
    0 8px 22px rgba(25, 62, 118, 0.06);
}

.ai-assistant__composer textarea {
  min-width: 0;
  min-height: 48px;
  flex: 1;
  resize: vertical;
  border: 0;
  background: transparent;
  color: var(--xt-text);
  font: inherit;
  font-size: 13px;
  line-height: 1.55;
  outline: none;
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
