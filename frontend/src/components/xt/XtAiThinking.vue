<template>
  <div v-if="visible" class="xt-ai-thinking" :class="{ 'is-error': lastError }" aria-live="polite">
    <div class="xt-ai-thinking__orb" aria-hidden="true">
      <span />
      <span />
      <span />
    </div>
    <div class="xt-ai-thinking__body">
      <strong>{{ title }}</strong>
      <div class="xt-ai-thinking__phases">
        <span
          v-for="(phase, index) in phases"
          :key="phase"
          class="xt-ai-thinking__phase"
          :class="{ 'is-active': activePhase === index }"
          :style="{ '--xt-thinking-delay': `${index * 90}ms` }"
        >
          {{ phase }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

defineOptions({ name: 'XtAiThinking' })

const props = defineProps({
  streaming: {
    type: Boolean,
    default: false
  },
  toolCalls: {
    type: Array,
    default: () => []
  },
  lastError: {
    type: String,
    default: ''
  }
})

const phases = ['读取现场', '核对规则', '推演影响', '生成动作']
const runningTools = computed(() => props.toolCalls.filter(item => ['pending', 'running'].includes(item?.status)))
const visible = computed(() => props.streaming || runningTools.value.length > 0 || Boolean(props.lastError))
const activePhase = computed(() => {
  if (props.lastError) return 1
  if (runningTools.value.length) return 2
  return props.streaming ? 3 : 0
})
const title = computed(() => {
  if (props.lastError) return props.lastError
  if (runningTools.value.length) return 'AI 正在调用工具'
  return 'AI 正在思考'
})
</script>

<style scoped>
.xt-ai-thinking {
  display: flex;
  align-items: center;
  gap: var(--xt-space-3);
  padding: var(--xt-space-3);
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-xl);
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-sm);
}

.xt-ai-thinking.is-error {
  border-color: rgba(194, 65, 52, 0.24);
  background: var(--xt-danger-light);
}

.xt-ai-thinking__orb {
  width: 42px;
  height: 42px;
  flex: 0 0 42px;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 3px;
  align-items: end;
  padding: 9px;
  border-radius: var(--xt-radius-xl);
  background: var(--xt-bg-ink);
}

.xt-ai-thinking__orb span {
  display: block;
  min-height: 10px;
  border-radius: var(--xt-radius-pill);
  background: var(--xt-primary);
  animation: xt-thinking-rise 1.35s var(--xt-ease) infinite;
}

.xt-ai-thinking__orb span:nth-child(2) {
  background: var(--xt-accent);
  animation-delay: 120ms;
}

.xt-ai-thinking__orb span:nth-child(3) {
  animation-delay: 240ms;
}

.xt-ai-thinking__body {
  min-width: 0;
  display: grid;
  gap: var(--xt-space-2);
}

.xt-ai-thinking__body strong {
  color: var(--xt-text);
  font-size: var(--xt-text-sm);
}

.xt-ai-thinking__phases {
  display: flex;
  flex-wrap: wrap;
  gap: var(--xt-space-1);
}

.xt-ai-thinking__phase {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 0 var(--xt-space-2);
  border-radius: var(--xt-radius-pill);
  background: var(--xt-bg-panel-soft);
  color: var(--xt-text-muted);
  font-size: var(--xt-text-xs);
  font-weight: 800;
  transition:
    background-color var(--xt-motion-fast) var(--xt-ease),
    color var(--xt-motion-fast) var(--xt-ease),
    transform var(--xt-motion-fast) var(--xt-ease);
}

.xt-ai-thinking__phase.is-active {
  background: var(--xt-primary-light);
  color: var(--xt-primary);
  transform: translateY(-1px);
}
</style>
