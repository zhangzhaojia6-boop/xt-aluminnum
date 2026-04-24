<template>
  <section class="panel form-section">
    <header v-if="title" class="form-section__header">
      <h1>{{ title }}</h1>
      <p v-if="subtitle">{{ subtitle }}</p>
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
  subtitle: {
    type: String,
    default: ''
  }
})
</script>

<style scoped>
.form-section {
  display: grid;
  gap: 12px;
}

.form-section__header h1 {
  margin: 0;
  font-size: 20px;
}

.form-section__header p {
  margin: 6px 0 0;
  color: var(--app-muted);
}
</style>
