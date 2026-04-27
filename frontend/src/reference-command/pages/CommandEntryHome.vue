<template>
  <CenterPageShell no="03" title="独立填报端首页" class="entry-home-page" data-testid="mobile-entry">
    <template #tools>
      <StatusBadge data-testid="mobile-current-shift" :label="`当前班次 ${currentShiftLabel}`" tone="normal" />
      <StatusBadge :label="identityLabel" tone="info" />
      <SourceBadge source="operator" />
    </template>

    <MockDataNotice v-if="usingFallback" source="fallback" message="班次任务使用兜底数据，提交入口仍按真实表单执行。" />

    <KpiStrip :items="entryHomeMock.kpis" />

    <div data-testid="mobile-role-bucket" class="center-grid-2">
      <SectionCard title="批次号" meta="唯一主线索" aria-label="批次号主入口">
        <div class="entry-batch-card">
          <div class="entry-batch-card__input">
            <input
              v-model="batchNo"
              aria-label="批次号"
              placeholder="扫码或输入批次号"
              @keyup.enter="openAdvancedForm"
            />
            <button type="button" data-testid="mobile-go-report" @click="openAdvancedForm">开始填报</button>
          </div>
          <div class="entry-batch-card__meta">
            <span>扫码带入线索字段</span>
            <span>字段可人工修改</span>
            <span>MES 待对接</span>
          </div>
        </div>
      </SectionCard>

      <SectionCard title="快捷操作">
        <div class="action-grid">
          <ActionTile label="快速填报" meta="当班报数" primary @click="openReportForm" />
          <ActionTile label="高级填报" meta="完整字段" @click="openAdvancedForm" />
          <ActionTile label="草稿" meta="草稿箱" @click="goDrafts" />
          <ActionTile label="历史" meta="历史记录" @click="goHistory" />
        </div>
      </SectionCard>
    </div>

    <div class="center-grid-2 entry-home-page__lower">
      <SectionCard title="最近提交状态" meta="录入端只负责录入">
        <DataTableShell :columns="taskColumns" :rows="entryHomeMock.tasks">
          <template #cell-status="{ value }">
            <StatusBadge :label="value" :tone="value === '异常待补' ? 'warning' : value === '已提交' ? 'success' : 'info'" />
          </template>
        </DataTableShell>
      </SectionCard>

      <SectionCard title="MES 线索追踪说明" meta="待 MES 对接">
        <div class="entry-mes-copy">
          <p>当前阶段以批次号启动填报；若系统命中上一工序记录，可先回填合金、规格、上机重量等字段。</p>
          <p>所有回填字段均保留人工修改权限；MES 后续码、对象号、状态与更新时间保持待对接语义。</p>
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
const batchNo = ref('')
const currentShiftLabel = computed(() => currentShift.value?.shift_name || currentShift.value?.name || '白班')
const identityLabel = computed(() => currentShift.value?.machine_name || currentShift.value?.team_name || '现场填报')

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
