<template>
  <FactoryCommandShell title="工厂总览" active="overview" :freshness="freshness">
    <section class="fc-grid fc-grid--metrics">
      <article class="fc-metric is-primary">
        <span>在制吨数</span>
        <strong>{{ overview?.wip_tons ?? '--' }}</strong>
        <em>数据源 {{ sourceLabel(freshness.source) }}</em>
      </article>
      <article class="fc-metric">
        <span>今日产出</span>
        <strong>{{ overview?.today_output_tons ?? '--' }}</strong>
        <em>吨</em>
      </article>
      <article class="fc-metric">
        <span>库存</span>
        <strong>{{ overview?.stock_tons ?? '--' }}</strong>
        <em>成品吨数</em>
      </article>
      <article class="fc-metric" :class="{ 'is-danger': overview?.abnormal_count > 0 }">
        <span>风险项</span>
        <strong>{{ overview?.abnormal_count ?? 0 }}</strong>
        <em>最后同步 {{ freshness.last_synced_at || '--' }}</em>
      </article>
    </section>

    <section class="fc-panel">
      <div class="fc-panel__head">
        <strong>车间扫描</strong>
        <button type="button" @click="askAi({ type: 'factory', key: 'all' })">问 AI</button>
      </div>
      <div class="fc-table">
        <div class="fc-table__row is-head">
          <span>车间</span><span>卷数</span><span>吨数</span><span>停滞</span>
        </div>
        <div v-for="row in store.workshops" :key="row.workshop_name" class="fc-table__row">
          <span>{{ row.workshop_name }}</span>
          <span>{{ row.active_coil_count }}</span>
          <span>{{ row.active_tons }}</span>
          <span>{{ row.stalled_count }}</span>
        </div>
      </div>
    </section>
  </FactoryCommandShell>
</template>

<script setup>
import { computed, onMounted } from 'vue'

import { askFactoryCommandAi } from '../../api/factory-command'
import { useFactoryCommandStore } from '../../stores/factory-command'
import { sourceLabel } from '../../utils/factoryCommandFormatters'
import FactoryCommandShell from './FactoryCommandShell.vue'

const store = useFactoryCommandStore()
const overview = computed(() => store.overview || {})
const freshness = computed(() => overview.value.freshness || {})

async function askAi(scope) {
  await askFactoryCommandAi({ question: '当前工厂状态和优先风险是什么？', scope })
}

onMounted(async () => {
  await Promise.all([store.loadOverview(), store.loadWorkshops(), store.loadMachineLines()])
})
</script>

<style scoped>
.fc-grid {
  display: grid;
  gap: 12px;
}

.fc-grid--metrics {
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin-bottom: 12px;
}

.fc-metric,
.fc-panel {
  border: 1px solid rgba(43, 93, 178, 0.13);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 14px 34px rgba(25, 62, 118, 0.07);
}

.fc-metric {
  display: grid;
  gap: 8px;
  min-height: 112px;
  padding: 15px;
}

.fc-metric span,
.fc-metric em {
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-style: normal;
  font-weight: 800;
}

.fc-metric strong {
  color: var(--xt-text);
  font-family: var(--xt-font-number);
  font-size: 30px;
  font-variant-numeric: tabular-nums;
  font-weight: 900;
}

.fc-metric.is-primary {
  background: oklch(54% 0.19 255);
  color: #fff;
}

.fc-metric.is-primary span,
.fc-metric.is-primary strong,
.fc-metric.is-primary em {
  color: rgba(255, 255, 255, 0.92);
}

.fc-metric.is-danger {
  border-color: rgba(194, 65, 52, 0.24);
}

.fc-panel {
  padding: 14px;
}

.fc-panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.fc-panel__head button {
  min-height: 36px;
  border: 0;
  border-radius: 6px;
  background: var(--xt-primary);
  color: #fff;
  font-weight: 850;
  cursor: pointer;
}

.fc-table {
  display: grid;
  border: 1px solid rgba(43, 93, 178, 0.13);
  border-radius: 8px;
  overflow: hidden;
}

.fc-table__row {
  display: grid;
  grid-template-columns: minmax(160px, 1.4fr) repeat(3, minmax(90px, 1fr));
  gap: 12px;
  padding: 10px 12px;
  background: #fff;
  border-bottom: 1px solid rgba(43, 93, 178, 0.1);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

.fc-table__row.is-head {
  background: oklch(96% 0.025 254);
  color: var(--xt-text-secondary);
  font-weight: 900;
}

@media (max-width: 900px) {
  .fc-grid--metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 520px) {
  .fc-grid--metrics {
    grid-template-columns: 1fr;
  }
}
</style>
