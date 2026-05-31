<template>
  <section class="ai-workstation" data-testid="ai-workstation-page">
    <div class="ai-workstation__grid" aria-hidden="true"></div>
    <AiConversationList
      :conversations="store.conversations"
      :current-id="store.currentId"
      :loading="store.loadingConversations"
      :disabled="store.streaming"
      @new="handleNew"
      @select="store.loadMessages"
      @delete="handleDelete"
    />

    <main class="ai-workstation__main">
      <header class="ai-workstation__bar">
        <div>
          <span class="ai-workstation__eyebrow">
            <i aria-hidden="true"></i>
            COMMAND AI
          </span>
          <h1>{{ store.currentConversation?.title || 'AI 工作台' }}</h1>
          <span>{{ statusText }} · 证据上下文</span>
        </div>
        <div class="ai-workstation__telemetry" aria-label="AI 工作台状态">
          <span v-for="stat in aiStats" :key="stat.label">
            <small>{{ stat.label }}</small>
            <strong>{{ stat.value }}</strong>
          </span>
        </div>
      </header>

      <nav class="ai-workstation__tabs" aria-label="AI 工作台区域">
        <button
          v-for="tab in tabs"
          :key="tab.value"
          type="button"
          :class="{ 'is-active': activeTab === tab.value }"
          @click="activeTab = tab.value"
        >
          {{ tab.label }}
        </button>
      </nav>

      <div v-if="activeTab === 'conversation'" ref="messagesRef" class="ai-workstation__messages">
        <XtAiThinking
          v-if="showThinkingState"
          :streaming="store.streaming || store.loadingMessages"
          :tool-calls="activeToolCalls"
          :last-error="store.lastError"
        />
        <div v-if="store.loadingMessages && !store.messages.length" class="ai-workstation__state">加载中</div>
        <template v-else-if="store.messages.length">
          <AiChatMessage v-for="(message, index) in store.messages" :key="`${message.timestamp}-${index}`" :msg="message" />
        </template>
        <div v-else class="ai-workstation__state">暂无消息</div>
      </div>

      <div v-else-if="activeTab === 'briefings'" class="ai-workstation__panel">
        <AiBriefingInbox />
      </div>

      <div v-else class="ai-workstation__panel">
        <AiWatchlistPanel />
      </div>

      <form v-if="activeTab === 'conversation'" class="ai-workstation__composer" @submit.prevent="send">
        <div class="ai-workstation__composer-shell">
          <span class="ai-workstation__composer-mark">AI</span>
          <textarea
            v-model="input"
            rows="1"
            placeholder="问 AI 总管：今天哪个车间风险最高，下一步怎么做？"
            :disabled="store.loadingMessages"
            @keydown.enter.exact.prevent="send"
          />
          <div class="ai-workstation__composer-tags" aria-hidden="true">
            <span>现场</span>
            <span>规则</span>
            <span>日报</span>
          </div>
        </div>
        <div class="ai-workstation__composer-actions">
          <el-button v-if="store.streaming" type="danger" @click="store.stopGeneration">停止</el-button>
          <el-button v-else type="primary" native-type="submit" :disabled="!canSend">发送</el-button>
        </div>
      </form>
    </main>
  </section>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { useAiChatStore } from '../../stores/ai-chat'
import AiBriefingInbox from '../../components/ai/AiBriefingInbox.vue'
import AiWatchlistPanel from '../../components/ai/AiWatchlistPanel.vue'
import { XtAiThinking } from '../../components/xt'
import AiChatMessage from './AiChatMessage.vue'
import AiConversationList from './AiConversationList.vue'

const store = useAiChatStore()
const input = ref('')
const messagesRef = ref(null)
const activeTab = ref('conversation')
const tabs = [
  { value: 'conversation', label: '对话' },
  { value: 'briefings', label: '主动汇报' },
  { value: 'watchlist', label: '关注列表' }
]

