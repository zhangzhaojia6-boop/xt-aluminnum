import { computed, onMounted, ref } from 'vue'
import { buildAssistantFallback, fetchAssistantCapabilities } from '../api/assistant'

export function useAssistantIntegration() {
  const assistantOpen = ref(false)
  const assistantLoading = ref(false)
  const assistantSeedQuery = ref('')
  const assistantShortcutSeed = ref(null)
  const assistantCapabilities = ref(buildAssistantFallback())
  let assistantShortcutSequence = 0

  const assistantQuickActions = computed(() =>
    assistantCapabilities.value.quick_actions || buildAssistantFallback().quick_actions
  )

  function mergeAssistantCapabilities(payload = {}) {
    return {
      ...buildAssistantFallback(),
      ...payload,
      groups: payload.groups || buildAssistantFallback().groups
    }
  }

  function handleAssistantOpen() {
    assistantSeedQuery.value = ''
    assistantShortcutSeed.value = null
    assistantOpen.value = true
  }

  function handleAssistantShortcut(action) {
    const query = action?.query || action?.label || ''
    assistantShortcutSequence += 1
    assistantSeedQuery.value = query
    assistantShortcutSeed.value = {
      key: action?.key || `assistant-shortcut-${assistantShortcutSequence}`,
      mode: action?.mode || 'answer',
      query,
      token: `assistant-shortcut-${assistantShortcutSequence}`
    }
    assistantOpen.value = true
  }

  async function loadAssistant() {
    assistantLoading.value = true
    try {
      const payload = await fetchAssistantCapabilities()
      assistantCapabilities.value = mergeAssistantCapabilities(payload)
    } catch {
      assistantCapabilities.value = buildAssistantFallback()
    } finally {
      assistantLoading.value = false
    }
  }

  onMounted(() => {
    loadAssistant()
  })

  return {
    assistantOpen, assistantLoading,
    assistantSeedQuery, assistantShortcutSeed,
    assistantCapabilities, assistantQuickActions,
    handleAssistantOpen, handleAssistantShortcut,
    loadAssistant
  }
}
