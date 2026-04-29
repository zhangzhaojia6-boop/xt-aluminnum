<template>
  <div class="mobile-shell">
    <div class="mobile-top">
      <div>
        <h1>历史填报</h1>
        <p>只看你有权限的班次记录。</p>
      </div>
      <div class="header-actions">
        <el-button plain class="mobile-inline-action" @click="load">刷新</el-button>
      </div>
    </div>

    <div v-if="loading" class="mobile-inline-state panel">
      <p>正在加载历史记录…</p>
      <p>如果长时间不返回，请检查网络并重试。</p>
      <el-button
        type="primary"
        plain
        class="mobile-inline-action"
        :loading="loading"
        @click="load"
      >
        重试加载
      </el-button>
      <el-button class="mobile-inline-action" plain @click="goEntry">返回首页</el-button>
    </div>

    <div v-else-if="pageError" class="mobile-inline-state panel">
      <p>{{ pageError }}</p>
      <el-button
        type="primary"
        plain
        class="mobile-inline-action"
        @click="load"
      >
        重试加载
      </el-button>
      <el-button plain class="mobile-inline-action" @click="goEntry">返回首页</el-button>
    </div>

    <el-card v-else class="panel mobile-card">
      <template #header>最近记录</template>
      <div v-if="!items.length" class="mobile-placeholder">暂无历史填报记录。</div>
      <div v-else class="mobile-history-list">
        <div v-for="item in items" :key="item.id" class="mobile-history-item">
          <div class="mobile-history-main">
            <div>
              <div class="mobile-history-title">
                {{ item.business_date }} / {{ item.shift_name || item.shift_code || '-' }}
              </div>
              <div class="mobile-history-meta">
                {{ item.workshop_name || '-' }} · {{ item.team_name || '未分班组' }}
              </div>
            </div>
            <el-tag :type="statusTagType(item.report_status)" effect="light">
              {{ formatStatusLabel(item.report_status) }}
            </el-tag>
          </div>
          <div class="mobile-history-grid">
            <div><span>产量</span><strong>{{ formatNumber(item.output_weight) }}</strong></div>
            <div><span>日电耗</span><strong>{{ formatNumber(item.electricity_daily) }}</strong></div>
            <div><span>日气耗</span><strong>{{ formatNumber(item.gas_daily) }}</strong></div>
            <div><span>图片</span><strong>{{ item.photo_file_name || '未上传' }}</strong></div>
          </div>
          <div v-if="item.has_exception || item.exception_type" class="mobile-history-note">
            异常：{{ item.exception_type || '已标记异常' }}
          </div>
          <div v-if="item.returned_reason" class="mobile-history-note">退回原因：{{ item.returned_reason }}</div>
          <div class="mobile-history-actions">
            <span class="mobile-history-meta">最近保存：{{ item.last_saved_at || '-' }}</span>
            <el-button text type="primary" @click="openDetail(item)">继续查看</el-button>
          </div>
        </div>
      </div>
    </el-card>

  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { fetchMobileHistory } from '../../api/mobile'
import { formatNumber, formatStatusLabel } from '../../utils/display'
import { useAuthStore } from '../../stores/auth'
import { resolveTransitionRoleBucket } from '../../utils/mobileTransition'

const router = useRouter()
const auth = useAuthStore()
const items = ref([])
const loading = ref(true)
const pageError = ref('')

const advancedRoleBuckets = [
  'machine_operator',
  'weigher',
  'qc',
  'energy_stat',
  'maintenance_lead',
  'hydraulic_lead',
  'contracts',
  'inventory_keeper',
  'utility_manager'
]

const currentUserRoleBucket = resolveTransitionRoleBucket({
  role: auth.role,
  isMachineBound: Boolean(auth.isMachineBound)
})

function isAdvancedHistoryItem(item) {
  const roleBucket = item?.role_bucket || item?.report_role_bucket || currentUserRoleBucket
  return advancedRoleBuckets.includes(roleBucket)
}

function resolveDetailRouteName(item = {}) {
  return isAdvancedHistoryItem(item) ? 'mobile-report-form-advanced' : 'mobile-report-form'
}

function statusTagType(status) {
  if (status === 'submitted' || status === 'approved') return 'success'
  if (status === 'returned') return 'danger'
  if (status === 'draft') return 'warning'
  return 'info'
}

async function load() {
  loading.value = true
  pageError.value = ''
  try {
    const data = await fetchMobileHistory({ limit: 12 })
    items.value = data.items || []
  } catch (error) {
    pageError.value = requestErrorMessage(error, '加载历史记录失败，请重试。')
    items.value = []
  } finally {
    loading.value = false
  }
}

function requestErrorMessage(error, fallback = '操作失败') {
  const detail = error?.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || item).join('；')
  }
  if (detail && typeof detail === 'object') {
    return detail.message || detail.msg || fallback
  }
  if (typeof detail === 'string' && detail.trim()) {
    return detail.trim()
  }
  return error?.message || fallback
}

function openDetail(item) {
  router.push({
    name: resolveDetailRouteName(item),
    params: {
      businessDate: item.business_date,
      shiftId: item.shift_id
    }
  })
}

function goEntry() {
  router.push({ name: 'mobile-entry' })
}

onMounted(load)
</script>
