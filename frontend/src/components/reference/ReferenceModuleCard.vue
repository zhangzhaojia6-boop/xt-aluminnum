<template>
  <article class="reference-card" :class="sizeClass">
    <header v-if="$slots.header || title || $slots.actions" class="reference-card__head">
      <div class="reference-card__title">
        <slot name="header">
          <span v-if="moduleNumber" class="reference-card__number">{{ paddedNumber }}</span>
          <strong>{{ title }}</strong>
        </slot>
      </div>
      <div v-if="$slots.actions" class="reference-card__actions">
        <slot name="actions" />
      </div>
    </header>
    <div class="reference-card__body">
      <slot />
    </div>
  </article>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  moduleNumber: {
    type: [Number, String],
    default: ''
  },
  title: {
    type: String,
    default: ''
  },
  density: {
    type: String,
    default: 'normal'
  }
})

const paddedNumber = computed(() => String(props.moduleNumber).padStart(2, '0'))
const sizeClass = computed(() => `reference-card--${props.density}`)
</script>
