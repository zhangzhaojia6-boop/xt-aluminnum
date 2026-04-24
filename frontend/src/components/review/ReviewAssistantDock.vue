<template>
  <section class="review-assistant-dock panel" data-testid="review-assistant-dock">
    <div class="review-assistant-dock__copy">
      <strong>AI 助手</strong>
      <div class="review-assistant-dock__status-strip">
        <article
          v-for="card in summaryCards"
          :key="card.key"
          class="review-assistant-dock__status-card"
          :class="card.tone ? `is-${card.tone}` : ''"
        >
          <div class="review-assistant-dock__status-head">
            <span class="review-assistant-dock__status-icon review-icon-badge" :class="statusToneClass(card.tone)">
              <el-icon>
                <component :is="statusIcon(card.tone)" />
              </el-icon>
            </span>
            <span>{{ card.title }}</span>
          </div>
          <strong>{{ card.value }}</strong>
        </article>
      </div>
    </div>

    <div class="review-assistant-dock__actions">
      <button
        v-for="action in shortcutActions"
        :key="action.key"
        type="button"
        class="review-assistant-dock__shortcut"
        :class="shortcutToneClass(action)"
        @click="$emit('run', action)"
      >
        <span class="review-assistant-dock__shortcut-icon review-icon-badge" :class="shortcutIconToneClass(action)">
          <el-icon>
            <component :is="shortcutIcon(action)" />
          </el-icon>
        </span>
        <span>{{ action.label }}</span>
      </button>
      <el-button type="primary" :icon="ChatRound" class="review-assistant-dock__open" @click="$emit('open')">
        打开 AI 助手
      </el-button>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import {
  ChatDotRound,
  ChatRound,
  CircleCheckFilled,
  Connection,
  DataAnalysis,
  Promotion,
  Search,
  WarningFilled
} from '@element-plus/icons-vue'

const props = defineProps({
  quickActions: {
    type: Array,
    default: () => []
  },
  capabilities: {
    type: Object,
    default: () => ({})
  },
  loading: {
    type: Boolean,
    default: false
  }
})

defineEmits(['open', 'run'])

const shortcutIconMap = {
  answer: ChatDotRound,
  search: Search,
  retrieve: DataAnalysis,
  automation: Promotion,
  generate_image: Connection
}

function statusIcon(tone) {
  if (tone === 'success') return CircleCheckFilled
  if (tone === 'alert') return WarningFilled
  return DataAnalysis
}

function statusToneClass(tone) {
  if (tone === 'success') return 'is-success'
  if (tone === 'alert') return 'is-warn'
  if (tone === 'danger') return 'is-danger'
  if (tone === 'primary') return 'is-primary'
  return 'is-neutral'
}

function shortcutIcon(action) {
  const mode = action?.mode || action?.key
  return shortcutIconMap[mode] || ChatDotRound
}

function shortcutToneClass(action) {
  const mode = action?.mode || action?.key
  if (mode === 'automation') return 'is-success'
  if (mode === 'generate_image') return 'is-warn'
  return 'is-primary'
}

function shortcutIconToneClass(action) {
  const mode = action?.mode || action?.key
  if (mode === 'automation') return 'is-success'
  if (mode === 'generate_image') return 'is-warn'
  if (mode === 'search') return 'is-neutral'
  return 'is-primary'
}

const summaryCards = computed(() => {
  const cards = Array.isArray(props.capabilities?.summary_cards) ? props.capabilities.summary_cards : []
  if (cards.length) {
    return cards
  }

  const groups = Array.isArray(props.capabilities?.groups) ? props.capabilities.groups : []
  const integrations = Array.isArray(props.capabilities?.integrations) ? props.capabilities.integrations : []
  const capabilities = Array.isArray(props.capabilities?.capabilities) ? props.capabilities.capabilities : []
  const hasAutomation = capabilities.some((item) => (typeof item === 'string' ? item : item?.key) === 'automation')

  return [
    {
      key: 'capabilities',
      title: '能力域',
      value: String(groups.length || 3),
      detail: '分析 / 执行 / 出图',
      tone: 'primary'
    },
    {
      key: 'integrations',
      title: '已接数据',
      value: String(integrations.length || 0),
      detail: '首页 / 流程 / 交付',
      tone: 'neutral'
    },
    {
      key: 'agents',
      title: '双助手',
      value: hasAutomation ? '在线' : '在线',
      detail: '分析决策 + 执行交付',
      tone: 'success'
    }
  ]
})

const shortcutActions = computed(() => {
  if (props.quickActions.length) {
    return props.quickActions
  }

  const groups = Array.isArray(props.capabilities?.groups) ? props.capabilities.groups : []
  return groups.slice(0, 4).map((group) => ({
    key: group.key,
    label: group.examples?.[0] || group.label || group.kicker || '快捷动作'
  }))
})
</script>

