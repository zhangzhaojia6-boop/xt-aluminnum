<template>
  <span class="reference-status" :data-status="status">{{ label || statusLabel }}</span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  status: {
    type: String,
    default: 'normal'
  },
  label: {
    type: String,
    default: ''
  }
})

const statusLabel = computed(() => {
  const map = {
    success: '正常',
    warning: '预警',
    danger: '异常',
    pending: '待处理',
    normal: '同步中'
  }
  return map[props.status] || props.status
})
</script>
