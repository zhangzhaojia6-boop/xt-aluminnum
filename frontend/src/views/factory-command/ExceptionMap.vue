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
  border: 1px solid oklch(50% 0.16 28 / 0.35);
  border-radius: 10px;
  background:
    linear-gradient(180deg, oklch(60% 0.16 28 / 0.05) 0%, transparent 50%),
    oklch(18% 0.022 252);
  color: oklch(92% 0.01 252);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.04);
  transition: border-color 120ms cubic-bezier(0.16, 1, 0.3, 1), box-shadow 120ms cubic-bezier(0.16, 1, 0.3, 1);
}

@media (hover: hover) {
  .fc-exceptions article:hover {
    border-color: oklch(60% 0.16 28 / 0.55);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4), 0 0 0 1px oklch(60% 0.16 28 / 0.2);
  }
}

.fc-exceptions strong {
  color: oklch(92% 0.01 252);
  font-size: 14px;
  font-weight: 900;
}

.fc-exceptions span {
  color: oklch(58% 0.02 252);
  font-size: 12px;
  font-weight: 800;
}

.fc-exceptions button {
  align-self: end;
  min-height: 34px;
  padding: 0 12px;
  border: 0;
  border-radius: 6px;
  background: oklch(62% 0.18 255);
  color: #fff;
  font-weight: 850;
  cursor: pointer;
  box-shadow: 0 0 12px oklch(62% 0.18 255 / 0.25);
  transition: transform 120ms cubic-bezier(0.16, 1, 0.3, 1);
}

.fc-exceptions button:active {
  transform: scale(0.96);
}

@media (max-width: 1100px) {
  .fc-exceptions {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