const canSend = computed(() => Boolean(input.value.trim()) && !store.streaming && !store.loadingMessages)
const activeToolCalls = computed(() => {
  return store.messages.flatMap((message) => message.toolCalls || message.tool_calls || []).filter((toolCall) => ['pending', 'running'].includes(toolCall?.status))
})
const aiStats = computed(() => [
  { label: '对话', value: store.conversations.length },
  { label: '消息', value: store.messages.length },
  { label: '证据', value: activeToolCalls.value.length }
])
const showThinkingState = computed(() => store.loadingMessages || store.streaming || activeToolCalls.value.length > 0 || Boolean(store.lastError))
const statusText = computed(() => {
  if (store.streaming) return '生成中'
  if (store.loadingMessages || store.loadingConversations) return '加载中'
  if (store.lastError) return store.lastError
  return '就绪'
})

onMounted(async () => {
  try {
    await store.loadConversations()
  } catch {
    ElMessage.error(store.lastError || '加载对话失败')
  }
})

watch(
  () => [store.messages.length, store.messages[store.messages.length - 1]?.content, store.messages[store.messages.length - 1]?.toolCalls?.length],
  () => {
    nextTick(() => {
      if (messagesRef.value) messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    })
  }
)

async function handleNew() {
  try {
    await store.createConversation()
  } catch {
    ElMessage.error(store.lastError || '创建对话失败')
  }
}

async function handleDelete(id) {
  try {
    await ElMessageBox.confirm('确认删除该对话？', '删除对话', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning'
    })
    await store.deleteConversation(id)
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') ElMessage.error(store.lastError || '删除对话失败')
  }
}

async function send() {
  const text = input.value.trim()
  if (!text || store.streaming) return
  input.value = ''
  try {
    await store.sendMessage(text)
  } catch {
    ElMessage.error(store.lastError || '发送失败')
  }
}
</script>

<style scoped>
.ai-workstation {
  --ai-accent: #00f2ff;
  --ai-accent-soft: rgba(0, 242, 255, 0.12);
  --ai-line: rgba(0, 242, 255, 0.16);
  --ai-line-strong: rgba(0, 242, 255, 0.34);
  --ai-panel: rgba(6, 29, 51, 0.82);
  --ai-panel-strong: rgba(2, 12, 25, 0.94);
  --ai-muted: rgba(185, 223, 235, 0.66);
  position: relative;
  isolation: isolate;
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  min-height: calc(100vh - 96px);
  overflow: hidden;
  border: 1px solid var(--ai-line);
  border-radius: 18px;
  background:
    radial-gradient(circle at 15% 0%, rgba(0, 242, 255, 0.18), transparent 28%),
    radial-gradient(circle at 88% 12%, rgba(0, 118, 255, 0.16), transparent 30%),
    linear-gradient(135deg, rgba(3, 16, 31, 0.96), rgba(1, 7, 15, 0.98));
  box-shadow:
    inset 0 1px 0 rgba(255, 255, 255, 0.06),
    0 22px 60px rgba(0, 18, 42, 0.28);
}

.ai-workstation__grid {
  position: absolute;
  inset: 0;
  z-index: -1;
  opacity: 0.22;
  background:
    linear-gradient(rgba(0, 242, 255, 0.08) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 242, 255, 0.08) 1px, transparent 1px);
  background-size: 34px 34px;
  mask-image: linear-gradient(180deg, #000, transparent 82%);
  pointer-events: none;
}

.ai-workstation__grid::after {
  position: absolute;
  inset: 0;
  background: linear-gradient(90deg, transparent, rgba(0, 242, 255, 0.18), transparent);
  transform: translateX(-70%);
  animation: aiSweep 7s linear infinite;
  content: "";
}

.ai-workstation__main {
  display: flex;
  flex: 1;
  min-width: 0;
  flex-direction: column;
}

.ai-workstation__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  min-height: 92px;
  padding: 18px 22px;
  border-bottom: 1px solid var(--ai-line);
  background:
    linear-gradient(90deg, rgba(6, 29, 51, 0.82), rgba(2, 12, 25, 0.72)),
    rgba(2, 12, 25, 0.7);
  box-shadow: inset 0 -1px 0 rgba(255, 255, 255, 0.04);
}

