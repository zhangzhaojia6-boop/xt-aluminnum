<template>
  <div class="xt-action-bar" :class="{ 'xt-action-bar--sticky': sticky }">
    <div class="xt-action-bar__main">
      <slot />
    </div>
    <div v-if="$slots.actions" class="xt-action-bar__actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup>
defineOptions({ name: 'XtActionBar' })

defineProps({
  sticky: {
    type: Boolean,
    default: false
  }
})
</script>

<style scoped>
.xt-action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-4);
  padding: var(--xt-space-3) var(--xt-space-4);
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-xl);
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-sm);
}

.xt-action-bar--sticky {
  position: sticky;
  bottom: var(--xt-space-4);
  z-index: 20;
  box-shadow: var(--xt-shadow-md);
}

.xt-action-bar__main,
.xt-action-bar__actions {
  display: flex;
  align-items: center;
  gap: var(--xt-space-2);
}

.xt-action-bar__main {
  min-width: 0;
}

.xt-action-bar__actions {
  flex: 0 0 auto;
}

@media (max-width: 768px) {
  .xt-action-bar {
    align-items: stretch;
    flex-direction: column;
  }
}
</style>
