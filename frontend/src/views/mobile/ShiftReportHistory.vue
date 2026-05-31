<template>
  <div class="mobile-shell">
    <div class="mobile-top">
      <div>
        <h1>历史填报</h1>
        <p>按整日查看有权限的录入记录。</p>
      </div>
      <div class="header-actions">
        <el-date-picker
          v-model="businessDate"
          type="date"
          value-format="YYYY-MM-DD"
          size="small"
          class="mobile-history-date"
          @change="load"
        />
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
        <div v-for="item in items" :key="historyItemKey(item)" class="mobile-history-item">
          <div class="mobile-history-main">
            <div>
              <div class="mobile-history-title">
                {{ item.business_date }} / {{ item.shift_name || item.shift_code || '-' }}
              </div>
              <div class="mobile-history-meta">
                {{ historyActorMeta(item) }}
              </div>
            </div>
            <div class="mobile-history-tags">
              <el-tag effect="light">{{ sourceTagLabel(item) }}</el-tag>
              <el-tag :type="statusTagType(item.report_status)" effect="light">
                {{ formatStatusLabel(item.report_status) }}
              </el-tag>
            </div>
          </div>
          <div v-if="isCoilHistoryItem(item)" class="mobile-history-grid">
            <div><span>随行卡</span><strong>{{ item.tracking_card_no || '-' }}</strong></div>
            <div><span>投料</span><strong>{{ formatNumber(item.input_weight) }}</strong></div>
            <div><span>下机</span><strong>{{ formatNumber(item.output_weight) }}</strong></div>
            <div><span>废料</span><strong>{{ formatNumber(item.scrap_weight) }}</strong></div>
          </div>
          <div v-else class="mobile-history-grid">
            <div><span>产量</span><strong>{{ formatNumber(item.output_weight) }}</strong></div>
            <div><span>日电耗</span><strong>{{ formatNumber(item.electricity_daily) }}</strong></div>
            <div><span>日气耗</span><strong>{{ formatNumber(item.gas_daily) }}</strong></div>
            <div><span>图片</span><strong>{{ item.photo_file_name || '未上传' }}</strong></div>
          </div>
          <div v-if="item.created_by_name" class="mobile-history-note">录入人：{{ item.created_by_name }}</div>
          <div v-if="item.has_exception || item.exception_type" class="mobile-history-note">
            异常：{{ item.exception_type || '已标记异常' }}
          </div>
          <div v-if="item.returned_reason" class="mobile-history-note">退回原因：{{ item.returned_reason }}</div>
          <div class="mobile-history-actions">
            <span class="mobile-history-meta">最近保存：{{ item.last_saved_at || '-' }}</span>
            <el-button text type="primary" @click="openDetail(item)">{{ actionLabel(item) }}</el-button>
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
import { inferBusinessDate } from '../../utils/shiftClock'

const router = useRouter()
const auth = useAuthStore()
const items = ref([])
const loading = ref(true)
const pageError = ref('')
const businessDate = ref(inferBusinessDate())

const advancedRoleBuckets = [
  'machine_operator',
  'energy_stat',
  'quality_owner',
  'planning_owner',
  'energy_chief',
  'storage_owner',
  'shipment_outflow_owner',
  'recovery_owner',
  'overhaul_owner'
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
  return isAdvancedHistoryItem(item) ? 'mobile-unified-entry' : 'mobile-report-form'
}

function statusTagType(status) {
  if (status === 'submitted' || status === 'approved') return 'success'
  if (status === 'returned') return 'danger'
  if (status === 'draft') return 'warning'
  return 'info'
}

function historyItemKey(item) {
  return `${item.source_type || 'shift_report'}-${item.id}`
}

function isCoilHistoryItem(item) {
  return item?.source_type === 'mobile_coil'
}

function sourceTagLabel(item) {
  if (isCoilHistoryItem(item)) return '主操逐卷'
  if (item?.source_type === 'owner_daily') return '专项每日'
  return '班次汇总'
}

function historyActorMeta(item) {
  const parts = [
    item.workshop_name,
    item.machine_name || item.team_name,
    item.created_by_name
  ].filter(Boolean)
  return parts.length ? parts.join(' · ') : '-'
}

function actionLabel(item) {
  return isCoilHistoryItem(item) ? '继续录入' : '继续查看'
}

async function load() {
  loading.value = true
  pageError.value = ''
  try {
    const data = await fetchMobileHistory({
      business_date: businessDate.value,
      all_day: true,
      limit: 30,
    })
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
  const routeName = resolveDetailRouteName(item)
  if (routeName === 'mobile-unified-entry') {
    router.push({
      name: routeName,
      query: {
        businessDate: item.business_date,
        shiftId: item.shift_id
      }
    })
    return
  }
  router.push({
    name: routeName,
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

<style scoped>
.mobile-top {
  grid-template-columns: minmax(0, 1fr);
  align-items: stretch;
}

.mobile-top h1,
.mobile-top p {
  writing-mode: horizontal-tb;
}

.header-actions {
  width: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
}

.mobile-history-date {
  width: 100%;
}

.mobile-history-tags {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  flex-wrap: wrap;
}

.mobile-inline-action {
  min-height: 40px;
}

@media (max-width: 480px) {
  .header-actions {
    grid-template-columns: minmax(0, 1fr);
  }

  .mobile-inline-action {
    width: 100%;
    min-height: 44px;
  }
}
</style>
