<template>
  <section class="xt-factory-map" :class="{ 'xt-factory-map--compact': compact }" aria-label="全厂作战地图">
    <div class="xt-factory-map__canvas">
      <span class="xt-scan-line" aria-hidden="true" />
      <div class="xt-factory-map__rail xt-factory-map__rail--top" />
      <div class="xt-factory-map__rail xt-factory-map__rail--mid" />
      <div class="xt-factory-map__rail xt-factory-map__rail--bottom" />

      <button
        v-for="node in resolvedNodes"
        :key="node.key"
        type="button"
        class="xt-factory-map__node"
        :class="[`is-${node.status || 'normal'}`, { 'is-active': node.key === activeKey }]"
        :style="{ left: node.x, top: node.y }"
        :aria-label="node.label"
      >
        <span>{{ node.short || node.label?.slice(0, 1) || '点' }}</span>
        <strong>{{ node.label }}</strong>
      </button>
    </div>

    <div class="xt-factory-map__footer">
      <div v-for="line in resolvedLines" :key="line.key" class="xt-factory-map__line" :class="`is-${line.status || 'normal'}`">
        <span class="xt-industrial-dot" :class="line.status === 'warning' ? 'is-warning' : line.status === 'danger' ? 'is-danger' : ''" />
        <span>{{ line.label }}</span>
        <strong>{{ line.value }}</strong>
      </div>
    </div>

    <div v-if="resolvedAlerts.length" class="xt-factory-map__alerts">
      <div v-for="alert in resolvedAlerts" :key="alert.key" class="xt-factory-map__alert" :class="`is-${alert.status || 'warning'}`">
        <span>{{ alert.label }}</span>
        <strong>{{ alert.value }}</strong>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'

defineOptions({ name: 'XtFactoryMap' })

const props = defineProps({
  lines: {
    type: Array,
    default: () => []
  },
  nodes: {
    type: Array,
    default: () => []
  },
  alerts: {
    type: Array,
    default: () => []
  },
  activeKey: {
    type: String,
    default: ''
  },
  compact: {
    type: Boolean,
    default: false
  }
})

const fallbackNodes = [
  { key: 'furnace', label: '熔炉', short: '炉', status: 'normal', x: '12%', y: '22%' },
  { key: 'casting', label: '铸机', short: '铸', status: 'normal', x: '52%', y: '36%' },
  { key: 'ingot', label: '铝锭', short: '锭', status: 'warning', x: '24%', y: '68%' },
  { key: 'warehouse', label: '成品', short: '库', status: 'normal', x: '74%', y: '64%' }
]

const fallbackLines = [
  { key: 'zd', label: '铸锭线', value: '在线', status: 'normal' },
  { key: 'sync', label: '生产系统', value: '同步', status: 'normal' },
  { key: 'report', label: '日报', value: '待发布', status: 'warning' }
]

const resolvedNodes = computed(() => props.nodes.length ? props.nodes : fallbackNodes)
const resolvedLines = computed(() => props.lines.length ? props.lines : fallbackLines)
const resolvedAlerts = computed(() => props.alerts || [])
</script>

<style scoped>
.xt-factory-map {
  position: relative;
  min-height: 420px;
  display: grid;
  grid-template-rows: minmax(0, 1fr) auto;
  gap: var(--xt-space-3);
  padding: var(--xt-space-4);
  overflow: hidden;
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-2xl);
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-md);
}

.xt-factory-map--compact {
  min-height: 300px;
}

.xt-factory-map__canvas {
  position: relative;
  min-height: 270px;
  overflow: hidden;
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-xl);
  background:
    linear-gradient(90deg, rgba(15, 23, 42, 0.035) 1px, transparent 1px),
    linear-gradient(rgba(15, 23, 42, 0.028) 1px, transparent 1px),
    var(--xt-bg-panel-soft);
  background-size: 28px 28px;
}

.xt-factory-map__rail {
  position: absolute;
  right: 8%;
  left: 8%;
  height: 18px;
  border-radius: var(--xt-radius-pill);
  background: rgba(11, 99, 246, 0.10);
  box-shadow: inset 0 0 0 1px rgba(11, 99, 246, 0.08);
}

.xt-factory-map__rail--top {
  top: 26%;
  transform: rotate(-4deg);
}

.xt-factory-map__rail--mid {
  top: 50%;
  transform: rotate(2deg);
}

.xt-factory-map__rail--bottom {
  top: 72%;
  transform: rotate(-2deg);
}

.xt-factory-map__node {
  position: absolute;
  min-width: 68px;
  display: grid;
  gap: 4px;
  padding: 8px;
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-xl);
  background: var(--xt-bg-panel);
  color: var(--xt-text);
  box-shadow: var(--xt-shadow-sm);
  transform: translate(-50%, -50%);
  transition:
    border-color var(--xt-motion-fast) var(--xt-ease),
    box-shadow var(--xt-motion-fast) var(--xt-ease),
    transform var(--xt-motion-fast) var(--xt-ease);
}

.xt-factory-map__node:active {
  transform: translate(-50%, -50%) scale(0.96);
}

@media (hover: hover) {
  .xt-factory-map__node:hover {
    border-color: rgba(11, 99, 246, 0.24);
    box-shadow: var(--xt-shadow-md);
  }
}

.xt-factory-map__node span {
  width: 32px;
  height: 32px;
  display: grid;
  place-items: center;
  border-radius: var(--xt-radius-lg);
  background: var(--xt-primary-soft);
  color: var(--xt-primary);
  font-weight: 900;
}

.xt-factory-map__node strong {
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-xs);
  white-space: nowrap;
}

.xt-factory-map__node.is-warning span {
  background: var(--xt-warning-light);
  color: var(--xt-warning);
}

.xt-factory-map__node.is-danger span {
  background: var(--xt-danger-light);
  color: var(--xt-danger);
}

.xt-factory-map__node.is-active {
  border-color: rgba(11, 99, 246, 0.34);
  box-shadow: var(--xt-shadow-command);
}

.xt-factory-map__footer {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: var(--xt-space-2);
}

.xt-factory-map__line,
.xt-factory-map__alert {
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-2);
  padding: var(--xt-space-2) var(--xt-space-3);
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-lg);
  background: var(--xt-bg-panel-soft);
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-xs);
  font-weight: 800;
}

.xt-factory-map__line strong,
.xt-factory-map__alert strong {
  color: var(--xt-text);
  font-variant-numeric: tabular-nums;
}

.xt-factory-map__alerts {
  display: grid;
  gap: var(--xt-space-2);
}

.xt-factory-map__alert.is-danger {
  border-color: rgba(194, 65, 52, 0.18);
  background: var(--xt-danger-light);
}

.xt-factory-map__alert.is-warning {
  border-color: rgba(183, 121, 31, 0.18);
  background: var(--xt-warning-light);
}

@media (max-width: 760px) {
  .xt-factory-map {
    min-height: 320px;
    padding: var(--xt-space-3);
  }

  .xt-factory-map__canvas {
    min-height: 210px;
  }
}
</style>
