<template>
  <section class="xt-production" data-testid="manage-production">
    <header class="xt-production__header">
      <h1>生产</h1>
    </header>
    <FactoryOverview embedded />
  </section>
</template>

<script setup>
import FactoryOverview from '../../factory-command/FactoryOverview.vue'
</script>

<style scoped>
.xt-production {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.xt-production__header h1 {
  margin: 0;
  font-size: 22px;
}
</style>
