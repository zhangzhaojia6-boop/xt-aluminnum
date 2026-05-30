<template>
  <section class="live-market-ticker" aria-label="实时行情">
    <article
      v-for="item in items"
      :key="item.label"
      class="live-market-ticker__item"
      :class="`is-${item.tone}`"
    >
      <span>{{ item.label }}</span>
      <strong data-xt-numeric>{{ item.value }}</strong>
      <em>{{ item.source }}</em>
    </article>
  </section>
</template>

<script setup>
defineProps({
  items: {
    type: Array,
    default: () => [],
  },
})
</script>
