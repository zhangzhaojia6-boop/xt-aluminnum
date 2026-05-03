<template>
  <FactoryCommandShell title="经营效益" active="cost" :freshness="freshness">
    <section class="fc-cost">
      <article>
        <span>经营估算</span>
        <strong>{{ cost?.estimated_cost ?? '--' }}</strong>
      </article>
      <article>
        <span>毛差估算</span>
        <strong>{{ cost?.estimated_gross_margin ?? '--' }}</strong>
      </article>
      <article>
        <span>待补口径</span>
        <strong>{{ missingDataText }}</strong>
      </article>
      <button type="button" @click="askAi">问 AI</button>
    </section>
  </FactoryCommandShell>
</template>

<script setup>
import { computed, onMounted } from 'vue'

import { useFactoryCommandStore } from '../../stores/factory-command'
import { openAiAssistant } from '../../utils/assistantLauncher'
import { formatMissingDataLabel } from '../../utils/factoryCommandFormatters'
import FactoryCommandShell from './FactoryCommandShell.vue'

const store = useFactoryCommandStore()
const cost = computed(() => store.costBenefit || {})
const freshness = computed(() => cost.value.freshness || store.overview?.freshness || {})
const missingDataText = computed(() => {
  const items = cost.value.missing_data || []
  if (!items.length) return '已配置'
  return items.map((item) => formatMissingDataLabel(item)).join('、')
})

function askAi() {
  openAiAssistant({
    question: '经营估算缺哪些输入？',
    scope: { type: 'metric', key: 'cost-benefit' },
    freshness: freshness.value
  })
}

onMounted(async () => {
  await Promise.all([store.loadOverview(), store.loadCostBenefit()])
})
</script>

<style scoped>
.fc-cost {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr)) auto;
  gap: 12px;
}

.fc-cost article,
.fc-cost button {
  min-height: 108px;
  padding: 14px;
  border: 1px solid rgba(43, 93, 178, 0.13);
  border-radius: 8px;
  background: #fff;
}

.fc-cost span {
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-weight: 850;
}

.fc-cost strong {
  display: block;
  margin-top: 16px;
  font-family: var(--xt-font-number);
  font-size: 28px;
  font-variant-numeric: tabular-nums;
  font-weight: 900;
}

.fc-cost button {
  background: var(--xt-primary);
  color: #fff;
  font-weight: 900;
}

@media (max-width: 820px) {
  .fc-cost {
    grid-template-columns: 1fr;
  }
}
</style>
