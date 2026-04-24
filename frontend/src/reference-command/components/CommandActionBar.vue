<template>
  <div class="cmd-action-bar">
    <button
      v-for="action in actions"
      :key="action.key || action.label"
      type="button"
      :class="{ 'is-primary': action.primary }"
      @click="$emit('action', action)"
    >
      {{ action.label }}
    </button>
  </div>
</template>

<script setup>
defineEmits(['action'])

defineProps({
  actions: {
    type: Array,
    default: () => []
  }
})
</script>
