<template>
  <span class="cmd-status" :data-state="state">
    <i class="cmd-status__dot" />
    {{ label }}
  </span>
</template>

<script setup>
defineProps({
  label: {
    type: String,
    required: true
  },
  state: {
    type: String,
    default: 'normal'
  }
})
</script>
