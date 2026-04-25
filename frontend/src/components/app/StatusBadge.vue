<template>
  <span class="status-badge" :class="`is-${resolvedTone}`">{{ label }}</span>
</template>

<script setup>
import { computed } from 'vue'

import { resolveStatusTone } from '../../design/status'

const props = defineProps({
  label: {
    type: String,
    required: true
  },
  tone: {
    type: String,
    default: 'info'
  }
})

const resolvedTone = computed(() => resolveStatusTone(props.tone))
</script>
