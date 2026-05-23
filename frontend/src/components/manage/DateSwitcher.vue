<!-- frontend/src/components/manage/DateSwitcher.vue -->
<template>
  <div class="xt-date-switcher" data-testid="manage-date-switcher">
    <button type="button" class="xt-date-switcher__btn" :disabled="loading" @click="emit('step', -1)" aria-label="前一天">‹</button>
    <span class="xt-date-switcher__label">{{ formatted }}</span>
    <button type="button" class="xt-date-switcher__btn" :disabled="loading" @click="emit('step', 1)" aria-label="后一天">›</button>
    <button type="button" class="xt-date-switcher__refresh" :disabled="loading" @click="emit('refresh')">刷新</button>
    <span v-if="freshness" class="xt-date-switcher__dot" :class="`is-${freshness}`" :aria-label="`同步状态 ${freshness}`" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import dayjs from 'dayjs'

const props = defineProps({
  modelValue: { type: String, required: true },
  loading: { type: Boolean, default: false },
  freshness: { type: String, default: null }
})
const emit = defineEmits(['step', 'refresh'])
const formatted = computed(() => {
  const d = dayjs(props.modelValue)
  return `${d.month() + 1}月${d.date()}日 日报`
})
</script>

<style scoped>
.xt-date-switcher { display: flex; align-items: center; gap: var(--xt-space-2); }
.xt-date-switcher__btn,
.xt-date-switcher__refresh {
  min-height: 36px;
  padding: 0 var(--xt-space-3);
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-md);
  background: var(--xt-bg-panel);
  color: var(--xt-text);
  font-size: var(--xt-text-sm);
  cursor: pointer;
}
.xt-date-switcher__btn:disabled,
.xt-date-switcher__refresh:disabled { opacity: 0.5; cursor: not-allowed; }
.xt-date-switcher__label { font-size: var(--xt-text-md); font-weight: 800; color: var(--xt-text); }
.xt-date-switcher__dot { width: 8px; height: 8px; border-radius: 50%; }
.xt-date-switcher__dot.is-green { background: var(--xt-color-success); }
.xt-date-switcher__dot.is-yellow { background: var(--xt-color-warning); }
.xt-date-switcher__dot.is-red { background: var(--xt-color-danger); }
</style>
