<template>
  <aside class="ai-conversations">
    <div class="ai-conversations__header">
      <strong>对话</strong>
      <el-button type="primary" size="small" :disabled="disabled" @click="$emit('new')">新建</el-button>
    </div>

    <div v-if="loading" class="ai-conversations__state">加载中</div>
    <div v-else-if="!conversations.length" class="ai-conversations__state">暂无对话</div>
    <nav v-else class="ai-conversations__list">
      <div
        v-for="conversation in conversations"
        :key="conversation.id"
        class="ai-conversations__item"
        :class="{ 'is-active': conversation.id === currentId }"
        :aria-disabled="disabled"
        role="button"
        tabindex="0"
        @click="$emit('select', conversation.id)"
        @keydown.enter.prevent="$emit('select', conversation.id)"
        @keydown.space.prevent="$emit('select', conversation.id)"
      >
        <span class="ai-conversations__title">{{ conversation.title || '新对话' }}</span>
        <span class="ai-conversations__time">{{ formatTime(conversation.updated_at || conversation.created_at) }}</span>
        <el-button
          class="ai-conversations__delete"
          link
          type="danger"
          size="small"
          :disabled="disabled"
          @click.stop="$emit('delete', conversation.id)"
        >
          删除
        </el-button>
      </div>
    </nav>
  </aside>
</template>

<script setup>
import dayjs from 'dayjs'

defineProps({
  conversations: { type: Array, default: () => [] },
  currentId: { type: [String, Number], default: null },
  loading: { type: Boolean, default: false },
  disabled: { type: Boolean, default: false }
})

defineEmits(['new', 'select', 'delete'])

function formatTime(value) {
  if (!value) return ''
  const time = dayjs(value)
  return time.isValid() ? time.format('MM-DD HH:mm') : ''
}
</script>

<style scoped>
.ai-conversations {
  display: flex;
  flex-direction: column;
  width: 260px;
  min-width: 220px;
  border-right: 1px solid var(--app-border);
  background: rgba(255, 255, 255, 0.72);
}

.ai-conversations__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 16px;
  border-bottom: 1px solid var(--app-border);
}

.ai-conversations__list {
  display: grid;
  gap: 6px;
  overflow-y: auto;
  padding: 10px;
}

.ai-conversations__item {
  position: relative;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 4px 8px;
  width: 100%;
  border: 1px solid transparent;
  border-radius: 14px;
  background: transparent;
  color: var(--app-text);
  padding: 10px 12px;
  text-align: left;
  cursor: pointer;
}

.ai-conversations__item:hover,
.ai-conversations__item.is-active {
  border-color: rgba(0, 113, 227, 0.14);
  background: var(--app-accent-soft);
}

.ai-conversations__item[aria-disabled="true"] {
  cursor: not-allowed;
}

.ai-conversations__title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
  font-weight: 700;
}

.ai-conversations__time {
  color: var(--app-muted);
  font-size: 12px;
}

.ai-conversations__delete {
  grid-column: 2;
  justify-self: end;
  min-height: 20px;
  padding: 0;
  opacity: 0;
}

.ai-conversations__item:hover .ai-conversations__delete,
.ai-conversations__item.is-active .ai-conversations__delete {
  opacity: 1;
}

.ai-conversations__state {
  padding: 24px 16px;
  color: var(--app-muted);
  font-size: 14px;
  text-align: center;
}

@media (max-width: 900px) {
  .ai-conversations {
    width: 100%;
    max-height: 220px;
    border-right: 0;
    border-bottom: 1px solid var(--app-border);
  }
}
</style>
