<template>
  <span class="source-badge" :class="`is-${resolvedSource}`">{{ label }}</span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  source: {
    type: String,
    required: true
  }
})

const labels = {
  operator: '主操直录',
  owner: '专项补录',
  import: '导入',
  mes: 'MES',
  system: '系统汇总',
  exception: '异常处置'
}

const resolvedSource = computed(() => labels[props.source] ? props.source : 'system')
const label = computed(() => labels[resolvedSource.value])
</script>
