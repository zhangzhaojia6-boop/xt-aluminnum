<template>
  <article class="cmd-kpi" :data-status="status">
    <span class="cmd-kpi__icon">{{ icon }}</span>
    <div>
      <span class="cmd-kpi__label">{{ label }}</span>
      <strong class="cmd-kpi__value">
        {{ value }}
        <small v-if="unit">{{ unit }}</small>
      </strong>
      <em v-if="trend" class="cmd-kpi__trend">{{ trend }}</em>
    </div>
  </article>
</template>

<script setup>
defineProps({
  icon: {
    type: String,
    default: '数'
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
