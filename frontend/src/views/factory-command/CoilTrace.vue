<template>
  <FactoryCommandShell title="卷级追踪" active="coils" :freshness="freshness">
    <section class="fc-coils">
      <input v-model="keyword" class="fc-coils__search" placeholder="搜索批号 / 随行卡 / 物料" />
      <div class="fc-coils__list">
        <button v-for="coil in filteredCoils" :key="coil.coil_key" type="button" @click="selectCoil(coil)">
          <strong>{{ coil.tracking_card_no }}</strong>
          <span>{{ coil.material_code || '--' }}</span>
          <span>{{ coil.current_process || '--' }} → {{ coil.next_process || '--' }}</span>
        </button>
      </div>
      <article class="fc-coils__flow">
        <strong>{{ activeFlow?.tracking_card_no || '选择卷查看流转' }}</strong>
        <span>前工序 {{ activeFlow?.previous_process || '--' }}</span>
        <span>当前工序 {{ activeFlow?.current_process || '--' }}</span>
        <span>下工序 {{ activeFlow?.next_process || '--' }}</span>
        <span>计划去向 {{ activeFlow?.destination?.label || '--' }}</span>
        <button v-if="activeFlow" type="button" @click="askAi(activeFlow)">问 AI</button>
      </article>
    </section>
  </FactoryCommandShell>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

import { useFactoryCommandStore } from '../../stores/factory-command'
import { openAiAssistant } from '../../utils/assistantLauncher'
import FactoryCommandShell from './FactoryCommandShell.vue'

const store = useFactoryCommandStore()
const keyword = ref('')
const activeKey = ref('')
const freshness = computed(() => store.overview?.freshness || {})
const activeFlow = computed(() => store.coilFlows[activeKey.value] || null)
const filteredCoils = computed(() => {
  const value = keyword.value.trim().toLowerCase()
  if (!value) return store.coils
  return store.coils.filter((coil) => `${coil.tracking_card_no} ${coil.batch_no} ${coil.material_code}`.toLowerCase().includes(value))
})

async function selectCoil(coil) {
  activeKey.value = coil.coil_key
  await store.loadCoilFlow(coil.coil_key)
}

function askAi(flow) {
  openAiAssistant({
    question: `${flow.tracking_card_no} 的证据和下一步动作是什么？`,
    scope: { type: 'coil', key: flow.coil_key },
    freshness: freshness.value
  })
}

onMounted(async () => {
  await Promise.all([store.loadOverview(), store.loadCoils()])
})
</script>

<style scoped>
.fc-coils {
  display: grid;
  grid-template-columns: minmax(260px, 0.8fr) minmax(0, 1.2fr);
  gap: 12px;
}

.fc-coils__search,
.fc-coils__flow,
.fc-coils__list button {
  border: 1px solid rgba(43, 93, 178, 0.13);
  border-radius: 8px;
  background: #fff;
}

.fc-coils__search {
  grid-column: 1 / -1;
  min-height: 40px;
  padding: 0 12px;
}

.fc-coils__list {
  display: grid;
  gap: 8px;
}

.fc-coils__list button {
  display: grid;
  gap: 4px;
  min-height: 70px;
  padding: 10px;
  text-align: left;
}

.fc-coils__flow {
  display: grid;
  align-content: start;
  gap: 10px;
  min-height: 260px;
  padding: 14px;
}

.fc-coils__flow button {
  width: max-content;
  min-height: 34px;
  border: 0;
  border-radius: 6px;
  background: var(--xt-primary);
  color: #fff;
  font-weight: 850;
}

@media (max-width: 820px) {
  .fc-coils {
    grid-template-columns: 1fr;
  }
}
</style>
