<template>
  <span class="xt-source-tag" :data-source="source">
    <svg class="xt-source-tag__icon" width="12" height="12" viewBox="0 0 12 12" fill="none">
      <circle cx="6" cy="6" r="2" fill="currentColor" />
      <circle cx="6" cy="6" r="5" stroke="currentColor" stroke-width="1" opacity="0.3" />
    </svg>
    <span class="xt-source-tag__text">{{ source }}</span>
    <span v-if="refreshedAt" class="xt-source-tag__time">{{ refreshedAt }}</span>
  </span>
</template>

<script setup>
defineOptions({ name: 'XtSourceTag' })

defineProps({
  source: {
    type: String,
    required: true
  },
  refreshedAt: {
    type: String,
    default: ''
  }
})
</script>

<style scoped>
.xt-source-tag {
  display: inline-flex;
  align-items: center;
  gap: var(--xt-space-1);
  padding: 2px var(--xt-space-2);
  border-radius: var(--xt-radius-sm);
  background: var(--xt-bg-subtle);
  color: var(--xt-text-muted);
  font-size: var(--xt-text-xs);
  font-weight: 600;
  line-height: 1;
  white-space: nowrap;
}

.xt-source-tag__icon {
  flex-shrink: 0;
}

.xt-source-tag__time {
  opacity: 0.7;
}

.xt-source-tag__time::before {
  content: '·';
  margin: 0 2px;
}
</style>
