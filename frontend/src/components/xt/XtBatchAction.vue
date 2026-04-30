<template>
  <div v-if="selectedCount > 0" class="xt-batch-action">
    <span class="xt-batch-action__count">已选择 {{ selectedCount }} 项</span>
    <div class="xt-batch-action__items">
      <button
        v-for="action in actions"
        :key="action.key"
        type="button"
        class="xt-batch-action__button"
        :class="`xt-batch-action__button--${action.tone || 'neutral'}`"
        @click="$emit('action', action.key)"
      >
        {{ action.label }}
      </button>
      <button type="button" class="xt-batch-action__button" @click="$emit('clear')">清空选择</button>
    </div>
  </div>
</template>

<script setup>
defineOptions({ name: 'XtBatchAction' })

defineProps({
  selectedCount: {
    type: Number,
    default: 0
  },
  actions: {
    type: Array,
    default: () => []
  }
})

defineEmits(['action', 'clear'])
</script>

<style scoped>
.xt-batch-action {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-3);
  padding: var(--xt-space-3) var(--xt-space-4);
  border: 1px solid var(--xt-primary-border);
  border-radius: var(--xt-radius-xl);
  color: var(--xt-primary);
  background: var(--xt-primary-light);
}

.xt-batch-action__count {
  font-size: var(--xt-text-sm);
  font-weight: 700;
}

.xt-batch-action__items {
  display: flex;
  flex-wrap: wrap;
  gap: var(--xt-space-2);
}

.xt-batch-action__button {
  height: 30px;
  padding: 0 var(--xt-space-3);
  border: 1px solid transparent;
  border-radius: var(--xt-radius-md);
  color: var(--xt-text);
  background: var(--xt-bg-panel);
}

.xt-batch-action__button--danger {
  color: var(--xt-danger);
}

.xt-batch-action__button--primary {
  color: var(--xt-primary);
}

@media (max-width: 768px) {
  .xt-batch-action {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
