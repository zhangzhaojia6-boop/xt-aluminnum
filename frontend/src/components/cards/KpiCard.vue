<template>
  <article class="kpi-card stat-card" :class="toneClass">
    <div class="stat-label">{{ label }}</div>
    <div class="stat-value">{{ value }}</div>
    <div v-if="hint" class="note">{{ hint }}</div>
  </article>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  label: {
    type: String,
    default: ''
  },
  value: {
    type: [String, Number],
    default: '--'
  },
  hint: {
    type: String,
    default: ''
  },
  tone: {
    type: String,
    default: 'neutral'
  }
})

const toneClass = computed(() => `is-${props.tone || 'neutral'}`)
</script>

<style scoped>
.kpi-card.is-success .stat-value {
  color: var(--xt-success);
}

.kpi-card.is-warning .stat-value {
  color: var(--xt-warning);
}

.kpi-card.is-danger .stat-value {
  color: var(--xt-danger);
}

.kpi-card.is-info .stat-value {
  color: var(--xt-info);
}
</style>
