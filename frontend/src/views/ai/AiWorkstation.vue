<template>
  <section class="ai-workstation">
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
          <h1>{{ store.currentConversation?.title || 'AI 工作台' }}</h1>
          <span>{{ statusText }}</span>
        </div>
      </header>

      <div ref="messagesRef" class="ai-workstation__messages">
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

      <form class="ai-workstation__composer" @submit.prevent="send">
        <div class="ai-workstation__composer-shell">
          <span class="ai-workstation__composer-mark">AI</span>
          <textarea
            v-model="input"
            rows="1"
            placeholder="输入消息"
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
import { XtAiThinking } from '../../components/xt'
import AiChatMessage from './AiChatMessage.vue'
import AiConversationList from './AiConversationList.vue'

const store = useAiChatStore()
const input = ref('')
const messagesRef = ref(null)

const canSend = computed(() => Boolean(input.value.trim()) && !store.streaming && !store.loadingMessages)
const activeToolCalls = computed(() => {
  return store.messages.flatMap((message) => message.toolCalls || message.tool_calls || []).filter((toolCall) => ['pending', 'running'].includes(toolCall?.status))
})
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
  display: grid;
  grid-template-columns: 280px minmax(0, 1fr);
  min-height: calc(100vh - 96px);
  overflow: hidden;
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-2xl);
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-md);
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
  min-height: 68px;
  padding: 14px 20px;
  border-bottom: 1px solid var(--xt-border-light);
  background: var(--xt-command-surface);
}

.ai-workstation__bar h1 {
  margin: 0;
  color: var(--xt-text);
  font-size: 18px;
  line-height: 1.4;
  letter-spacing: 0;
}

.ai-workstation__bar span {
  color: var(--xt-text-secondary);
  font-size: 13px;
}

.ai-workstation__messages {
  display: grid;
  align-content: start;
  gap: 14px;
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background:
    linear-gradient(90deg, rgba(15, 23, 42, 0.025) 1px, transparent 1px),
    linear-gradient(rgba(15, 23, 42, 0.02) 1px, transparent 1px),
    var(--xt-bg-panel-soft);
  background-size: 34px 34px;
}

.ai-workstation__state {
  align-self: start;
  justify-self: center;
  min-width: 160px;
  margin-top: var(--xt-space-5);
  padding: 12px 16px;
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-lg);
  background: var(--xt-bg-panel);
  color: var(--xt-text-secondary);
  font-size: 14px;
  text-align: center;
  box-shadow: var(--xt-shadow-sm);
}

.ai-workstation__composer {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: flex-end;
  gap: 12px;
  padding: 14px 16px 16px;
  border-top: 1px solid var(--xt-border-light);
  background: var(--xt-bg-panel);
}

.ai-workstation__composer-shell {
  min-width: 0;
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-xl);
  background: var(--xt-bg-panel-soft);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.72);
}

.ai-workstation__composer-mark {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: var(--xt-radius-lg);
  background: var(--xt-bg-ink);
  color: #ffffff;
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
  color: var(--xt-text);
  font: inherit;
  line-height: 1.6;
  padding: 9px 0;
  outline: none;
}

.ai-workstation__composer-shell:focus-within {
  border-color: rgba(0, 113, 227, 0.45);
  box-shadow: var(--app-focus-ring);
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
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-pill);
  background: var(--xt-bg-panel);
  color: var(--xt-text-muted);
  font-size: 12px;
  font-weight: 800;
}

.ai-workstation__composer-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

@media (max-width: 900px) {
  .ai-workstation {
    display: flex;
    flex-direction: column;
    min-height: calc(100vh - 72px);
    border-radius: 0;
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
</style>
