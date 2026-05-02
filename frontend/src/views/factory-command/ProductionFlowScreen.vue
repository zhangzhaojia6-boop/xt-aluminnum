<template>
  <FactoryCommandShell title="生产流转" active="flow" :freshness="freshness">
    <section class="fc-flow">
      <article v-for="coil in store.coils" :key="coil.coil_key" class="fc-flow__row">
        <strong>{{ coil.tracking_card_no }}</strong>
        <span>前工序 {{ coil.previous_process || '待追溯' }}</span>
        <span>当前工序 {{ coil.current_process || '--' }}</span>
        <span>下工序 {{ coil.next_process || '--' }}</span>
        <span>{{ coil.destination?.label || '去向待定' }}</span>
        <button type="button" @click="askAi(coil)">问 AI</button>
      </article>
    </section>
  </FactoryCommandShell>
</template>

<script setup>
import { computed, onMounted } from 'vue'

import { askFactoryCommandAi } from '../../api/factory-command'
import { useFactoryCommandStore } from '../../stores/factory-command'
import FactoryCommandShell from './FactoryCommandShell.vue'

const store = useFactoryCommandStore()
const freshness = computed(() => store.overview?.freshness || {})

async function askAi(coil) {
  await askFactoryCommandAi({ question: `这卷 ${coil.tracking_card_no} 的流转风险是什么？`, scope: { type: 'coil', key: coil.coil_key } })
}

onMounted(async () => {
  await Promise.all([store.loadOverview(), store.loadCoils()])
})
</script>

<style scoped>
.fc-flow {
  display: grid;
  gap: 8px;
}

.fc-flow__row {
  display: grid;
  grid-template-columns: minmax(120px, 1.2fr) repeat(4, minmax(110px, 1fr)) auto;
  gap: 10px;
  align-items: center;
  padding: 12px;
  border: 1px solid rgba(43, 93, 178, 0.13);
  border-radius: 8px;
  background: #fff;
  font-size: 13px;
}

.fc-flow__row button {
  min-height: 34px;
  border: 0;
  border-radius: 6px;
  background: var(--xt-primary);
  color: #fff;
  font-weight: 850;
}

@media (max-width: 900px) {
  .fc-flow__row {
    grid-template-columns: 1fr;
  }
}
</style>
