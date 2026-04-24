<template>
  <section class="reference-page" :data-module="moduleNumber">
    <header class="reference-page__head">
      <div class="reference-page__title-group">
        <span class="reference-page__number">{{ paddedNumber }}</span>
        <h1>{{ title }}</h1>
        <div v-if="tags.length" class="reference-page__tags">
          <span v-for="tag in tags" :key="tag">{{ tag }}</span>
        </div>
      </div>
      <div v-if="$slots.actions" class="reference-page__actions">
        <slot name="actions" />
      </div>
    </header>
    <div class="reference-page__body">
      <slot />
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  moduleNumber: {
    type: [Number, String],
    required: true
  },
  title: {
    type: String,
    required: true
  },
  tags: {
    type: Array,
    default: () => []
  }
})

const paddedNumber = computed(() => String(props.moduleNumber).padStart(2, '0'))
</script>
