import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

export function useTableQuery({ fetchFn, defaultPageSize = 20 } = {}) {
  const route = useRoute()
  const router = useRouter()

  const page = ref(Number(route.query.page) || 1)
  const pageSize = ref(Number(route.query.page_size) || defaultPageSize)
  const sortField = ref(route.query.sort || '')
  const sortOrder = ref(route.query.order || '')
  const loading = ref(false)
  const data = ref([])
  const total = ref(0)

  const params = computed(() => ({
    page: page.value,
    page_size: pageSize.value,
    sort: sortField.value || undefined,
    order: sortOrder.value || undefined
  }))

  function syncQuery() {
    router.replace({
      query: {
        ...route.query,
        page: page.value > 1 ? page.value : undefined,
        page_size: pageSize.value !== defaultPageSize ? pageSize.value : undefined,
        sort: sortField.value || undefined,
        order: sortOrder.value || undefined
      }
    })
  }

  async function load(extraParams = {}) {
    if (!fetchFn) return
    loading.value = true
    try {
      const res = await fetchFn({ ...params.value, ...extraParams })
      data.value = res.items || res.data || res
      total.value = res.total ?? data.value.length
    } finally {
      loading.value = false
    }
  }

  function onPageChange(p) {
    page.value = p
    syncQuery()
    load()
  }

  function onSortChange({ prop, order }) {
    sortField.value = prop || ''
    sortOrder.value = order === 'ascending' ? 'asc' : order === 'descending' ? 'desc' : ''
    page.value = 1
    syncQuery()
    load()
  }

  watch([page, pageSize], syncQuery)

  return {
    page, pageSize, sortField, sortOrder,
    loading, data, total, params,
    load, onPageChange, onSortChange
  }
}
