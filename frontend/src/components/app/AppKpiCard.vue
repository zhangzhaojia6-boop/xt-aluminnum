<template>
  <article class="app-kpi-card kpi-card" :class="`is-${tone}`">
    <div class="kpi-card__label">{{ label }}</div>
    <div class="kpi-card__value">
      {{ value }}<span v-if="unit" class="kpi-card__unit">{{ unit }}</span>
    </div>
    <div v-if="trend" class="kpi-card__trend">{{ trend }}</div>
  </article>
</template>

<script setup>
defineProps({
  label: {
    type: String,
    required: true
  },
  value: {
    type: [String, Number],
    required: true
  },
  unit: {
    type: String,
    default: ''
  },
  trend: {
    type: String,
    default: ''
  },
  tone: {
    type: String,
    default: 'neutral'
  }
})
</script>