.ai-workstation__eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: rgba(116, 245, 255, 0.82);
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.14em;
}

.ai-workstation__eyebrow i {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: var(--ai-accent);
  box-shadow: 0 0 0 6px rgba(0, 242, 255, 0.1), 0 0 22px rgba(0, 242, 255, 0.52);
  animation: aiPulse 1.8s ease-out infinite;
}

.ai-workstation__bar h1 {
  margin: 5px 0 2px;
  color: rgba(225, 253, 255, 0.96);
  font-family: var(--xt-font-number);
  font-size: clamp(24px, 3vw, 36px);
  line-height: 1.08;
  letter-spacing: -0.035em;
  text-shadow: 0 0 22px rgba(0, 242, 255, 0.18);
}

.ai-workstation__bar span {
  color: var(--ai-muted);
  font-size: 13px;
}

.ai-workstation__telemetry {
  flex: 0 0 auto;
  display: grid;
  grid-template-columns: repeat(3, minmax(74px, 1fr));
  gap: 10px;
}

.ai-workstation__telemetry span {
  min-width: 0;
  display: grid;
  gap: 5px;
  padding: 10px 12px;
  border: 1px solid var(--ai-line);
  border-radius: 12px;
  background:
    linear-gradient(180deg, rgba(10, 38, 66, 0.74), rgba(2, 12, 25, 0.88)),
    rgba(2, 12, 25, 0.76);
}

.ai-workstation__telemetry small {
  color: rgba(116, 245, 255, 0.72);
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.12em;
}

.ai-workstation__telemetry strong {
  color: rgba(225, 253, 255, 0.96);
  font-family: var(--xt-font-number);
  font-size: 22px;
  line-height: 1;
}

.ai-workstation__tabs {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  overflow-x: auto;
  border-bottom: 1px solid var(--ai-line);
  background: rgba(1, 16, 31, 0.62);
}

.ai-workstation__tabs button {
  position: relative;
  min-height: 36px;
  padding: 0 14px;
  overflow: hidden;
  border: 1px solid var(--ai-line);
  border-radius: 10px;
  background: rgba(2, 12, 25, 0.6);
  color: var(--ai-muted);
  font-size: 13px;
  font-weight: 850;
  cursor: pointer;
  transition:
    background-color var(--xt-motion-fast) var(--xt-ease),
    color var(--xt-motion-fast) var(--xt-ease),
    transform var(--xt-motion-fast) var(--xt-ease);
}

.ai-workstation__tabs button::after {
  position: absolute;
  inset: auto 10px 6px;
  height: 2px;
  border-radius: 999px;
  background: linear-gradient(90deg, transparent, var(--ai-accent), transparent);
  opacity: 0;
  transform: scaleX(0.5);
  transition: opacity var(--xt-motion-fast) var(--xt-ease), transform var(--xt-motion-fast) var(--xt-ease);
  content: "";
}

.ai-workstation__tabs button:active {
  transform: scale(0.96);
}

.ai-workstation__tabs button.is-active {
  border-color: var(--ai-line-strong);
  background: rgba(0, 242, 255, 0.12);
  color: #e1fdff;
  box-shadow: 0 0 20px rgba(0, 242, 255, 0.12);
}

.ai-workstation__tabs button.is-active::after {
  opacity: 1;
  transform: scaleX(1);
}

.ai-workstation__messages {
  display: grid;
  align-content: start;
  gap: 16px;
  flex: 1;
  overflow-y: auto;
  padding: 22px;
  background:
    radial-gradient(circle at 50% 0%, rgba(0, 242, 255, 0.1), transparent 28%),
    linear-gradient(90deg, rgba(0, 242, 255, 0.035) 1px, transparent 1px),
    linear-gradient(rgba(0, 242, 255, 0.028) 1px, transparent 1px),
    rgba(2, 12, 25, 0.74);
  background-size: 34px 34px;
  scrollbar-width: thin;
  scrollbar-color: rgba(0, 242, 255, 0.36) transparent;
}

