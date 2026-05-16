import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ref } from 'vue'
import dayjs from 'dayjs'

export function useDateRange(defaultRange = null) {
  const route = useRoute()
  const router = useRouter()

  const fallback = defaultRange || [
    dayjs().startOf('month').format('YYYY-MM-DD'),
    dayjs().format('YYYY-MM-DD')
  ]

  const dateRange = ref([
    route.query.date_from || fallback[0],
    route.query.date_to || fallback[1]
  ])

  const dateFrom = computed(() => dateRange.value[0])
  const dateTo = computed(() => dateRange.value[1])

  watch(dateRange, (val) => {
    if (!val || val.length < 2) return
    router.replace({
      query: { ...route.query, date_from: val[0], date_to: val[1] }
    })
  })

  function setRange(from, to) {
    dateRange.value = [from, to]
  }

  function setPreset(preset) {
    const today = dayjs()
    const presets = {
      today: [today, today],
      yesterday: [today.subtract(1, 'day'), today.subtract(1, 'day')],
      week: [today.startOf('week'), today],
      month: [today.startOf('month'), today],
      quarter: [today.startOf('quarter'), today],
      year: [today.startOf('year'), today],
      last7: [today.subtract(6, 'day'), today],
      last30: [today.subtract(29, 'day'), today]
    }
    const p = presets[preset]
    if (p) dateRange.value = [p[0].format('YYYY-MM-DD'), p[1].format('YYYY-MM-DD')]
  }

  return { dateRange, dateFrom, dateTo, setRange, setPreset }
}
