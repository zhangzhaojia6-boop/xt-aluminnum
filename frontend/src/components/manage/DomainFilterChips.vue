<template>
  <div class="xt-domain-chips" role="group" aria-label="异常域过滤">
    <button
      type="button"
      class="xt-domain-chip"
      :class="{ 'is-active': isAllActive }"
      @click="clearDomains"
    >全部 {{ totalCount }}</button>
    <button
      v-for="d in DOMAIN_DEFS"
      :key="d.key"
      type="button"
      class="xt-domain-chip"
      :class="{ 'is-active': isActive(d.key) }"
      @click="toggle(d.key)"
    >{{ d.label }} {{ counts[d.key] || 0 }}</button>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

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
const emit = defineEmits(['update:modelValue', 'domain-change'])

const selectedDomains = ref([])
watch(() => props.modelValue, (value) => {
  selectedDomains.value = Array.isArray(value) ? [...value] : []
}, { immediate: true })

const isAllActive = computed(() => selectedDomains.value.length === 0)
const totalCount = computed(() => DOMAIN_DEFS.reduce((s, d) => s + (props.counts[d.key] || 0), 0))

function updateDomains(next) {
  selectedDomains.value = next
  emit('update:modelValue', next)
  emit('domain-change', next)
}

function isActive(key) { return selectedDomains.value.includes(key) }
function clearDomains() { updateDomains([]) }
function toggle(key) {
  const current = selectedDomains.value
  const next = isActive(key) ? current.filter((k) => k !== key) : [...current, key]
  updateDomains(next)
}
</script>

<style scoped>
.xt-domain-chips {
  position: relative;
  z-index: 1;
  display: flex;
  flex-wrap: nowrap;
  overflow-x: auto;
  gap: var(--xt-space-2);
}
.xt-domain-chip {
  position: relative;
  z-index: 1;
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
  color: var(--xt-text-inverse);
}
@media (hover: hover) {
  .xt-domain-chip:hover { background: var(--xt-bg-panel-soft); color: var(--xt-text); }
  .xt-domain-chip.is-active:hover { background: var(--xt-color-accent); color: var(--xt-text-inverse); }
}
</style>
