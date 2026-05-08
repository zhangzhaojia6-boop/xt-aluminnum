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
:deep(*) {
  --xt-bg-panel: oklch(18% 0.022 252);
  --xt-bg-panel-soft: oklch(16% 0.018 252);
  --xt-bg-panel-muted: oklch(22% 0.025 252);
  --xt-border-light: oklch(28% 0.03 252);
  --xt-text: oklch(92% 0.01 252);
  --xt-text-secondary: oklch(58% 0.02 252);
  --xt-primary: oklch(62% 0.18 255);
  --xt-warning: oklch(68% 0.14 75);
  --xt-warning-bg: oklch(24% 0.06 75);
  --xt-shadow-sm: 0 4px 16px rgba(0, 0, 0, 0.3);
}

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
  border: 1px solid oklch(28% 0.03 252);
  border-radius: 10px;
  background: oklch(18% 0.022 252);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.fc-lines__summary article.is-warning {
  border-color: oklch(50% 0.14 75);
  background:
    linear-gradient(180deg, oklch(68% 0.14 75 / 0.06) 0%, transparent 60%),
    oklch(20% 0.032 75);
}

.fc-lines__summary span {
  color: oklch(58% 0.02 252);
  font-size: 12px;
  font-weight: 850;
}

.fc-lines__summary strong {
  color: oklch(92% 0.01 252);
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
  border: 1px solid oklch(28% 0.03 252);
  border-radius: 10px;
  background:
    linear-gradient(180deg, rgba(80, 160, 255, 0.02) 0%, transparent 50%),
    oklch(18% 0.022 252);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255, 255, 255, 0.04);
  color: oklch(92% 0.01 252);
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

.fc-line.is-warning {
  border-color: oklch(50% 0.14 75);
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
  color: oklch(92% 0.01 252);
  font-size: 16px;
  font-weight: 900;
}

.fc-line__head span,
.fc-line__foot span,
.fc-line__metrics span,
.fc-line__source {
  color: oklch(58% 0.02 252);
  font-size: 12px;
  font-weight: 820;
}

.fc-line__source,
.fc-line__binding {
  min-height: 28px;
  display: inline-flex;
  align-items: center;
  padding: 0 8px;
  border: 1px solid oklch(28% 0.03 252);
  border-radius: 6px;
  background: oklch(16% 0.018 252);
  white-space: nowrap;
}

.fc-line__binding.is-warning {
  color: oklch(72% 0.14 75);
  border-color: oklch(50% 0.14 75);
  background: oklch(22% 0.05 75);
}

.fc-line__bar {
  height: 10px;
  overflow: hidden;
  border-radius: 999px;
  background: oklch(22% 0.025 252);
  box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.3);
}

.fc-line__bar span {
  display: block;
  height: 100%;
  border-radius: inherit;
  background: linear-gradient(90deg, oklch(62% 0.18 255), oklch(62% 0.14 158));
  box-shadow: 0 0 8px oklch(62% 0.18 255 / 0.4);
  transition: width 360ms cubic-bezier(0.16, 1, 0.3, 1);
}

.fc-line.is-warning .fc-line__bar span {
  background: linear-gradient(90deg, oklch(68% 0.14 75), oklch(62% 0.14 158));
  box-shadow: 0 0 8px oklch(68% 0.14 75 / 0.4);
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
  border: 1px solid oklch(28% 0.03 252);
  border-radius: 6px;
  background: oklch(16% 0.018 252);
}

.fc-line__metrics strong {
  color: oklch(92% 0.01 252);
  font-family: var(--xt-font-number);
  font-size: 20px;
  font-weight: 900;
}

.fc-line button {
  min-height: 34px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
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
