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
        <div v-if="store.loadingMessages" class="ai-workstation__state">加载中</div>
        <template v-else-if="store.messages.length">
          <AiChatMessage v-for="(message, index) in store.messages" :key="`${message.timestamp}-${index}`" :msg="message" />
        </template>
        <div v-else class="ai-workstation__state">暂无消息</div>
      </div>

      <form class="ai-workstation__composer" @submit.prevent="send">
        <textarea
          v-model="input"
          rows="1"
          placeholder="输入消息"
          :disabled="store.loadingMessages"
          @keydown.enter.exact.prevent="send"
        />
        <el-button v-if="store.streaming" type="danger" @click="store.stopGeneration">停止</el-button>
        <el-button v-else type="primary" native-type="submit" :disabled="!canSend">发送</el-button>
      </form>
    </main>
  </section>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { useAiChatStore } from '../../stores/ai-chat'
import AiChatMessage from './AiChatMessage.vue'
import AiConversationList from './AiConversationList.vue'

const store = useAiChatStore()
const input = ref('')
const messagesRef = ref(null)

const canSend = computed(() => Boolean(input.value.trim()) && !store.streaming && !store.loadingMessages)
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
  () => [store.messages.length, store.messages[store.messages.length - 1]?.content],
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
  display: flex;
  min-height: calc(100vh - 96px);
  overflow: hidden;
  border: 1px solid var(--app-border);
  border-radius: var(--radius-card);
  background: var(--card-bg);
  box-shadow: var(--shadow-card);
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
  min-height: 72px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--app-border);
}

.ai-workstation__bar h1 {
  margin: 0;
  color: var(--app-text);
  font-size: 18px;
  line-height: 1.4;
}

.ai-workstation__bar span {
  color: var(--app-muted);
  font-size: 13px;
}

.ai-workstation__messages {
  display: grid;
  align-content: start;
  gap: 16px;
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: linear-gradient(180deg, rgba(245, 245, 247, 0.58), rgba(255, 255, 255, 0.9));
}

.ai-workstation__state {
  align-self: center;
  justify-self: center;
  color: var(--app-muted);
  font-size: 14px;
}

.ai-workstation__composer {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  padding: 14px 16px;
  border-top: 1px solid var(--app-border);
  background: rgba(255, 255, 255, 0.9);
}

.ai-workstation__composer textarea {
  flex: 1;
  min-height: 40px;
  max-height: 128px;
  resize: vertical;
  border: 1px solid var(--app-border);
  border-radius: var(--radius-control);
  color: var(--app-text);
  font: inherit;
  line-height: 1.6;
  padding: 9px 12px;
  outline: none;
}

.ai-workstation__composer textarea:focus {
  border-color: rgba(0, 113, 227, 0.45);
  box-shadow: var(--app-focus-ring);
}

@media (max-width: 900px) {
  .ai-workstation {
    flex-direction: column;
    min-height: calc(100vh - 72px);
    border-radius: 0;
  }

  .ai-workstation__composer {
    align-items: stretch;
  }
}
</style>
