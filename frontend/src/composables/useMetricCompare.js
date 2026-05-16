import { computed, ref } from 'vue'
import { api } from '../api/index'

export function useMetricCompare(module) {
  const mode = ref('yoy')
  const anchor = ref('')
  const loading = ref(false)
  const result = ref(null)

  const modeLabel = computed(() => {
    const labels = { yoy: '同比', mom: '环比', wow: '周比' }
    return labels[mode.value] || mode.value
  })

  async function load(params = {}) {
    loading.value = true
    try {
      const { data } = await api.get(`/${module}/comparison`, {
        params: { mode: mode.value, anchor: anchor.value || undefined, ...params }
      })
      result.value = data
    } finally {
      loading.value = false
    }
  }

  function setMode(m) {
    mode.value = m
    load()
  }

  return { mode, anchor, loading, result, modeLabel, load, setMode }
}
