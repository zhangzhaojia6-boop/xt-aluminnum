<template>
  <section class="live-data-state-panel" aria-label="数据状态">
    <span v-for="state in states" :key="state.label" :class="`is-${state.tone}`">
      <b>{{ state.label }}</b>
      <em>{{ state.value }}</em>
    </span>
  </section>
</template>

<script setup>
defineProps({
  states: {
    type: Array,
    default: () => [],
  },
})
</script>
