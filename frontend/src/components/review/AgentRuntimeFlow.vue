<template>
  <section class="agent-runtime-flow" :class="{ 'is-compact': compact }" data-testid="agent-runtime-flow">
    <div v-if="title" class="agent-runtime-flow__header">
      <h3>{{ title }}</h3>
    </div>

    <div class="agent-runtime-flow__columns">
      <article class="agent-runtime-flow__column">
        <div class="agent-runtime-flow__column-title">执行单元</div>
        <div class="agent-runtime-flow__items">
          <div
            v-for="lane in sourceLaneCards"
            :key="lane.key"
            class="agent-runtime-flow__item"
            :class="`is-${lane.status}`"
          >
            <span class="agent-runtime-flow__badge" :class="`is-${lane.status}`">
              <el-icon>
                <component :is="sourceIcon(lane.status)" />
              </el-icon>
            </span>
            <div class="agent-runtime-flow__item-main">
              <strong>{{ lane.label }}</strong>
              <span>{{ lane.detail }}</span>
            </div>
          </div>
        </div>
      </article>

      <article class="agent-runtime-flow__column">
        <div class="agent-runtime-flow__column-title">运行状态</div>
        <div class="agent-runtime-flow__steps">
          <div
            v-for="worker in processingBots"
            :key="worker.key"
            class="agent-runtime-flow__step"
            :class="`is-${worker.status}`"
          >
            <span class="agent-runtime-flow__badge agent-runtime-flow__badge--step" :class="`is-${worker.status}`">
              <el-icon>
                <component :is="stepIcon(worker.key, worker.status)" />
              </el-icon>
            </span>
            <div class="agent-runtime-flow__item-main">
              <strong>{{ worker.label }}</strong>
              <span>{{ worker.value }}</span>
            </div>
          </div>
        </div>
      </article>
    </div>

    <div class="agent-runtime-flow__risk-strip">
      <div
        v-for="risk in riskCards"
        :key="risk.label"
        class="agent-runtime-flow__risk"
        :class="{ 'is-alert': risk.alert }"
      >
        <span>
          <el-icon>
            <component :is="riskIcon(risk.alert)" />
          </el-icon>
          {{ risk.label }}
        </span>
        <strong>{{ risk.value }}</strong>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { Bell, CircleCheckFilled, Clock, Document, Promotion, WarningFilled } from '@element-plus/icons-vue'

const props = defineProps({
  title: {
    type: String,
    default: ''
  },
  trace: {
    type: Object,
    default: () => ({})
  },
  risks: {
    type: Object,
    default: () => ({})
  },
  compact: {
    type: Boolean,
    default: false
  }
})

function sourceIcon(status) {
  if (status === 'alert' || status === 'blocked' || status === 'warning') return WarningFilled
  if (status === 'idle') return Clock
  return CircleCheckFilled
}

function stepIcon(key, status) {
  if (status === 'alert' || status === 'blocked' || status === 'warning') return WarningFilled
  if (key === 'reminder') return Bell
  if (key === 'archive') return Document
  if (key === 'delivery') return Promotion
  return CircleCheckFilled
}

function riskIcon(alert) {
  return alert ? WarningFilled : CircleCheckFilled
}

function safeCount(value) {
  return Number(value) || 0
}

const sourceLaneCards = computed(() => {
  const lanes = props.trace?.source_lanes
  if (Array.isArray(lanes) && lanes.length) {
    return lanes.map((lane, index) => ({
      key: lane.key || lane.id || `lane-${index}`,
      label: lane.label || lane.source_label || lane.name || `来源 ${index + 1}`,
      detail:
        lane.detail ||
        lane.stage_label ||
        (Array.isArray(lane.result_targets) && lane.result_targets.length ? lane.result_targets.join(' / ') : '处理中'),
      status: lane.status || 'healthy'
    }))
  }
  const orchestration = props.trace?.orchestration || {}
  const reliabilityScore = Number(orchestration.reliability_score) || 0
  return [
    {
      key: 'algorithm_pipeline',
      label: '算法流水线',
      detail: `可靠度 ${reliabilityScore || '--'}`,
      status: reliabilityScore >= 80 ? 'healthy' : 'warning'
    }
  ]
})

const processingBots = computed(() => {
  const workerList = props.trace?.orchestration?.workers
  if (Array.isArray(workerList) && workerList.length) {
    return workerList.map((worker, index) => ({
      key: worker.key || `worker-${index}`,
      label: worker.label || `执行节点 ${index + 1}`,
      value: worker.value || '运行中',
      status: worker.status || 'healthy'
    }))
  }
  const frontline = props.trace?.frontline || {}
  const backline = props.trace?.backline || {}
  const delivery = props.trace?.delivery || {}
  return [
    {
      key: 'algorithm_pipeline',
      label: '算法流水线',
      value: `${safeCount(frontline.reminder_count)} 次提醒`,
      status: safeCount(frontline.unreported_count) > 0 || safeCount(frontline.late_count) > 0 ? 'alert' : 'healthy'
    },
    {
      key: 'analysis_agent',
      label: '分析决策助手',
      value: `${safeCount(backline.history_points)} 日留存`,
      status: backline.status === 'blocked' ? 'alert' : 'healthy'
    },
    {
      key: 'execution_agent',
      label: '执行交付助手',
      value: `${safeCount(delivery.reports_ready_count)} 份已就绪`,
      status: delivery.status === 'blocked' ? 'alert' : 'healthy'
    }
  ]
})

