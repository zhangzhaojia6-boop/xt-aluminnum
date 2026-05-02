<template>
  <FactoryCommandShell title="库存去向" active="destinations" :freshness="freshness">
    <section class="fc-destinations">
      <article v-for="item in store.destinations" :key="item.kind">
        <span>{{ item.label || destinationGroupLabel(item.kind) }}</span>
        <strong>{{ item.tons }}</strong>
        <em>{{ item.coil_count }} 卷 · 成品库存 / 分配 / 交付</em>
      </article>
    </section>
  </FactoryCommandShell>
</template>

<script setup>
import { computed, onMounted } from 'vue'

import { useFactoryCommandStore } from '../../stores/factory-command'
import { destinationGroupLabel } from '../../utils/factoryCommandFormatters'
import FactoryCommandShell from './FactoryCommandShell.vue'

const store = useFactoryCommandStore()
const freshness = computed(() => store.overview?.freshness || {})

onMounted(async () => {
  await Promise.all([store.loadOverview(), store.loadDestinations()])
})
</script>

<style scoped>
.fc-destinations {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.fc-destinations article {
  min-height: 120px;
  padding: 14px;
  border: 1px solid rgba(43, 93, 178, 0.13);
  border-radius: 8px;
  background: #fff;
}

.fc-destinations span,
.fc-destinations em {
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-style: normal;
  font-weight: 850;
}

.fc-destinations strong {
  display: block;
  margin: 16px 0 10px;
  font-family: var(--xt-font-number);
  font-size: 30px;
  font-variant-numeric: tabular-nums;
  font-weight: 900;
}

@media (max-width: 900px) {
  .fc-destinations {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
