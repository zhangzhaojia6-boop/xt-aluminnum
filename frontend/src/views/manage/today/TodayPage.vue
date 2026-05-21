<template>
  <section class="xt-today" data-testid="manage-today">
    <header class="xt-today__header">
      <h1>今日</h1>
      <p class="xt-today__date">{{ today }}</p>
    </header>
    <OverviewCenter />
  </section>
</template>

<script setup>
import { computed } from 'vue'

import OverviewCenter from '../../review/OverviewCenter.vue'

const today = computed(() => {
  const now = new Date()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')

  return `${now.getFullYear()}-${month}-${day}`
})
</script>

<style scoped>
.xt-today {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.xt-today__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 22px;
}

.xt-today__header h1 {
  margin: 0;
  font-size: 22px;
}

.xt-today__date {
  margin: 0;
  color: var(--xt-text-secondary);
}
</style>
