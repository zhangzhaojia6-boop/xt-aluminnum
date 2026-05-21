<template>
  <section class="xt-alerts" data-testid="manage-alerts">
    <header class="xt-alerts__header">
      <h1>异常</h1>
    </header>
    <AnomalyReview />
  </section>
</template>

<script setup>
import AnomalyReview from '../../attendance/AnomalyReview.vue'
</script>

<style scoped>
.xt-alerts {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.xt-alerts__header h1 {
  margin: 0;
  font-size: 22px;
}
</style>
