<template>
  <div class="xt-domain-chips" role="group" aria-label="异常域过滤">
    <button
      type="button"
      role="button"
      class="xt-domain-chip"
      :class="{ 'is-active': isAllActive }"
      @click="clearDomains"
    >全部 {{ totalCount }}</button>
    <button
      v-for="d in DOMAIN_DEFS"
      :key="d.key"
      type="button"
      role="button"
      class="xt-domain-chip"
      :class="{ 'is-active': isActive(d.key) }"
      @click="toggle(d.key)"
    >{{ d.label }} {{ counts[d.key] || 0 }}</button>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const DOMAIN_DEFS = [
  { key: 'production', label: '生产' },
  { key: 'quality', label: '质检' },
  { key: 'reconciliation', label: '对账' },
  { key: 'reporting', label: '填报' }
]

const props = defineProps({
  modelValue: { type: Array, default: () => [] },
  counts: { type: Object, default: () => ({}) }
})
const emit = defineEmits(['update:modelValue'])

const isAllActive = computed(() => props.modelValue.length === 0)
const totalCount = computed(() => DOMAIN_DEFS.reduce((s, d) => s + (props.counts[d.key] || 0), 0))

function isActive(key) { return props.modelValue.includes(key) }
function clearDomains() { emit('update:modelValue', []) }
function toggle(key) {
  const next = isActive(key) ? props.modelValue.filter((k) => k !== key) : [...props.modelValue, key]
  emit('update:modelValue', next)
}
</script>

<style scoped>
.xt-domain-chips {
  display: flex;
  flex-wrap: nowrap;
  overflow-x: auto;
  gap: var(--xt-space-2);
}
.xt-domain-chip {
  flex: 0 0 auto;
  height: 28px;
  padding: 0 var(--xt-space-3);
  border: 0;
  border-radius: var(--xt-radius-pill);
  background: var(--xt-bg-panel-soft);
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-xs);
  font-weight: 700;
  cursor: pointer;
  transition: background-color var(--xt-motion-fast) var(--xt-ease), color var(--xt-motion-fast) var(--xt-ease);
}
.xt-domain-chip.is-active {
  background: var(--xt-color-accent);
  color: var(--xt-text-on-accent, white);
}
@media (hover: hover) {
  .xt-domain-chip:hover { background: var(--xt-bg-panel-soft); color: var(--xt-text); }
  .xt-domain-chip.is-active:hover { background: var(--xt-color-accent); }
}
</style>
