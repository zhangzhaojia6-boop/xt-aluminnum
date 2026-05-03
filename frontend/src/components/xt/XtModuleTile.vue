<template>
  <article class="xt-module-tile" :class="{ 'is-compact': compact }" data-interactive="true">
    <div class="xt-module-tile__top">
      <span class="xt-module-tile__status">{{ resolvedStatus }}</span>
    </div>

    <XtModuleGlyph
      class="xt-module-tile__glyph"
      :module-id="moduleId"
      :variant="moduleVariant"
      :status="status"
      :compact="compact"
    />

    <div class="xt-module-tile__body">
      <h3>{{ moduleTitle }}</h3>
      <p v-if="moduleSubtitle">{{ moduleSubtitle }}</p>
    </div>

    <div v-if="resolvedMetrics.length" class="xt-module-tile__metrics">
      <div v-for="metric in resolvedMetrics" :key="metric.label" class="xt-module-tile__metric">
        <span>{{ metric.label }}</span>
        <strong>{{ metric.value }}</strong>
      </div>
    </div>

    <button v-if="actionLabel" type="button" class="xt-module-tile__action" @click="$emit('action', module)">
      {{ actionLabel }}
    </button>
  </article>
</template>

<script setup>
import { computed } from 'vue'
import XtModuleGlyph from './XtModuleGlyph.vue'

defineOptions({ name: 'XtModuleTile' })

const props = defineProps({
  module: {
    type: Object,
    default: () => ({})
  },
  metrics: {
    type: Array,
    default: () => []
  },
  status: {
    type: String,
    default: 'normal'
  },
  statusText: {
    type: String,
    default: ''
  },
  actionLabel: {
    type: String,
    default: ''
  },
  compact: {
    type: Boolean,
    default: false
  }
})

defineEmits(['action'])

const moduleId = computed(() => props.module.id || props.module.key || props.module.variant || 'overview')
const moduleVariant = computed(() => props.module.variant || moduleId.value)
const moduleTitle = computed(() => props.module.shortTitle || props.module.title || props.module.label || '模块')
const moduleSubtitle = computed(() => props.module.subtitle || props.module.description || '')
const resolvedMetrics = computed(() => props.metrics.slice(0, 3))
const resolvedStatus = computed(() => props.module.statusText || props.statusText || statusText(props.status))

function statusText(value) {
  const map = {
    normal: '运行中',
    success: '正常',
    warning: '关注',
    danger: '异常',
    pending: '待处理'
  }
  return map[value] || '运行中'
}
</script>

<style scoped>
.xt-module-tile {
  position: relative;
  min-width: 0;
  display: grid;
  gap: var(--xt-space-3);
  padding: var(--xt-space-4);
  overflow: hidden;
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-xl);
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-sm);
  transition:
    border-color var(--xt-motion-fast) var(--xt-ease),
    box-shadow var(--xt-motion-fast) var(--xt-ease),
    transform var(--xt-motion-fast) var(--xt-ease);
}

.xt-module-tile::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  box-shadow: var(--xt-shadow-inset-hairline);
}

@media (hover: hover) {
  .xt-module-tile:hover {
    border-color: var(--xt-border);
    box-shadow: var(--xt-shadow-md);
    transform: translateY(-1px);
  }
}

.xt-module-tile__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-2);
}

.xt-module-tile__status {
  min-height: 24px;
  display: inline-flex;
  align-items: center;
  padding: 0 var(--xt-space-2);
  border-radius: var(--xt-radius-pill);
  background: var(--xt-primary-light);
  color: var(--xt-primary);
  font-size: var(--xt-text-xs);
  font-weight: 850;
}

.xt-module-tile__glyph {
  margin-block: -6px;
}

.xt-module-tile__body {
  display: grid;
  gap: 4px;
}

.xt-module-tile__body h3 {
  margin: 0;
  color: var(--xt-text);
  font-family: var(--xt-font-display);
  font-size: var(--xt-text-lg);
  font-weight: 850;
  line-height: 1.25;
}

.xt-module-tile__body p {
  margin: 0;
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-sm);
  line-height: 1.45;
}

.xt-module-tile__metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: var(--xt-space-2);
}

.xt-module-tile__metric {
  min-width: 0;
  padding: var(--xt-space-2);
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-lg);
  background: var(--xt-bg-panel-soft);
}

.xt-module-tile__metric span {
  display: block;
  overflow: hidden;
  color: var(--xt-text-muted);
  font-size: var(--xt-text-xs);
  font-weight: 760;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.xt-module-tile__metric strong {
  display: block;
  margin-top: 2px;
  overflow: hidden;
  color: var(--xt-text);
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-lg);
  font-weight: 900;
  font-variant-numeric: tabular-nums;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.xt-module-tile__action {
  min-height: 38px;
  border: 0;
  border-radius: var(--xt-radius-md);
  background: var(--xt-bg-ink);
  color: var(--xt-text-inverse);
  font-size: var(--xt-text-sm);
  font-weight: 850;
  transition:
    background-color var(--xt-motion-fast) var(--xt-ease),
    transform var(--xt-motion-fast) var(--xt-ease);
}

.xt-module-tile__action:active {
  transform: scale(0.96);
}

@media (max-width: 520px) {
  .xt-module-tile__metrics {
    grid-template-columns: 1fr;
  }
}
</style>
