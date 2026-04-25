<template>
  <CenterPageShell no="03" title="独立填报端首页" data-testid="mobile-entry">
    <template #tools>
      <StatusBadge data-testid="mobile-current-shift" :label="`当前班次 ${currentShiftLabel}`" tone="normal" />
      <SourceBadge source="operator" />
    </template>

    <MockDataNotice v-if="usingFallback" source="fallback" message="班次任务使用兜底数据，提交入口仍按真实表单执行。" />

    <KpiStrip :items="entryHomeMock.kpis" />

    <div data-testid="mobile-role-bucket" class="center-grid-2">
      <SectionCard title="今日待填任务" meta="录入端只负责录入">
        <DataTableShell :columns="taskColumns" :rows="entryHomeMock.tasks">
          <template #cell-status="{ value }">
            <StatusBadge :label="value" :tone="value === '异常待补' ? 'warning' : value === '已提交' ? 'success' : 'info'" />
          </template>
        </DataTableShell>
      </SectionCard>

      <SectionCard title="快捷操作">
        <div class="action-grid">
          <ActionTile label="快速填报" meta="当班报数" primary @click="openReportForm" />
          <ActionTile data-testid="mobile-go-report" label="高项填报" meta="专项 owner" @click="openAdvancedForm" />
          <ActionTile label="历史记录" meta="已提交" @click="goHistory" />
          <ActionTile label="草稿箱" meta="待续填" @click="goDrafts" />
          <ActionTile label="拍照识别" meta="试验功能" @click="openOcr" />
        </div>
      </SectionCard>
    </div>
  </CenterPageShell>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import ActionTile from '../../components/app/ActionTile.vue'
import CenterPageShell from '../../components/app/CenterPageShell.vue'
import DataTableShell from '../../components/app/DataTableShell.vue'
import KpiStrip from '../../components/app/KpiStrip.vue'
import MockDataNotice from '../../components/app/MockDataNotice.vue'
import SectionCard from '../../components/app/SectionCard.vue'
import SourceBadge from '../../components/app/SourceBadge.vue'
import StatusBadge from '../../components/app/StatusBadge.vue'
import { api } from '../../api/index.js'
import { entryHomeMock } from '../../mocks/centerMockData.js'

const router = useRouter()
const currentShift = ref(null)
const usingFallback = ref(false)
const currentShiftLabel = computed(() => currentShift.value?.shift_name || currentShift.value?.name || '白班')

const taskColumns = [
  { key: 'name', label: '任务' },
  { key: 'shift', label: '班次' },
  { key: 'status', label: '状态' }
]

function resolveShiftParam(key, fallback) {
  return currentShift.value?.[key] || currentShift.value?.current_shift?.[key] || fallback
}

function shiftParams() {
  return {
    businessDate: resolveShiftParam('business_date', new Date().toISOString().slice(0, 10)),
    shiftId: resolveShiftParam('shift_id', 1)
  }
}

function openReportForm() {
  const { businessDate, shiftId } = shiftParams()
  router.push(`/entry/report/${businessDate}/${shiftId}`)
}

function openAdvancedForm() {
  const { businessDate, shiftId } = shiftParams()
  router.push(`/entry/advanced/${businessDate}/${shiftId}`)
}

function openOcr() {
  const { businessDate, shiftId } = shiftParams()
  router.push(`/entry/ocr/${businessDate}/${shiftId}`)
}

function goHistory() {
  router.push({ name: 'mobile-report-history' })
}

function goDrafts() {
  router.push({ name: 'entry-drafts' })
}

onMounted(async () => {
  try {
    const { data } = await api.get('/mobile/current-shift', { skipErrorToast: true })
    currentShift.value = data
    usingFallback.value = false
  } catch {
    currentShift.value = { shift_name: '白班' }
    usingFallback.value = true
  }
})
</script>
