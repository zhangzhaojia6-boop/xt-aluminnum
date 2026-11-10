<template>
  <div class="xt-empty">
    <svg class="xt-empty__mark" viewBox="0 0 64 40" aria-hidden="true">
      <circle cx="20" cy="20" r="15" />
      <circle cx="20" cy="20" r="10" />
      <circle cx="20" cy="20" r="4" />
      <path d="M20 35 H60" />
      <path class="xt-empty__strip" d="M35 20 L60 35" />
    </svg>
    <div class="xt-empty__text">{{ text }}</div>
    <div v-if="$slots.actions" class="xt-empty__actions">
      <slot name="actions" />
    </div>
  </div>
</template>

<script setup>
defineOptions({ name: 'XtEmpty' })

defineProps({
  text: {
    type: String,
    default: '暂无数据'
  }
})
</script>

<style scoped>
.xt-empty {
  display: grid;
  place-items: center;
  gap: var(--xt-space-3);
  min-height: 160px;
  padding: var(--xt-space-8);
  border-radius: 4px;
  background: var(--xt-bg-panel-soft);
  color: var(--xt-text-muted);
  text-align: center;
}

.xt-empty__mark {
  width: 64px;
  height: 40px;
  fill: none;
  stroke: var(--xt-primary);
  stroke-width: 1.25;
  stroke-linecap: round;
  opacity: 0.55;
}

.xt-empty__strip {
  stroke-dasharray: 3 3;
}

.xt-empty__text {
  font-size: var(--xt-text-sm);
  font-weight: 600;
}

.xt-empty__actions {
  display: flex;
  justify-content: center;
  gap: var(--xt-space-2);
}
</style>
