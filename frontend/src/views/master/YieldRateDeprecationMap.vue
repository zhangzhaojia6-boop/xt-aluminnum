<template>
  <div class="page-stack">
    <div class="page-header">
      <div>
        <h1>成品率口径收敛图</h1>
        <p>查看 Phase 2 下旧 `yield_rate` 到 `yield_matrix_lane` 的正式去留表，避免双真相继续扩散。</p>
      </div>
      <el-button @click="load">刷新</el-button>
    </div>

    <el-card class="panel" v-loading="loading">
      <el-descriptions :column="4" border>
        <el-descriptions-item label="正式真相源">{{ payload.formal_truth || '-' }}</el-descriptions-item>
        <el-descriptions-item label="版本">{{ payload.version ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="替换项">{{ payload.statuses?.replace ?? 0 }}</el-descriptions-item>
        <el-descriptions-item label="兼容保留项">{{ payload.statuses?.compat_only ?? 0 }}</el-descriptions-item>
      </el-descriptions>
      <div class="note">产品规则：正式管理口径统一收敛到 `yield_matrix_lane`，旧 `yield_rate` 只能做兼容明细或迁移残留。</div>
    </el-card>

    <el-card class="panel">
      <el-form inline>
        <el-form-item label="去留状态">
          <el-select v-model="filters.status" clearable style="width: 180px">
            <el-option label="全部" value="" />
            <el-option label="替换为矩阵口径" value="replace" />
            <el-option label="仅兼容保留" value="compat_only" />
            <el-option label="直接移除" value="remove" />
          </el-select>
        </el-form-item>
        <el-form-item label="类别">
          <el-select v-model="filters.category" clearable style="width: 180px">
            <el-option label="全部" value="" />
            <el-option label="页面展示" value="page_display" />
            <el-option label="服务规则" value="service_rule" />
            <el-option label="自动文案" value="automation_copy" />
            <el-option label="原始运行字段" value="raw_runtime" />
            <el-option label="模板/Schema 展示" value="schema_display" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="panel" v-loading="loading">
      <ReferenceDataTable :data="filteredItems" stripe>
        <el-table-column prop="surface_id" label="Surface ID" min-width="220" />
        <el-table-column prop="category" label="类别" min-width="140">
          <template #default="{ row }">{{ formatCategory(row.category) }}</template>
        </el-table-column>
        <el-table-column prop="location" label="位置" min-width="240" />
        <el-table-column prop="status" label="去留" min-width="140">
          <template #default="{ row }">
            <ReferenceStatusTag :status="statusTagType(row.status)" :label="formatMapStatus(row.status)" />
          </template>
        </el-table-column>
        <el-table-column prop="replacement" label="正式替代口径" min-width="260" />
        <el-table-column prop="notes" label="说明" min-width="320" />
      </ReferenceDataTable>
    </el-card>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'

import { fetchYieldRateDeprecationMap } from '../../api/master'
import ReferenceDataTable from '../../components/reference/ReferenceDataTable.vue'
import ReferenceStatusTag from '../../components/reference/ReferenceStatusTag.vue'

const loading = ref(false)
const payload = ref({
  version: null,
  formal_truth: '',
  statuses: {},
  items: []
})

const filters = reactive({
  status: '',
  category: ''
})

const filteredItems = computed(() =>
  (payload.value.items || []).filter((item) => {
    if (filters.status && item.status !== filters.status) return false
    if (filters.category && item.category !== filters.category) return false
    return true
  })
)

function formatMapStatus(value) {
  return (
    {
      replace: '替换为矩阵口径',
      compat_only: '仅兼容保留',
      remove: '直接移除'
    }[value] || value || '-'
  )
}

function statusTagType(value) {
  return (
    {
      replace: 'success',
      compat_only: 'warning',
      remove: 'danger'
    }[value] || 'normal'
  )
}

function formatCategory(value) {
  return (
    {
      page_display: '页面展示',
      service_rule: '服务规则',
      automation_copy: '自动文案',
      raw_runtime: '原始运行字段',
      schema_display: '模板/Schema 展示'
    }[value] || value || '-'
  )
}

async function load() {
  loading.value = true
  try {
    payload.value = await fetchYieldRateDeprecationMap()
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>