.ai-workstation__panel {
  flex: 1;
  overflow-y: auto;
  padding: 22px;
  background: rgba(2, 12, 25, 0.72);
}

.ai-workstation__state {
  align-self: start;
  justify-self: center;
  min-width: 160px;
  margin-top: var(--xt-space-5);
  padding: 12px 16px;
  border: 1px solid var(--ai-line);
  border-radius: 12px;
  background: rgba(1, 16, 31, 0.78);
  color: var(--ai-muted);
  font-size: 14px;
  text-align: center;
  box-shadow: 0 0 24px rgba(0, 242, 255, 0.08);
}

.ai-workstation__composer {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: flex-end;
  gap: 12px;
  padding: 16px 18px 18px;
  border-top: 1px solid var(--ai-line);
  background:
    linear-gradient(180deg, rgba(6, 29, 51, 0.72), rgba(2, 12, 25, 0.92)),
    rgba(2, 12, 25, 0.84);
}

.ai-workstation__composer-shell {
  min-width: 0;
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border: 1px solid var(--ai-line);
  border-radius: 12px;
  background: rgba(1, 16, 31, 0.78);
  box-shadow: inset 0 -1px 0 rgba(0, 242, 255, 0.18);
}

.ai-workstation__composer-mark {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: 10px;
  background: linear-gradient(180deg, rgba(116, 245, 255, 0.96), rgba(0, 185, 214, 0.92));
  color: #00252b;
  font-family: var(--xt-font-number);
  font-size: 12px;
  font-weight: 900;
}

.ai-workstation__composer textarea {
  min-width: 0;
  min-height: 44px;
  max-height: 128px;
  resize: vertical;
  border: 0;
  background: transparent;
  color: rgba(225, 253, 255, 0.94);
  font: inherit;
  line-height: 1.6;
  padding: 9px 0;
  outline: none;
}

.ai-workstation__composer textarea::placeholder {
  color: rgba(185, 223, 235, 0.45);
}

.ai-workstation__composer-shell:focus-within {
  border-color: var(--ai-line-strong);
  box-shadow: 0 0 0 3px rgba(0, 242, 255, 0.08), 0 0 28px rgba(0, 242, 255, 0.12);
}

.ai-workstation__composer-tags {
  display: flex;
  gap: 6px;
}

.ai-workstation__composer-tags span {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 0 8px;
  border: 1px solid rgba(0, 242, 255, 0.12);
  border-radius: 999px;
  background: rgba(0, 242, 255, 0.06);
  color: rgba(116, 245, 255, 0.78);
  font-size: 12px;
  font-weight: 800;
}

.ai-workstation__composer-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ai-workstation :deep(.ai-conversations) {
  position: relative;
  width: 280px;
  min-width: 220px;
  border-right: 1px solid var(--ai-line);
  background:
    linear-gradient(180deg, rgba(6, 29, 51, 0.82), rgba(1, 9, 19, 0.94)),
    rgba(1, 16, 31, 0.82);
}

.ai-workstation :deep(.ai-conversations__header) {
  min-height: 92px;
  border-bottom: 1px solid var(--ai-line);
  background: rgba(1, 16, 31, 0.76);
}

.ai-workstation :deep(.ai-conversations__header span) {
  color: rgba(116, 245, 255, 0.78);
  letter-spacing: 0.12em;
}

.ai-workstation :deep(.ai-conversations__header strong) {
  color: rgba(225, 253, 255, 0.96);
  font-family: var(--xt-font-number);
}

.ai-workstation :deep(.ai-conversations__item) {
  border-radius: 12px;
  color: rgba(225, 253, 255, 0.9);
}

.ai-workstation :deep(.ai-conversations__item:hover),
.ai-workstation :deep(.ai-conversations__item.is-active) {
  border-color: var(--ai-line-strong);
  background: rgba(0, 242, 255, 0.1);
  box-shadow: 0 0 22px rgba(0, 242, 255, 0.1);
}

.ai-workstation :deep(.ai-conversations__time),
.ai-workstation :deep(.ai-conversations__state) {
  color: var(--ai-muted);
}

