<template>
  <div class="xt-error-panel" role="alert">
    <div class="xt-error-panel__icon">!</div>
    <div class="xt-error-panel__body">
      <p class="xt-error-panel__message">{{ message }}</p>
      <button v-if="retryable" class="xt-error-panel__retry" @click="$emit('retry')">
        重试
      </button>
    </div>
  </div>
</template>

<script setup>
defineOptions({ name: 'XtErrorPanel' })

defineProps({
  message: {
    type: String,
    default: '加载失败，请稍后重试'
  },
  retryable: {
    type: Boolean,
    default: true
  }
})

defineEmits(['retry'])
</script>

<style scoped>
.xt-error-panel {
  display: flex;
  align-items: flex-start;
  gap: var(--xt-space-4);
  padding: var(--xt-space-6);
  border-radius: var(--xt-radius-lg);
  background: var(--xt-bg-danger-subtle, #fff5f5);
  border: 1px solid var(--xt-border-danger, #cf222e33);
}

.xt-error-panel__icon {
  display: grid;
  width: 32px;
  height: 32px;
  place-items: center;
  border-radius: var(--xt-radius-full);
  background: var(--xt-bg-danger, #cf222e);
  color: #fff;
  font-weight: 700;
  font-size: var(--xt-text-sm);
  flex-shrink: 0;
}

.xt-error-panel__body {
  display: flex;
  flex-direction: column;
  gap: var(--xt-space-3);
}

.xt-error-panel__message {
  margin: 0;
  font-size: var(--xt-text-sm);
  color: var(--xt-text-primary);
}

.xt-error-panel__retry {
  align-self: flex-start;
  padding: var(--xt-space-1) var(--xt-space-3);
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-md);
  background: var(--xt-bg-panel);
  color: var(--xt-text-primary);
  font-size: var(--xt-text-xs);
  cursor: pointer;
  transition: background 0.15s;
}

.xt-error-panel__retry:hover {
  background: var(--xt-bg-panel-hover);
}
</style>