const riskCards = computed(() => {
  const orchestration = props.trace?.orchestration || {}
  const reliabilityScore = Number(orchestration.reliability_score) || 0
  const riskLevel = String(orchestration.risk_level || '').toLowerCase()
  const bottlenecks = Array.isArray(orchestration.bottlenecks) ? orchestration.bottlenecks : []
  const exceptionCount = safeCount(props.risks.mobile_exception_count) + safeCount(props.risks.production_exception_count)
  const deliveryRisk = safeCount(props.risks.pending_report_publish_count) + safeCount(props.risks.reconciliation_open_count)
  return [
    {
      label: '可靠度',
      value: reliabilityScore ? `${reliabilityScore}` : '--',
      alert: reliabilityScore > 0 && reliabilityScore < 80
    },
    {
      label: '风险级别',
      value: riskLevel === 'high' ? '高' : riskLevel === 'medium' ? '中' : riskLevel === 'low' ? '低' : '--',
      alert: riskLevel === 'high'
    },
    {
      label: '阻塞项',
      value: bottlenecks.length || safeCount(orchestration.blocking_count),
      alert: bottlenecks.length > 0 || safeCount(orchestration.blocking_count) > 0
    },
    {
      label: '异常数',
      value: exceptionCount + deliveryRisk,
      alert: exceptionCount + deliveryRisk > 0
    }
  ]
})
</script>

<style scoped>
.agent-runtime-flow,
.agent-runtime-flow__header,
.agent-runtime-flow__columns,
.agent-runtime-flow__column,
.agent-runtime-flow__items,
.agent-runtime-flow__steps,
.agent-runtime-flow__risk-strip {
  display: grid;
  gap: 10px;
}

.agent-runtime-flow {
  padding: 10px;
  border-radius: 12px;
  background: var(--xt-bg-panel-strong);
  border: 1px solid var(--xt-border-light);
}

.agent-runtime-flow__header {
  grid-template-columns: 1fr;
  align-items: center;
  min-height: 0;
}

.agent-runtime-flow__column-title,
.agent-runtime-flow__risk span {
  font-size: 12px;
  color: var(--app-muted);
}

.agent-runtime-flow__header h3 {
  margin: 0 0 2px;
  font-size: 22px;
  line-height: 1.15;
  color: var(--app-text);
}
.agent-runtime-flow__item-main strong,
.agent-runtime-flow__risk strong {
  color: var(--app-text);
}

.agent-runtime-flow__columns {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-items: start;
}

.agent-runtime-flow__column {
  padding: 10px;
  border-radius: 10px;
  border: 1px solid var(--xt-border-light);
  background: var(--xt-gray-50);
}

.agent-runtime-flow__item,
.agent-runtime-flow__step {
  display: flex;
  align-items: center;
  gap: 9px;
  min-height: 50px;
  padding: 9px 10px;
  border-radius: 10px;
  background: var(--xt-bg-panel-strong);
  border: 1px solid var(--xt-border-light);
  transition:
    border-color 0.18s ease,
    background-color 0.18s ease,
    transform 0.18s ease,
    box-shadow 0.18s ease;
}

.agent-runtime-flow__item:hover,
.agent-runtime-flow__step:hover {
  transform: translateY(-1px);
  border-color: var(--xt-info-border);
  box-shadow: 0 8px 18px rgba(15, 23, 42, 0.06);
}

.agent-runtime-flow__item.is-alert,
.agent-runtime-flow__step.is-alert,
.agent-runtime-flow__item.is-warning,
.agent-runtime-flow__step.is-warning,
.agent-runtime-flow__risk.is-alert {
  border-color: var(--xt-danger-border);
  background: rgba(254, 242, 242, 0.92);
}

.agent-runtime-flow__badge {
  width: 22px;
  height: 22px;
  flex: 0 0 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  background: rgba(219, 234, 254, 0.82);
  color: var(--xt-primary);
}

.agent-runtime-flow__badge.is-alert {
  background: rgba(254, 226, 226, 0.88);
  color: var(--xt-danger);
}

.agent-runtime-flow__badge.is-warning {
  background: rgba(254, 243, 199, 0.92);
  color: var(--xt-warning);
}

.agent-runtime-flow__badge.is-idle {
  background: rgba(241, 245, 249, 0.9);
  color: var(--xt-gray-600);
}

.agent-runtime-flow__badge--step {
  width: 24px;
  height: 24px;
  flex-basis: 24px;
}

.agent-runtime-flow__item-main {
  display: grid;
  gap: 2px;
}

.agent-runtime-flow__item-main strong {
  font-size: 13px;
  line-height: 1.2;
}

.agent-runtime-flow__item-main span {
  font-size: 12px;
  color: var(--app-muted);
  line-height: 1.45;
}

.agent-runtime-flow__risk-strip {
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.agent-runtime-flow__risk {
  padding: 9px 10px;
  border-radius: 10px;
  background: var(--xt-gray-50);
  border: 1px solid var(--xt-border-light);
  transition:
    border-color 0.18s ease,
    background-color 0.18s ease,
    transform 0.18s ease;
}

.agent-runtime-flow__risk:hover {
  transform: translateY(-1px);
  border-color: var(--xt-info-border);
}

.agent-runtime-flow__risk span {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.agent-runtime-flow__risk strong {
  display: block;
  margin-top: 3px;
  font-size: 18px;
}

.agent-runtime-flow.is-compact .agent-runtime-flow__header h3 {
  font-size: 20px;
}

@media (max-width: 900px) {
  .agent-runtime-flow__columns,
  .agent-runtime-flow__risk-strip {
    grid-template-columns: 1fr;
  }
}
</style>
