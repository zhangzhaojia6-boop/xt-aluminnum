import { api } from './index'

export function buildAssistantFallback() {
  return {
    connected: false,
    assistant_status: 'mock_ready',
    capabilities: [
      { key: 'query', label: '分析决策 / 执行交付', entrypoint: '/api/v1/assistant/query' },
      { key: 'generate_image', label: '图像生成', entrypoint: '/api/v1/assistant/generate-image' }
    ],
    integrations: [
      { key: 'dashboard', label: '审阅首页', status: 'mock_ready' },
      { key: 'runtime_trace', label: '流程追踪', status: 'mock_ready' },
      { key: 'delivery_status', label: '交付状态', status: 'mock_ready' }
    ],
    quick_actions: [
      { key: 'priority-blocker', label: '阻塞优先级', mode: 'answer', query: '今天先处理哪个阻塞项最有效？' },
      { key: 'delivery-readiness', label: '交付就绪检查', mode: 'retrieve', query: '当前交付链路还缺什么步骤？' },
      { key: 'daily-briefing-image', label: '生成日报图', mode: 'generate_image', query: '生成今日产量和异常简报图。' }
    ],
    summary_cards: [
      {
        key: 'capabilities',
        title: '能力域',
        value: '3',
        detail: '分析 / 执行 / 出图',
        tone: 'primary'
      },
      {
        key: 'integrations',
        title: '已接数据',
        value: '3',
        detail: '首页 / 流程 / 交付',
        tone: 'neutral'
      },
      {
        key: 'agents',
        title: '双助手',
        value: '在线',
        detail: '分析决策 + 执行交付',
        tone: 'success'
      }
    ],
    groups: [
      {
        key: 'analysis',
        kicker: '分析决策',
        label: '分析决策',
        description: '聚焦异常归因、阻塞优先级和风险解释。',
        examples: ['今天先处理哪个阻塞项', '哪里最影响交付']
      },
      {
        key: 'execution',
        kicker: '执行交付',
        label: '执行交付',
        description: '围绕交付链路给出可执行动作与闭环建议。',
        examples: ['现在能否发布日报', '交付缺口如何补齐']
      },
      {
        key: 'generate_image',
        kicker: '图像输出',
        label: '图像输出',
        description: '生成简报图卡用于日报与管理看板。',
        examples: ['生成日报图', '生成异常图卡']
      }
    ]
  }
}

export const assistantCapabilityFallback = buildAssistantFallback()

export async function fetchAssistantCapabilities() {
  try {
    const { data } = await api.get('/assistant/capabilities', { skipErrorToast: true })
    return {
      ...buildAssistantFallback(),
      ...data,
      groups: data?.groups || buildAssistantFallback().groups,
      quick_actions: data?.quick_actions || buildAssistantFallback().quick_actions,
      summary_cards: data?.summary_cards || buildAssistantFallback().summary_cards
    }
  } catch {
    return buildAssistantFallback()
  }
}

export async function queryAssistant(payload = {}) {
  const { data } = await api.post('/assistant/query', payload, { skipErrorToast: true })
  return data
}

export async function generateAssistantImage(payload = {}) {
  const { data } = await api.post('/assistant/generate-image', payload, { skipErrorToast: true })
  return data
}

export async function fetchAssistantLiveProbe() {
  try {
    const { data } = await api.get('/assistant/live-probe', { skipErrorToast: true })
    return data
  } catch {
    return null
  }
}
