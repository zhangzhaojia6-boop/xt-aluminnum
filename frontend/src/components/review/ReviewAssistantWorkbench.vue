<template>
  <el-drawer
    v-model="drawerVisible"
    direction="rtl"
    size="min(620px, 100vw)"
    :with-header="false"
    class="review-assistant-drawer"
  >
    <div class="review-assistant-workbench" data-testid="review-assistant-workbench" v-loading="capabilityLoading || loading">
      <div class="review-assistant-workbench__hero">
        <div class="review-assistant-workbench__eyebrow">AI 审阅工作台</div>
        <h2>问答 · 取数 · 图卡 · 动作</h2>
        <p>已接生产上下文，可直接用于审阅与交付。</p>
      </div>

      <div class="review-assistant-workbench__composer">
        <span>指令</span>
        <el-input
          v-model="draftQuery"
          type="textarea"
          :rows="3"
          resize="none"
          placeholder="例如：今天产线异常原因"
        />
        <div class="review-assistant-workbench__composer-actions">
          <el-button plain :disabled="actionLoading" :loading="activeAction === 'retrieve'" @click="runAssistantQuery('retrieve')">取数</el-button>
          <el-button plain :disabled="actionLoading" :loading="activeAction === 'generate_image'" @click="runAssistantImage">图卡</el-button>
          <el-button
            type="primary"
            :disabled="actionLoading"
            :loading="activeAction === 'answer'"
            @click="runAssistantQuery('answer')"
          >
            问答
          </el-button>
        </div>
      </div>

      <div class="review-assistant-workbench__status">
        <div class="review-assistant-workbench__status-card">
          <span>连接状态</span>
          <strong>{{ capabilityLoading || loading ? '同步中' : capabilityState.connected ? '已联通' : '未联通' }}</strong>
        </div>
        <div class="review-assistant-workbench__status-card">
          <span>已接数据源</span>
          <strong>{{ capabilityState.integrations.length }} 个</strong>
        </div>
      </div>

      <div class="review-assistant-workbench__chips">
        <span v-for="item in integrationLabels" :key="item">{{ item }}</span>
      </div>

      <div class="review-assistant-workbench__result">
        <div class="review-assistant-workbench__result-head">
          <span>结果</span>
          <strong>{{ assistantResult.title || '暂无' }}</strong>
        </div>
        <p v-if="assistantResult.summary">{{ assistantResult.summary }}</p>
        <p v-else class="review-assistant-workbench__result-empty">暂无结果</p>

        <div v-if="assistantResult.cards.length" class="review-assistant-workbench__result-cards">
          <article
            v-for="card in assistantResult.cards"
            :key="card.title"
            class="review-assistant-workbench__result-card"
          >
            <strong>{{ card.title }}</strong>
            <p>{{ card.summary }}</p>
            <div v-if="card.source_labels.length" class="review-assistant-workbench__result-sources">
              <span v-for="label in card.source_labels" :key="label">{{ label }}</span>
            </div>
          </article>
        </div>

        <figure v-if="assistantResult.imageUrl" class="review-assistant-workbench__result-preview">
          <img :src="assistantResult.imageUrl" :alt="assistantResult.caption || 'AI 工作台生成图卡'" />
          <figcaption>{{ assistantResult.caption }}</figcaption>
        </figure>

        <div v-if="assistantResult.nextActions.length" class="review-assistant-workbench__result-next">
          <span v-for="item in assistantResult.nextActions" :key="item">{{ item }}</span>
        </div>
      </div>

      <div class="review-assistant-workbench__grid">
        <section
          v-for="group in capabilityGroups"
          :key="group.key"
          class="review-assistant-workbench__capability"
          :class="{ 'is-ready': group.ready }"
        >
          <div class="review-assistant-workbench__capability-top">
            <span class="review-assistant-workbench__capability-title">
              <span class="review-assistant-workbench__capability-icon review-icon-badge" :class="group.ready ? 'is-success' : 'is-primary'">
                <el-icon>
                  <component :is="group.icon" />
                </el-icon>
              </span>
              <h3>{{ group.label }}</h3>
            </span>
            <span>{{ group.ready ? '已接入' : '待接入' }}</span>
          </div>
        </section>
      </div>
    </div>
  </el-drawer>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { Connection, DataAnalysis, Promotion } from '@element-plus/icons-vue'

