<template>
  <div class="cmd-flow">
    <div class="cmd-flow__nodes">
      <div
        v-for="(node, index) in resolvedNodes"
        :key="node.key || node.title"
        class="cmd-flow__node"
        :class="{ 'is-active': index <= activeIndex }"
      >
        <i />
        <strong>{{ node.title }}</strong>
        <span>{{ node.value }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  nodes: {
    type: Array,
    default: () => []
  },
  activeIndex: {
    type: Number,
    default: 3
  }
})

const resolvedNodes = computed(() => props.nodes.length ? props.nodes : [
  { title: '铸造区', value: '正常' },
  { title: '热轧区', value: '正常' },
  { title: '精整区', value: '关注' },
  { title: '检测区', value: '正常' },
  { title: '交付区', value: '同步' }
])
</script>
