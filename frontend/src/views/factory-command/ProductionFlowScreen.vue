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

import { useFactoryCommandStore } from '../../stores/factory-command'
import { openAiAssistant } from '../../utils/assistantLauncher'
import FactoryCommandShell from './FactoryCommandShell.vue'

const store = useFactoryCommandStore()
const freshness = computed(() => store.overview?.freshness || {})

function askAi(coil) {
  openAiAssistant({
    question: `这卷 ${coil.tracking_card_no} 的流转风险是什么？`,
    scope: { type: 'coil', key: coil.coil_key },
    freshness: freshness.value
  })
}

onMounted(async () => {
  await Promise.all([store.loadOverview(), store.loadCoils()])
})
</script>

<style scoped>
:deep(*) {
  --xt-bg-panel: oklch(18% 0.022 252);
  --xt-border-light: oklch(28% 0.03 252);
  --xt-text: oklch(92% 0.01 252);
  --xt-text-secondary: oklch(58% 0.02 252);
}

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
  border: 1px solid oklch(28% 0.03 252);
  border-radius: 8px;
  background:
    linear-gradient(180deg, rgba(80, 160, 255, 0.02) 0%, transparent 60%),
    oklch(18% 0.022 252);
  color: oklch(92% 0.01 252);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.04);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

.fc-flow__row strong {
  color: oklch(92% 0.01 252);
  font-weight: 900;
}

.fc-flow__row span {
  color: oklch(58% 0.02 252);
  font-size: 12px;
  font-weight: 820;
}

.fc-flow__row button {
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

.fc-flow__row button:active {
  transform: scale(0.96);
}

@media (max-width: 900px) {
  .fc-flow__row {
    grid-template-columns: 1fr;
  }
}
</style>
