<template>
  <div class="mobile-shell">
    <div class="mobile-top">
      <div>
        <div class="mobile-kicker">班长手机填报</div>
        <h1>历史填报</h1>
        <p>只显示你自己有权限查看的班次记录，不会混出其他班组数据。</p>
      </div>
      <div class="header-actions">
        <el-button plain @click="load">刷新</el-button>
        <el-button plain @click="goEntry">返回入口</el-button>
      </div>
    </div>

    <el-card class="panel mobile-card">
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

    <MobileBottomNav />
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { fetchMobileHistory } from '../../api/mobile'
import { formatNumber, formatStatusLabel } from '../../utils/display'
import MobileBottomNav from './MobileBottomNav.vue'

const router = useRouter()
const items = ref([])

function statusTagType(status) {
  if (status === 'submitted' || status === 'approved') return 'success'
  if (status === 'returned') return 'danger'
  if (status === 'draft') return 'warning'
  return 'info'
}

async function load() {
  const data = await fetchMobileHistory({ limit: 12 })
  items.value = data.items || []
}

function openDetail(item) {
  router.push({
    name: 'mobile-report-form',
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
