<template>
  <FactoryCommandShell title="异常地图" active="exceptions" :freshness="freshness">
    <section class="fc-exceptions">
      <article v-for="rule in rules" :key="rule.key">
        <strong>{{ rule.label }}</strong>
        <span>{{ rule.key }}</span>
        <button type="button" @click="askAi(rule)">问 AI</button>
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
const rules = [
  { key: 'route_missing', label: '路线缺失' },
  { key: 'delay_hours_high', label: '停滞超时' },
  { key: 'sync_stale', label: '同步滞后' },
  { key: 'weight_anomaly', label: '重量异常' },
  { key: 'destination_unknown', label: '去向未知' }
]

async function askAi(rule) {
  await askFactoryCommandAi({ question: `${rule.label} 的证据和下一步是什么？`, scope: { type: 'rule', key: rule.key } })
}

onMounted(async () => {
  await Promise.all([store.loadOverview(), store.loadCoils()])
})
</script>

<style scoped>
.fc-exceptions {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 12px;
}

.fc-exceptions article {
  display: grid;
  gap: 8px;
  min-height: 126px;
  padding: 14px;
  border: 1px solid rgba(194, 65, 52, 0.18);
  border-radius: 8px;
  background: #fff;
}

.fc-exceptions span {
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-weight: 800;
}

.fc-exceptions button {
  align-self: end;
  min-height: 34px;
  border: 0;
  border-radius: 6px;
  background: var(--xt-primary);
  color: #fff;
  font-weight: 850;
}

@media (max-width: 1100px) {
  .fc-exceptions {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
