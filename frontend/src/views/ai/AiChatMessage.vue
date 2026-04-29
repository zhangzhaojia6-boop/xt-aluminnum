<template>
  <article class="ai-message" :class="`ai-message--${message.role}`">
    <div class="ai-message__meta">{{ roleLabel }}</div>
    <div class="ai-message__bubble">
      <div class="ai-message__content">{{ message.content }}</div>
      <div v-if="message.toolCalls.length" class="ai-message__tools">
        <div class="ai-message__tool-grid">
          <div
            v-for="(toolCall, index) in message.toolCalls"
            :key="`row-${index}`"
            class="ai-message__tool-row"
            :class="`is-${normalizeToolStatus(toolCall.status)}`"
          >
            <span class="ai-message__tool-dot" />
            <div>
              <strong>{{ toolTitle(toolCall) }}</strong>
              <small>{{ toolSummary(toolCall) }}</small>
            </div>
            <em>{{ formatToolStatus(toolCall.status) }}</em>
          </div>
        </div>

        <div v-if="actionCards.length" class="ai-message__actions">
          <XtAiActionCard
            v-for="card in actionCards"
            :key="card.key"
            :title="card.title"
            :subtitle="card.subtitle"
            :status="card.status"
          />
        </div>

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

import { XtAiActionCard } from '../../components/xt'

const props = defineProps({
  msg: { type: Object, required: true }
})

const message = computed(() => ({
  role: props.msg?.role || 'assistant',
  content: props.msg?.content || '',
  toolCalls: props.msg?.toolCalls || props.msg?.tool_calls || []
}))

const roleLabel = computed(() => (message.value.role === 'user' ? '我' : 'AI'))
const actionCards = computed(() => {
  if (message.value.role !== 'assistant') return []
  return message.value.toolCalls.map((toolCall, index) => ({
    key: `${toolTitle(toolCall)}-${index}`,
    title: toolTitle(toolCall),
    subtitle: toolSummary(toolCall),
    status: normalizeToolStatus(toolCall.status)
  }))
})

function normalizeToolStatus(status) {
  const value = String(status || '').toLowerCase()
  if (['pending', 'queued'].includes(value)) return 'pending'
  if (['running', 'executing', 'started'].includes(value)) return 'running'
  if (['error', 'failed', 'danger'].includes(value)) return 'error'
  return 'done'
}

function formatToolStatus(status) {
  const labels = {
    pending: '等待中',
    running: '执行中',
    done: '已完成',
    error: '失败'
  }
  return labels[status] || status || '已完成'
}

function toolTitle(toolCall) {
  return toolCall.name || toolCall.tool || toolCall.action || '系统动作'
}

function toolSummary(toolCall) {
  const result = toolCall.result || toolCall.output || {}
  if (typeof result === 'string' && result.trim()) return result.trim()
  if (result.summary) return result.summary
  if (result.message) return result.message
  if (toolCall.summary) return toolCall.summary
  if (toolCall.description) return toolCall.description
  if (normalizeToolStatus(toolCall.status) === 'running') return '正在读取现场数据与规则结果'
  if (normalizeToolStatus(toolCall.status) === 'pending') return '等待进入执行队列'
  return '工具结果已记录，可展开查看原始返回'
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
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-weight: 700;
}

.ai-message--user .ai-message__meta {
  text-align: right;
}

.ai-message__bubble {
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-lg);
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-sm);
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

.ai-message__tool-grid,
.ai-message__actions {
  display: grid;
  gap: 8px;
}

.ai-message__tool-row {
  min-width: 0;
  display: grid;
  grid-template-columns: 10px minmax(0, 1fr) auto;
  align-items: center;
  gap: 10px;
  padding: 10px;
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-lg);
  background: var(--xt-bg-panel-soft);
}

.ai-message__tool-row > div {
  min-width: 0;
  display: grid;
  gap: 3px;
}

.ai-message__tool-row strong,
.ai-message__tool-row small {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ai-message__tool-row strong {
  color: var(--xt-text);
  font-size: 13px;
  font-weight: 900;
}

.ai-message__tool-row small {
  color: var(--xt-text-secondary);
  font-size: 12px;
}

.ai-message__tool-row em {
  color: var(--xt-text-muted);
  font-size: 12px;
  font-style: normal;
  font-weight: 800;
}

.ai-message__tool-dot {
  width: 10px;
  height: 10px;
  border-radius: var(--xt-radius-pill);
  background: var(--xt-success);
}

.ai-message__tool-row.is-pending .ai-message__tool-dot {
  background: var(--xt-warning);
}

.ai-message__tool-row.is-running .ai-message__tool-dot {
  background: var(--xt-primary);
  animation: xt-execution-pulse 1.8s var(--xt-ease) infinite;
}

.ai-message__tool-row.is-error .ai-message__tool-dot {
  background: var(--xt-danger);
}

.ai-message__tool {
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-lg);
  background: var(--xt-bg-panel-soft);
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
  color: var(--xt-text-secondary);
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

@media (max-width: 620px) {
  .ai-message {
    max-width: 100%;
  }

  .ai-message__tool-row {
    grid-template-columns: 10px minmax(0, 1fr);
  }

  .ai-message__tool-row em {
    grid-column: 2;
  }
}
</style>
