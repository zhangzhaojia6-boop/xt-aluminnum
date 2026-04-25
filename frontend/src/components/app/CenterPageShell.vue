<template>
  <section class="center-page" :data-module="resolvedNo">
    <header class="center-page__head">
      <h1 class="center-page__title">
        <span class="center-page__no">{{ resolvedNo }}</span>
        <span>{{ title }}</span>
      </h1>
      <div class="center-page__tools">
        <slot name="tools" />
      </div>
    </header>
    <div v-if="$slots.summary" class="center-page__summary">
      <slot name="summary" />
    </div>
    <slot />
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  centerNo: {
    type: String,
    default: ''
  },
  no: {
    type: String,
    default: ''
  },
  title: {
    type: String,
    required: true
  }
})

const resolvedNo = computed(() => props.centerNo || props.no)
</script>
