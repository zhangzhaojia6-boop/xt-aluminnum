<template>
  <div class="xt-empty">
    <div class="xt-empty__mark">—</div>
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
  border-radius: var(--xt-radius-xl);
  background: var(--xt-bg-panel-soft);
  color: var(--xt-text-muted);
  text-align: center;
}

.xt-empty__mark {
  display: grid;
  width: 44px;
  height: 44px;
  place-items: center;
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-xl);
  background: var(--xt-bg-panel);
  color: var(--xt-text-muted);
  font-size: var(--xt-text-xl);
  box-shadow: var(--xt-shadow-xs);
}

.xt-empty__text {
  font-size: var(--xt-text-sm);
  font-weight: 700;
}

.xt-empty__actions {
  display: flex;
  justify-content: center;
  gap: var(--xt-space-2);
}
</style>