.ai-workstation :deep(.ai-message) {
  max-width: min(780px, 88%);
}

.ai-workstation :deep(.ai-message__meta) {
  color: rgba(116, 245, 255, 0.72);
  letter-spacing: 0.08em;
}

.ai-workstation :deep(.ai-message__bubble),
.ai-workstation :deep(.ai-message__tool),
.ai-workstation :deep(.ai-message__tool-row) {
  border-color: var(--ai-line);
  background:
    linear-gradient(180deg, rgba(10, 38, 66, 0.74), rgba(2, 12, 25, 0.9)),
    rgba(2, 12, 25, 0.84);
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05);
}

.ai-workstation :deep(.ai-message--user .ai-message__bubble) {
  border-color: rgba(0, 242, 255, 0.36);
  background:
    linear-gradient(180deg, rgba(0, 242, 255, 0.22), rgba(0, 104, 153, 0.2)),
    rgba(0, 242, 255, 0.1);
  color: #e1fdff;
}

.ai-workstation :deep(.ai-message__content),
.ai-workstation :deep(.ai-message__tool-row strong),
.ai-workstation :deep(.ai-message__tool summary) {
  color: rgba(225, 253, 255, 0.92);
}

.ai-workstation :deep(.ai-message__tool-row small),
.ai-workstation :deep(.ai-message__tool-row em),
.ai-workstation :deep(.ai-message__tool-status) {
  color: var(--ai-muted);
}

.ai-workstation :deep(.xt-ai-action-card) {
  border-color: rgba(0, 242, 255, 0.16);
  background:
    linear-gradient(180deg, rgba(10, 38, 66, 0.82), rgba(2, 12, 25, 0.92)),
    rgba(2, 12, 25, 0.84);
  color: rgba(225, 253, 255, 0.92);
}

.ai-workstation :deep(.xt-ai-action-card__icon) {
  background: rgba(0, 242, 255, 0.12);
  color: #74f5ff;
}

.ai-workstation :deep(.xt-ai-action-card__body strong) {
  color: rgba(225, 253, 255, 0.96);
}

.ai-workstation :deep(.xt-ai-action-card__body span) {
  color: var(--ai-muted);
}

.ai-workstation :deep(.el-button--primary) {
  border: 0;
  background: linear-gradient(180deg, rgba(116, 245, 255, 1), rgba(0, 185, 214, 0.92));
  color: #00252b;
  font-weight: 900;
  box-shadow: 0 0 24px rgba(0, 242, 255, 0.22);
}

@keyframes aiSweep {
  to { transform: translateX(70%); }
}

@keyframes aiPulse {
  0% { box-shadow: 0 0 0 0 rgba(0, 242, 255, 0.3), 0 0 22px rgba(0, 242, 255, 0.52); }
  100% { box-shadow: 0 0 0 12px rgba(0, 242, 255, 0), 0 0 22px rgba(0, 242, 255, 0.52); }
}

@media (max-width: 900px) {
  .ai-workstation {
    display: flex;
    flex-direction: column;
    min-height: calc(100vh - 72px);
    border-radius: 0;
  }

  .ai-workstation__bar {
    align-items: stretch;
    flex-direction: column;
  }

  .ai-workstation__telemetry {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .ai-workstation :deep(.ai-conversations) {
    width: 100%;
    max-height: 220px;
    border-right: 0;
    border-bottom: 1px solid var(--ai-line);
  }

  .ai-workstation__composer {
    grid-template-columns: 1fr;
    align-items: stretch;
  }

  .ai-workstation__composer-shell {
    grid-template-columns: 34px minmax(0, 1fr);
  }

  .ai-workstation__composer-tags {
    grid-column: 1 / -1;
  }

  .ai-workstation__composer-actions {
    justify-content: stretch;
  }

  .ai-workstation__composer-actions :deep(.el-button) {
    width: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .ai-workstation__grid::after,
  .ai-workstation__eyebrow i {
    animation: none;
  }
}
</style>
