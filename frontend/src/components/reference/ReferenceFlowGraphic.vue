<template>
  <div class="reference-flow">
    <div
      v-for="(node, index) in nodes"
      :key="node.key || node.title"
      class="reference-flow__node"
      :class="{ 'is-active': index <= activeIndex }"
      :data-status="node.status || 'normal'"
    >
      <span>{{ String(index + 1).padStart(2, '0') }}</span>
      <strong>{{ node.title }}</strong>
      <i />
    </div>
  </div>
</template>

<script setup>
defineProps({
  nodes: {
    type: Array,
    default: () => []
  },
  activeIndex: {
    type: Number,
    default: 0
  }
})
</script>
