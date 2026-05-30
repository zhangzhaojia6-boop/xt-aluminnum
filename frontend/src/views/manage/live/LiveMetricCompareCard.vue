<template>
  <section class="live-metric-compare" aria-label="算法与填报对照">
    <header class="live-section-head">
      <div>
        <span>口径对照</span>
        <strong>算法优先</strong>
      </div>
      <em>填报保留对照</em>
    </header>
    <div class="live-metric-compare__grid">
      <article v-for="item in items" :key="item.label" :class="`is-${item.tone}`">
        <span>{{ item.label }}</span>
        <strong data-xt-numeric>{{ item.primaryValue }}</strong>
        <div>
          <b>{{ item.primaryLabel }}</b>
          <em>{{ item.compareLabel }} {{ item.compareValue }}</em>
        </div>
      </article>
    </div>
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
