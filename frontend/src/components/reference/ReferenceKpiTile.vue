<template>
  <article class="reference-kpi" :data-status="status">
    <span class="reference-kpi__icon">{{ icon }}</span>
    <div class="reference-kpi__content">
      <span class="reference-kpi__label">{{ label }}</span>
      <strong class="reference-kpi__value">
        {{ value }}
        <small v-if="unit">{{ unit }}</small>
      </strong>
      <em v-if="trend" class="reference-kpi__trend">{{ trend }}</em>
    </div>
  </article>
</template>

<script setup>
defineProps({
  icon: {
    type: String,
    default: '●'
  },
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
  status: {
    type: String,
    default: 'normal'
  }
})
</script>
