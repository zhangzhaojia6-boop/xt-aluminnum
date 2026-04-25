<template>
  <button type="button" class="action-tile" :class="{ 'is-primary': primary }" @click="$emit('click')">
    <strong>{{ label }}</strong>
    <span v-if="meta">{{ meta }}</span>
  </button>
</template>

<script setup>
defineEmits(['click'])

defineProps({
  label: {
    type: String,
    required: true
  },
  meta: {
    type: String,
    default: ''
  },
  primary: {
    type: Boolean,
    default: false
  }
})
</script>
