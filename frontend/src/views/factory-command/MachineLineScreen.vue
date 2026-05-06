<template>
  <FactoryCommandShell title="车间机列" active="machine-lines" :freshness="freshness">
    <section class="fc-lines__summary">
      <article>
        <span>实时机列</span>
        <strong>{{ lineCards.length }}</strong>
      </article>
      <article>
        <span>实时流入</span>
        <strong>{{ formatTons(totalActiveTons) }}</strong>
      </article>
      <article :class="{ 'is-warning': unboundLineCount > 0 }">
        <span>未绑定机列</span>
        <strong>{{ unboundLineCount }}</strong>
      </article>
    </section>

    <section class="fc-lines">
      <article v-for="line in lineCards" :key="line.lineCode" :class="['fc-line', `is-${line.bindingTone}`]">
        <header class="fc-line__head">
          <div>
            <strong>{{ line.title }}</strong>
            <span>{{ line.meta }}</span>
          </div>
          <span class="fc-line__source">{{ line.source }}</span>
        </header>

        <div class="fc-line__bar" aria-hidden="true">
          <span :style="{ width: line.barWidth }" />
        </div>

        <div class="fc-line__metrics">
          <div>
            <span>卷数</span>
            <strong>{{ line.activeCoilCount }}</strong>
          </div>
          <div>
            <span>当前</span>
            <strong>{{ line.activeTons }}</strong>
          </div>
          <div>
            <span>完成</span>
            <strong>{{ line.finishedTons }}</strong>
          </div>
          <div>
            <span>停滞</span>
            <strong>{{ line.stalledCount }}</strong>
          </div>
        </div>

        <footer class="fc-line__foot">
          <span :class="['fc-line__binding', `is-${line.bindingTone}`]">{{ line.bindingLabel }}</span>
          <span>经营估算 {{ line.costLabel }}</span>
          <span>毛差估算 {{ line.marginLabel }}</span>
          <button type="button" @click="askAi(line.raw)">
            <el-icon><TrendCharts /></el-icon>
            <span>问 AI</span>
          </button>
        </footer>
      </article>
    </section>
  </FactoryCommandShell>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { TrendCharts } from '@element-plus/icons-vue'

import { useFactoryCommandStore } from '../../stores/factory-command'
import { openAiAssistant } from '../../utils/assistantLauncher'
import { formatLineDisplay, formatMissingDataLabel, sourceLabel } from '../../utils/factoryCommandFormatters'
import FactoryCommandShell from './FactoryCommandShell.vue'

const store = useFactoryCommandStore()
const freshness = computed(() => store.overview?.freshness || {})
const maxActiveTons = computed(() => Math.max(...store.machineLines.map((line) => numberValue(line.active_tons ?? line.activeTons)), 1))
const totalActiveTons = computed(() => lineCards.value.reduce((total, line) => total + line.rawActiveTons, 0))
const unboundLineCount = computed(() => lineCards.value.filter((line) => line.bindingTone === 'warning').length)
const lineCards = computed(() => store.machineLines.map((line) => {
  const display = formatLineDisplay(line)
  const activeTons = numberValue(line.active_tons ?? line.activeTons)
  const finishedTons = numberValue(line.finished_tons ?? line.finishedTons)
  const costEstimate = line.cost_estimate || line.costEstimate || {}
  const marginEstimate = line.margin_estimate || line.marginEstimate || {}
  const isUnbound = (line.machine_binding_status || line.machineBindingStatus) === 'unbound'
  return {
    raw: line,
    lineCode: line.line_code || line.lineCode || display.code,
    title: display.title,
    meta: display.meta,
    source: sourceLabel(line.freshness?.source || freshness.value.source),
    activeCoilCount: numberValue(line.active_coil_count ?? line.activeCoilCount),
    activeTons: formatTons(activeTons),
    rawActiveTons: activeTons,
    finishedTons: formatTons(finishedTons),
    stalledCount: numberValue(line.stalled_count ?? line.stalledCount),
    barWidth: `${Math.max((activeTons / maxActiveTons.value) * 100, activeTons > 0 ? 8 : 0)}%`,
    bindingLabel: isUnbound ? '未绑定机列' : '机列已绑定',
    bindingTone: isUnbound ? 'warning' : 'normal',
    costLabel: costEstimate.estimated_cost ?? formatMissingDataLabel(costEstimate.missing_data?.[0]),
    marginLabel: marginEstimate.estimated_gross_margin ?? formatMissingDataLabel(marginEstimate.missing_data?.[0])
  }
}))

