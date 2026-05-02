<template>
  <FactoryCommandShell title="车间机列" active="machine-lines" :freshness="freshness">
    <section class="fc-lines">
      <article v-for="line in store.machineLines" :key="line.line_code" class="fc-line">
        <div>
          <strong>{{ line.line_name || line.line_code }}</strong>
          <span>{{ line.workshop_name || '未识别车间' }}</span>
        </div>
        <span>当前 {{ line.active_tons ?? line.activeTons }} 吨</span>
        <span>完成 {{ line.finished_tons ?? line.finishedTons }} 吨</span>
        <span>停滞 {{ line.stalled_count ?? line.stalledCount }}</span>
        <span>经营估算 {{ line.cost_estimate?.estimated_cost ?? '--' }}</span>
        <span>毛差估算 {{ line.margin_estimate?.estimated_gross_margin ?? '--' }}</span>
        <button type="button" @click="askAi(line)">问 AI</button>
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

async function askAi(line) {
  await askFactoryCommandAi({ question: `${line.line_name || line.line_code} 的负荷和停滞风险是什么？`, scope: { type: 'machine', key: line.line_code } })
}

onMounted(async () => {
  await Promise.all([store.loadOverview(), store.loadMachineLines()])
})
</script>

<style scoped>
.fc-lines {
  display: grid;
  gap: 8px;
}

.fc-line {
  display: grid;
  grid-template-columns: minmax(160px, 1.3fr) repeat(5, minmax(110px, 1fr)) auto;
  gap: 10px;
  align-items: center;
  padding: 12px;
  border: 1px solid rgba(43, 93, 178, 0.13);
  border-radius: 8px;
  background: #fff;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

.fc-line strong,
.fc-line span {
  display: block;
}

.fc-line button {
  min-height: 34px;
  border: 0;
  border-radius: 6px;
  background: var(--xt-primary);
  color: #fff;
  font-weight: 850;
}

@media (max-width: 1080px) {
  .fc-line {
    grid-template-columns: 1fr 1fr;
  }
}
</style>
