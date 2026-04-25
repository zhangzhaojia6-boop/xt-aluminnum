<template>
  <section class="section-card">
    <header v-if="title || meta" class="section-card__head">
      <h2 v-if="title" class="section-card__title">{{ title }}</h2>
      <span v-if="meta" class="section-card__meta">{{ meta }}</span>
    </header>
    <slot />
  </section>
</template>

<script setup>
defineProps({
  title: {
    type: String,
    default: ''
  },
  meta: {
    type: String,
    default: ''
  }
})
</script>
