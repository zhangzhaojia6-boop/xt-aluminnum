<template>
  <article class="xt-ai-action-card" :class="`is-${resolvedStatus}`">
    <div class="xt-ai-action-card__icon">{{ icon }}</div>
    <div class="xt-ai-action-card__body">
      <strong>{{ title }}</strong>
      <span>{{ subtitle }}</span>
    </div>
    <button v-if="actionLabel" type="button" class="xt-ai-action-card__button" @click="$emit('action')">
      {{ actionLabel }}
    </button>
  </article>
</template>

<script setup>
import { computed } from 'vue'

defineOptions({ name: 'XtAiActionCard' })

const props = defineProps({
  title: {
    type: String,
    default: '系统动作'
  },
  subtitle: {
    type: String,
    default: '等待执行结果'
  },
  status: {
    type: String,
    default: 'done'
  },
  actionLabel: {
    type: String,
    default: ''
  }
})

defineEmits(['action'])

const resolvedStatus = computed(() => props.status || 'done')
const icon = computed(() => {
  const map = {
    pending: '待',
    running: '执',
    done: '成',
    error: '错'
  }
  return map[resolvedStatus.value] || '动'
})
</script>

<style scoped>
.xt-ai-action-card {
  display: grid;
  grid-template-columns: 34px minmax(0, 1fr) auto;
  align-items: center;
  gap: var(--xt-space-3);
  padding: var(--xt-space-3);
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-xl);
  background: var(--xt-bg-panel-soft);
}

.xt-ai-action-card__icon {
  width: 34px;
  height: 34px;
  display: grid;
  place-items: center;
  border-radius: var(--xt-radius-lg);
  background: var(--xt-primary-light);
  color: var(--xt-primary);
  font-weight: 900;
}

.xt-ai-action-card.is-running .xt-ai-action-card__icon {
  animation: xt-execution-pulse 1.8s var(--xt-ease) infinite;
}

.xt-ai-action-card.is-done .xt-ai-action-card__icon {
  background: var(--xt-success-light);
  color: var(--xt-success);
}

.xt-ai-action-card.is-error .xt-ai-action-card__icon {
  background: var(--xt-danger-light);
  color: var(--xt-danger);
}

.xt-ai-action-card__body {
  min-width: 0;
  display: grid;
  gap: 2px;
}

.xt-ai-action-card__body strong {
  overflow: hidden;
  color: var(--xt-text);
  font-size: var(--xt-text-sm);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.xt-ai-action-card__body span {
  overflow: hidden;
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-xs);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.xt-ai-action-card__button {
  min-height: 32px;
  padding: 0 var(--xt-space-3);
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-md);
  background: var(--xt-bg-panel);
  color: var(--xt-text);
  font-size: var(--xt-text-xs);
  font-weight: 800;
  transition:
    background-color var(--xt-motion-fast) var(--xt-ease),
    border-color var(--xt-motion-fast) var(--xt-ease),
    color var(--xt-motion-fast) var(--xt-ease),
    transform var(--xt-motion-fast) var(--xt-ease);
}

.xt-ai-action-card__button:active {
  transform: scale(0.96);
}

@media (max-width: 520px) {
  .xt-ai-action-card {
    grid-template-columns: 34px minmax(0, 1fr);
  }

  .xt-ai-action-card__button {
    grid-column: 1 / -1;
  }
}
</style>
