<template>
  <section class="xt-execution-rail" :class="{ 'xt-execution-rail--compact': compact }" aria-label="自动执行轨">
    <div
      v-for="(step, index) in resolvedSteps"
      :key="step.key || step.label"
      class="xt-execution-rail__step"
      :class="[
        `is-${step.status || statusForIndex(index)}`,
        { 'is-active': index === activeIndex }
      ]"
    >
      <span class="xt-execution-rail__index">{{ index + 1 }}</span>
      <div class="xt-execution-rail__copy">
        <strong>{{ step.label }}</strong>
        <small>{{ step.detail || defaultDetail(index) }}</small>
      </div>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'

defineOptions({ name: 'XtExecutionRail' })

const props = defineProps({
  steps: {
    type: Array,
    default: () => []
  },
  activeIndex: {
    type: Number,
    default: 2
  },
  compact: {
    type: Boolean,
    default: false
  }
})

const fallbackSteps = [
  { key: 'discover', label: '发现' },
  { key: 'judge', label: '判断' },
  { key: 'execute', label: '执行' },
  { key: 'audit', label: '留痕' },
  { key: 'publish', label: '发布' }
]

const details = ['采集现场信号', '核对规则阈值', '触发系统动作', '写入审计链路', '推送日报看板']
const resolvedSteps = computed(() => props.steps.length ? props.steps : fallbackSteps)

function statusForIndex(index) {
  if (index < props.activeIndex) return 'done'
  if (index === props.activeIndex) return 'running'
  return 'pending'
}

function defaultDetail(index) {
  return details[index] || '等待系统动作'
}
</script>

<style scoped>
.xt-execution-rail {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: var(--xt-space-2);
}

.xt-execution-rail--compact {
  grid-template-columns: repeat(auto-fit, minmax(108px, 1fr));
}

.xt-execution-rail__step {
  position: relative;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: var(--xt-space-2);
  padding: var(--xt-space-3);
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-xl);
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-xs);
}

.xt-execution-rail__step.is-running {
  border-color: var(--xt-primary-border);
  box-shadow: var(--xt-shadow-command);
}

.xt-execution-rail__step.is-running .xt-execution-rail__index {
  animation: xt-execution-pulse 1.8s var(--xt-ease) infinite;
}

.xt-execution-rail__step.is-done .xt-execution-rail__index {
  background: var(--xt-success-light);
  color: var(--xt-success);
}

.xt-execution-rail__step.is-warning .xt-execution-rail__index {
  background: var(--xt-warning-light);
  color: var(--xt-warning);
}

.xt-execution-rail__step.is-danger .xt-execution-rail__index {
  background: var(--xt-danger-light);
  color: var(--xt-danger);
}

.xt-execution-rail__index {
  width: 30px;
  height: 30px;
  flex: 0 0 30px;
  display: grid;
  place-items: center;
  border-radius: var(--xt-radius-lg);
  background: var(--xt-primary-soft);
  color: var(--xt-primary);
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-sm);
  font-weight: 900;
}

.xt-execution-rail__copy {
  min-width: 0;
  display: grid;
  gap: 2px;
}

.xt-execution-rail__copy strong {
  color: var(--xt-text);
  font-size: var(--xt-text-sm);
  line-height: 1.2;
}

.xt-execution-rail__copy small {
  overflow: hidden;
  color: var(--xt-text-muted);
  font-size: var(--xt-text-xs);
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}

@media (max-width: 900px) {
  .xt-execution-rail {
    grid-template-columns: 1fr;
  }
}
</style>