<style scoped>
.review-assistant-dock {
  display: grid;
  grid-template-columns: minmax(0, 1.05fr) minmax(320px, 0.95fr);
  gap: 12px;
  padding: 14px;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: var(--app-shadow-xs);
}

.review-assistant-dock__copy,
.review-assistant-dock__actions {
  display: grid;
  gap: 10px;
}

.review-assistant-dock__copy strong {
  font-size: 17px;
  line-height: 1.25;
  color: var(--app-text);
}

.review-assistant-dock__status-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 8px;
}

.review-assistant-dock__status-card {
  display: grid;
  gap: 4px;
  min-height: 70px;
  padding: 9px 10px;
  border-radius: 12px;
  border: 1px solid rgba(148, 163, 184, 0.2);
  background: linear-gradient(180deg, rgba(248, 250, 252, 0.98), rgba(255, 255, 255, 0.96));
  box-shadow: var(--app-shadow-xs);
  transition:
    transform var(--app-motion-fast) var(--app-motion-curve),
    border-color var(--app-motion-fast) ease,
    box-shadow var(--app-motion-fast) var(--app-motion-curve),
    background-color var(--app-motion-fast) ease;
}

.review-assistant-dock__status-card:hover {
  transform: translateY(-2px);
  border-color: rgba(59, 130, 246, 0.24);
  box-shadow: var(--app-shadow-sm);
}

.review-assistant-dock__status-head {
  display: flex;
  align-items: center;
  gap: 6px;
}

.review-assistant-dock__status-icon {
  flex: 0 0 auto;
}

.review-assistant-dock__status-card:hover .review-assistant-dock__status-icon {
  transform: translateY(-1px);
  box-shadow: 0 8px 14px rgba(15, 23, 42, 0.1);
}

.review-assistant-dock__status-card.is-primary {
  border-color: rgba(37, 99, 235, 0.24);
  background: rgba(239, 246, 255, 0.9);
}

.review-assistant-dock__status-card.is-success {
  border-color: rgba(5, 150, 105, 0.24);
  background: rgba(236, 253, 245, 0.9);
}

.review-assistant-dock__status-card span {
  color: var(--app-muted);
}

.review-assistant-dock__status-card span {
  font-size: 12px;
}

.review-assistant-dock__status-card strong {
  font-size: 21px;
  line-height: 1.1;
  color: var(--app-text);
}

.review-assistant-dock__actions {
  grid-template-columns: repeat(2, minmax(0, 1fr));
  align-content: start;
  gap: 8px;
}

.review-assistant-dock__shortcut {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 44px;
  padding: 0 14px;
  border: 1px solid rgba(148, 163, 184, 0.18);
  border-radius: 12px;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.99), rgba(247, 250, 255, 0.96));
  color: var(--app-text);
  font-size: 13px;
  font-weight: 700;
  text-align: left;
  cursor: pointer;
  transition:
    transform var(--app-motion-fast) var(--app-motion-curve),
    border-color var(--app-motion-fast) ease,
    box-shadow var(--app-motion-fast) var(--app-motion-curve),
    background-color var(--app-motion-fast) ease;
}

.review-assistant-dock__shortcut:hover,
.review-assistant-dock__shortcut:focus-visible {
  transform: translateY(-2px);
  border-color: rgba(29, 78, 216, 0.24);
  background: rgba(239, 246, 255, 0.9);
  box-shadow: var(--app-shadow-xs);
  outline: none;
}

.review-assistant-dock__shortcut.is-success:hover,
.review-assistant-dock__shortcut.is-success:focus-visible {
  border-color: rgba(5, 150, 105, 0.24);
  background: rgba(236, 253, 245, 0.92);
}

.review-assistant-dock__shortcut.is-warn:hover,
.review-assistant-dock__shortcut.is-warn:focus-visible {
  border-color: rgba(217, 119, 6, 0.24);
  background: rgba(255, 247, 237, 0.92);
}

.review-assistant-dock__shortcut-icon {
  flex: 0 0 auto;
}

.review-assistant-dock__shortcut:hover .review-assistant-dock__shortcut-icon,
.review-assistant-dock__shortcut:focus-visible .review-assistant-dock__shortcut-icon {
  transform: translateY(-1px);
  box-shadow: 0 8px 14px rgba(15, 23, 42, 0.1);
}

.review-assistant-dock__open {
  grid-column: 1 / -1;
  min-height: 44px;
  border-radius: 12px;
}

@media (max-width: 1100px) {
  .review-assistant-dock {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .review-assistant-dock {
    padding: 18px;
  }

  .review-assistant-dock__status-strip,
  .review-assistant-dock__actions {
    grid-template-columns: 1fr;
  }

  .review-assistant-dock__status-card {
    min-height: auto;
  }
}
</style>