function numberValue(value) {
  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : 0
}

function formatTons(value) {
  return `${Math.round(numberValue(value) * 100) / 100} 吨`
}

function askAi(line) {
  openAiAssistant({
    question: `${line.line_name || line.line_code} 的负荷和停滞风险是什么？`,
    scope: { type: 'machine', key: line.line_code },
    freshness: freshness.value
  })
}

onMounted(async () => {
  await Promise.all([store.loadOverview(), store.loadMachineLines()])
})
</script>

<style scoped>
.fc-lines__summary {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin-bottom: 10px;
}

.fc-lines__summary article {
  min-height: 92px;
  display: grid;
  align-content: center;
  gap: 8px;
  padding: 14px;
  border: 1px solid rgba(43, 93, 178, 0.13);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 14px 34px rgba(25, 62, 118, 0.07);
}

.fc-lines__summary article.is-warning {
  border-color: rgba(194, 116, 22, 0.28);
  background: oklch(97% 0.035 82);
}

.fc-lines__summary span {
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-weight: 850;
}

.fc-lines__summary strong {
  color: var(--xt-text);
  font-family: var(--xt-font-number);
  font-size: 30px;
  font-variant-numeric: tabular-nums;
  font-weight: 900;
}

.fc-lines {
  display: grid;
  gap: 8px;
}

.fc-line {
  display: grid;
  gap: 12px;
  padding: 14px;
  border: 1px solid rgba(43, 93, 178, 0.13);
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 14px 34px rgba(25, 62, 118, 0.06);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

.fc-line.is-warning {
  border-color: rgba(194, 116, 22, 0.28);
}

.fc-line__head,
.fc-line__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.fc-line__head strong {
  display: block;
  color: var(--xt-text);
  font-size: 16px;
  font-weight: 900;
}

.fc-line__head span,
.fc-line__foot span,
.fc-line__metrics span,
.fc-line__source {
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-weight: 820;
}

.fc-line__source,
.fc-line__binding {
  min-height: 28px;
  display: inline-flex;
  align-items: center;
  padding: 0 8px;
  border: 1px solid rgba(43, 93, 178, 0.13);
  border-radius: 6px;
  background: #fff;
  white-space: nowrap;
}

.fc-line__binding.is-warning {
  color: oklch(48% 0.11 70);
  border-color: rgba(194, 116, 22, 0.28);
  background: oklch(96% 0.04 82);
}

.fc-line__bar {
  height: 10px;
  overflow: hidden;
  border-radius: 999px;
  background: oklch(94% 0.025 252);
}

.fc-line__bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, oklch(54% 0.19 255), oklch(62% 0.13 158));
  transition: width 360ms var(--xt-ease);
}

.fc-line.is-warning .fc-line__bar span {
  background: linear-gradient(90deg, oklch(62% 0.12 75), oklch(61% 0.11 158));
}

.fc-line__metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
}

.fc-line__metrics div {
  display: grid;
  gap: 4px;
  min-width: 0;
  padding: 10px;
  border: 1px solid rgba(43, 93, 178, 0.1);
  border-radius: 6px;
  background: oklch(98% 0.01 250);
}

.fc-line__metrics strong {
  color: var(--xt-text);
  font-family: var(--xt-font-number);
  font-size: 20px;
  font-weight: 900;
}

.fc-line button {
  min-height: 34px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border: 0;
  border-radius: 6px;
  background: var(--xt-primary);
  color: #fff;
  font-weight: 850;
  cursor: pointer;
  transition: transform var(--xt-motion-fast) var(--xt-ease);
}

.fc-line button:active {
  transform: scale(0.96);
}

@media (max-width: 1080px) {
  .fc-lines__summary,
  .fc-line__metrics {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .fc-line__foot {
    align-items: flex-start;
    flex-direction: column;
  }
}

@media (max-width: 560px) {
  .fc-lines__summary,
  .fc-line__metrics {
    grid-template-columns: 1fr;
  }

  .fc-line__head {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
