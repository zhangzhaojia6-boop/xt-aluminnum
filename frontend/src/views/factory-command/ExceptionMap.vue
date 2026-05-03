<template>
  <FactoryCommandShell title="异常地图" active="exceptions" :freshness="freshness">
    <section class="fc-exceptions">
      <article v-for="rule in rules" :key="rule.key">
        <strong>{{ formatRuleLabel(rule.key) }}</strong>
        <span>{{ rule.focus }}</span>
        <button type="button" @click="askAi(rule)">问 AI</button>
      </article>
    </section>
  </FactoryCommandShell>
</template>

<script setup>
import { computed, onMounted } from 'vue'

import { useFactoryCommandStore } from '../../stores/factory-command'
import { openAiAssistant } from '../../utils/assistantLauncher'
import { formatRuleLabel } from '../../utils/factoryCommandFormatters'
import FactoryCommandShell from './FactoryCommandShell.vue'

const store = useFactoryCommandStore()
const freshness = computed(() => store.overview?.freshness || {})
const rules = [
  { key: 'route_missing', focus: '下道工序未匹配' },
  { key: 'delay_hours_high', focus: '卷停留超阈值' },
  { key: 'sync_stale', focus: '生产数据未更新' },
  { key: 'weight_anomaly', focus: '投入产出需复核' },
  { key: 'destination_unknown', focus: '入库/调拨/发货不清' }
]

function askAi(rule) {
  openAiAssistant({
    question: `${formatRuleLabel(rule.key)} 的证据和下一步是什么？`,
    scope: { type: 'rule', key: rule.key },
    freshness: freshness.value
  })
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
