<template>
  <div class="mock-data-notice" :class="`is-${resolvedSource}`">
    <strong>{{ label }}</strong>
    <span>{{ message }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  source: {
    type: String,
    default: 'fallback'
  },
  message: {
    type: String,
    default: '当前为演示或兜底数据，待接口接通后自动替换。'
  }
})

const sourceLabels = {
  mock: 'mock',
  fallback: 'fallback',
  live: 'live',
  mixed: 'mixed'
}

const resolvedSource = computed(() => sourceLabels[props.source] ? props.source : 'fallback')
const label = computed(() => sourceLabels[resolvedSource.value])
</script>
