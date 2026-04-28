<template>
  <article class="ai-message" :class="`ai-message--${message.role}`">
    <div class="ai-message__meta">{{ roleLabel }}</div>
    <div class="ai-message__bubble">
      <div class="ai-message__content">{{ message.content }}</div>
      <div v-if="message.toolCalls.length" class="ai-message__tools">
        <details v-for="(toolCall, index) in message.toolCalls" :key="index" class="ai-message__tool">
          <summary>
            <span>{{ toolCall.name || toolCall.tool || '工具调用' }}</span>
            <span class="ai-message__tool-status">{{ formatToolStatus(toolCall.status) }}</span>
          </summary>
          <pre>{{ formatToolCall(toolCall) }}</pre>
        </details>
      </div>
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  msg: { type: Object, required: true }
})

const message = computed(() => ({
  role: props.msg?.role || 'assistant',
  content: props.msg?.content || '',
  toolCalls: props.msg?.toolCalls || props.msg?.tool_calls || []
}))

const roleLabel = computed(() => (message.value.role === 'user' ? '我' : 'AI'))

function formatToolStatus(status) {
  const labels = {
    pending: '等待中',
    running: '执行中',
    done: '已完成',
    error: '失败'
  }
  return labels[status] || status || '已完成'
}

function formatToolCall(toolCall) {
  return JSON.stringify(toolCall.result ?? toolCall, null, 2)
}
</script>

<style scoped>
.ai-message {
  display: grid;
  gap: 6px;
  max-width: min(760px, 86%);
}

.ai-message--user {
  justify-self: end;
}

.ai-message--assistant {
  justify-self: start;
}

.ai-message__meta {
  color: var(--app-muted);
  font-size: 12px;
  font-weight: 700;
}

.ai-message--user .ai-message__meta {
  text-align: right;
}

.ai-message__bubble {
  border: 1px solid var(--app-border);
  border-radius: 18px;
  background: var(--card-bg);
  box-shadow: var(--app-shadow-xs);
  padding: 12px 14px;
}

.ai-message--user .ai-message__bubble {
  border-color: rgba(0, 113, 227, 0.18);
  background: var(--app-accent);
  color: #ffffff;
}

.ai-message__content {
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 14px;
  line-height: 1.7;
}

.ai-message__tools {
  display: grid;
  gap: 8px;
  margin-top: 10px;
}

.ai-message__tool {
  border-radius: 12px;
  background: rgba(0, 0, 0, 0.04);
  padding: 8px 10px;
}

.ai-message__tool summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  cursor: pointer;
  font-size: 12px;
  font-weight: 700;
}

.ai-message__tool-status {
  color: var(--app-muted);
  font-weight: 600;
}

.ai-message__tool pre {
  max-height: 220px;
  margin: 8px 0 0;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.5;
}
</style>
