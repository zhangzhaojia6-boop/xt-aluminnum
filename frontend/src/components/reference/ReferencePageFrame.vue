<template>
  <section class="reference-page" :data-module="moduleNumber">
    <header class="reference-page__header">
      <div class="reference-page__title-group">
        <div class="reference-page__title-copy">
          <span class="reference-page__system">鑫泰数据中枢 · 运行中心</span>
          <h1>{{ title }}</h1>
        </div>
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
defineProps({
  moduleNumber: {
    type: [Number, String],
    default: null
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
</script>