import {
  assistantCapabilityFallback,
  fetchAssistantCapabilities,
  generateAssistantImage,
  queryAssistant
} from '../../api/assistant'

const props = defineProps({
  modelValue: {
    type: Boolean,
    default: false
  },
  visible: {
    type: Boolean,
    default: undefined
  },
  seedQuery: {
    type: String,
    default: ''
  },
  shortcutSeed: {
    type: Object,
    default: null
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

const emit = defineEmits(['update:modelValue', 'update:visible'])

const drawerVisible = computed({
  get: () => (typeof props.visible === 'boolean' ? props.visible : props.modelValue),
  set: (value) => {
    emit('update:modelValue', value)
    emit('update:visible', value)
  }
})

const capabilityLoading = ref(false)
const hydrated = ref(false)
const draftQuery = ref(props.seedQuery)
const lastHandledShortcutToken = ref('')
const assistantActionDefaults = {
  answer: '今天先处理哪个阻塞项最有效？',
  search: '帮我查这卷现在到哪了？',
  retrieve: '当前交付链路还缺什么步骤？',
  automation: '现在适合触发哪条自动化？',
  generate_image: '生成今日产量和异常简报图。'
}
const assistantActionTitles = {
  answer: '分析结果',
  search: '搜索结果',
  retrieve: '执行建议',
  automation: '动作建议',
  generate_image: '图卡结果'
}
const actionLoading = ref(false)
const activeAction = ref('')
const assistantResult = ref({
  title: '',
  summary: '',
  cards: [],
  nextActions: [],
  imageUrl: '',
  caption: ''
})
const capabilityState = ref({
  ...assistantCapabilityFallback,
  ...props.capabilities
})

function normalizeCapabilityKeys(items = []) {
  return items.map((item) => (typeof item === 'string' ? item : item?.key)).filter(Boolean)
}

function capabilityIcon(key) {
  if (key === 'execution' || key === 'automation') return Promotion
  if (key === 'generate_image') return Connection
  return DataAnalysis
}

const capabilityGroups = computed(() => {
  const capabilities = new Set(normalizeCapabilityKeys(capabilityState.value.capabilities || []))
  const groups = Array.isArray(capabilityState.value.groups) ? capabilityState.value.groups : []
  if (groups.length) {
    return groups.map((group) => {
      const key = group?.key || ''
      const normalized = String(key).toLowerCase()
      let ready = false
      if (normalized === 'analysis' || normalized === 'execution') {
        ready = capabilities.has('query')
      } else if (normalized === 'generate_image') {
        ready = capabilities.has('generate_image')
      } else {
        ready = capabilities.size > 0
      }
      return {
        key: key || 'capability',
        label: group?.label || group?.kicker || '能力',
        ready,
        icon: capabilityIcon(normalized)
      }
    })
  }

  return [
    {
      key: 'analysis',
      label: '分析决策',
      ready: capabilities.has('query'),
      icon: capabilityIcon('analysis')
    },
    {
      key: 'execution',
      label: '执行交付',
      ready: capabilities.has('query'),
      icon: capabilityIcon('execution')
    },
    {
      key: 'generate_image',
      label: '图像输出',
      ready: capabilities.has('generate_image'),
      icon: capabilityIcon('generate_image')
    }
  ]
})

const integrationLabels = computed(() =>
  (capabilityState.value.integrations || [])
    .map((item) => (typeof item === 'string' ? item : item?.label))
    .filter(Boolean)
)

function buildDraftForAction(mode) {
  const nextQuery = draftQuery.value.trim() || assistantActionDefaults[mode] || ''
  draftQuery.value = nextQuery
  return nextQuery
}

async function runAssistantQuery(mode) {
  const query = buildDraftForAction(mode)
  activeAction.value = mode
  actionLoading.value = true
  try {
    const response = await queryAssistant({
      mode,
      query,
      surface: 'review_home'
    })
    assistantResult.value = {
      title: assistantActionTitles[mode],
      summary: response.summary,
      cards: response.cards || [],
      nextActions: response.next_actions || [],
      imageUrl: '',
      caption: ''
    }
  } catch {
    assistantResult.value = {
      title: assistantActionTitles[mode],
      summary: '请求失败，请稍后重试。',
      cards: [],
      nextActions: [],
      imageUrl: '',
      caption: ''
    }
  } finally {
    activeAction.value = ''
    actionLoading.value = false
  }
}

async function runAssistantImage() {
  const prompt = buildDraftForAction('generate_image')
  activeAction.value = 'generate_image'
  actionLoading.value = true
  try {
    const response = await generateAssistantImage({
      prompt,
      image_type: 'daily_briefing_card',
      surface: 'review_home'
    })
    assistantResult.value = {
      title: assistantActionTitles.generate_image,
      summary: response.suggested_caption,
      cards: [],
      nextActions: response.next_actions || [],
      imageUrl: response.image_url,
      caption: response.suggested_caption
    }
  } catch {
    assistantResult.value = {
      title: assistantActionTitles.generate_image,
      summary: '图卡生成失败，请稍后重试。',
      cards: [],
      nextActions: [],
      imageUrl: '',
      caption: ''
    }
  } finally {
    activeAction.value = ''
    actionLoading.value = false
  }
}

watch(
  () => props.capabilities,
  (value) => {
    capabilityState.value = {
      ...assistantCapabilityFallback,
      ...value,
      groups: value?.groups || assistantCapabilityFallback.groups
    }
  },
  { immediate: true, deep: true }
)

watch(
  () => props.seedQuery,
  (value) => {
    if (value) {
      draftQuery.value = value
    }
  },
  { immediate: true }
)

watch(
  [() => drawerVisible.value, () => props.shortcutSeed],
  async ([visible, shortcutSeed]) => {
    const token = shortcutSeed?.token
    if (!visible || !token || token === lastHandledShortcutToken.value) {
      return
    }

    lastHandledShortcutToken.value = token
    if (shortcutSeed.query) {
      draftQuery.value = shortcutSeed.query
    }

    if (shortcutSeed.mode === 'generate_image') {
      await runAssistantImage()
      return
    }

    await runAssistantQuery(shortcutSeed.mode || 'answer')
  },
  { deep: true }
)

watch(
  () => drawerVisible.value,
  async (visible) => {
    if (!visible) return
    if (props.seedQuery) {
      draftQuery.value = props.seedQuery
    }
    if (hydrated.value || props.capabilities?.capabilities?.length) return
    capabilityLoading.value = true
    try {
      capabilityState.value = await fetchAssistantCapabilities()
    } catch {
      capabilityState.value = assistantCapabilityFallback
    } finally {
      hydrated.value = true
      capabilityLoading.value = false
    }
  }
)
</script>

<style scoped>
.review-assistant-workbench,
.review-assistant-workbench__hero,
.review-assistant-workbench__composer,
.review-assistant-workbench__status,
.review-assistant-workbench__grid {
  display: grid;
  gap: 14px;
}

.review-assistant-workbench {
  padding: 8px 4px 4px;
}

.review-assistant-drawer :deep(.el-drawer__body) {
  padding: var(--xt-space-5);
  background: var(--xt-bg-panel);
}

.review-assistant-workbench__eyebrow,
.review-assistant-workbench__composer span,
.review-assistant-workbench__status-card span,
.review-assistant-workbench__capability-top span {
  font-size: 12px;
  letter-spacing: 0;
  color: var(--xt-text-secondary);
}

.review-assistant-workbench__hero h2,
.review-assistant-workbench__capability-top h3 {
  margin: 0;
  color: var(--xt-text);
}

.review-assistant-workbench__hero h2 {
  font-size: clamp(22px, 1.6vw, 26px);
  line-height: 1.16;
  letter-spacing: 0;
}

.review-assistant-workbench__hero p,
.review-assistant-workbench__result p {
  margin: 0;
  color: var(--xt-text-secondary);
  line-height: 1.6;
}

.review-assistant-workbench__composer,
.review-assistant-workbench__status-card,
.review-assistant-workbench__capability {
  padding: 16px;
  border-radius: var(--xt-radius-lg);
  border: 1px solid var(--xt-border-light);
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-sm);
  transition:
    transform var(--app-motion-fast) var(--app-motion-curve),
    border-color var(--app-motion-fast) ease,
    box-shadow var(--app-motion-fast) var(--app-motion-curve),
    background-color var(--app-motion-fast) ease;
}

.review-assistant-workbench__composer:hover,
.review-assistant-workbench__status-card:hover,
.review-assistant-workbench__capability:hover {
  transform: translateY(-2px);
  border-color: rgba(0, 113, 227, 0.22);
  box-shadow: var(--xt-shadow-md);
}

.review-assistant-workbench__composer-actions,
.review-assistant-workbench__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.review-assistant-workbench__result,
.review-assistant-workbench__result-card {
  display: grid;
  gap: 12px;
  padding: 16px;
  border-radius: var(--xt-radius-lg);
  border: 1px solid var(--xt-border-light);
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-sm);
  transition:
    transform var(--app-motion-fast) var(--app-motion-curve),
    border-color var(--app-motion-fast) ease,
    box-shadow var(--app-motion-fast) var(--app-motion-curve),
    background-color var(--app-motion-fast) ease;
}

.review-assistant-workbench__result-card:hover {
  transform: translateY(-2px);
  border-color: rgba(0, 113, 227, 0.22);
  box-shadow: var(--xt-shadow-md);
}

.review-assistant-workbench__result-head {
  display: grid;
  gap: 4px;
}

.review-assistant-workbench__result-head strong,
.review-assistant-workbench__result-card strong {
  color: var(--xt-text);
}

.review-assistant-workbench__result-empty,
.review-assistant-workbench__result-card p,
.review-assistant-workbench__result-preview figcaption {
  margin: 0;
  color: var(--xt-text-secondary);
  line-height: 1.7;
}

.review-assistant-workbench__result-cards {
  display: grid;
  gap: 12px;
}

.review-assistant-workbench__result-sources,
.review-assistant-workbench__result-next {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.review-assistant-workbench__result-sources span,
.review-assistant-workbench__result-next span {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 0 12px;
  border-radius: var(--xt-radius-md);
  background: var(--xt-primary-light);
  border: 1px solid rgba(0, 113, 227, 0.14);
  color: var(--xt-primary);
  font-size: 12px;
  font-weight: 700;
  transition:
    transform var(--app-motion-fast) var(--app-motion-curve),
    box-shadow var(--app-motion-fast) var(--app-motion-curve);
}

.review-assistant-workbench__result-sources span:hover,
.review-assistant-workbench__result-next span:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 12px rgba(15, 23, 42, 0.08);
}

.review-assistant-workbench__result-preview {
  display: grid;
  gap: 10px;
  margin: 0;
}

.review-assistant-workbench__result-preview img {
  width: 100%;
  border-radius: var(--xt-radius-lg);
  border: 1px solid var(--xt-border-light);
  background: var(--xt-bg-panel-soft);
}

.review-assistant-workbench__status {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.review-assistant-workbench__status-card strong {
  font-size: 22px;
  color: var(--xt-text);
}

.review-assistant-workbench__chips span {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 0 12px;
  border-radius: var(--xt-radius-md);
  background: var(--xt-primary-light);
  border: 1px solid rgba(0, 113, 227, 0.14);
  color: var(--xt-primary);
  font-size: 12px;
  font-weight: 700;
  transition:
    transform var(--app-motion-fast) var(--app-motion-curve),
    box-shadow var(--app-motion-fast) var(--app-motion-curve);
}

.review-assistant-workbench__chips span:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 12px rgba(15, 23, 42, 0.08);
}

.review-assistant-workbench__grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.review-assistant-workbench__capability {
  min-height: 96px;
  align-content: start;
}

.review-assistant-workbench__capability.is-ready {
  border-color: rgba(34, 197, 94, 0.20);
  background: var(--xt-success-light);
}

.review-assistant-workbench__capability-top {
  display: flex;
  align-items: start;
  justify-content: space-between;
  gap: 12px;
}

.review-assistant-workbench__capability-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.review-assistant-workbench__capability-icon {
  flex: 0 0 auto;
}

.review-assistant-workbench__capability-top h3 {
  font-size: 14px;
  line-height: 1.22;
}

@media (max-width: 720px) {
  .review-assistant-workbench__hero h2 {
    font-size: 22px;
  }

  .review-assistant-workbench__status,
  .review-assistant-workbench__grid {
    grid-template-columns: 1fr;
  }

  .review-assistant-workbench__composer-actions {
    display: grid;
  }
}
</style>
