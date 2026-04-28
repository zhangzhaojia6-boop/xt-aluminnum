<template>
  <div class="xt-page command-entry-home" data-testid="mobile-entry">
    <XtPageHeader title="独立填报端首页" eyebrow="03 ENTRY" />
    <XtGrid>
      <XtKpi label="待填任务" value="12" unit="项" trend="今日" />
      <XtKpi label="已提交" value="18" unit="单" trend="已同步" tone="success" />
      <XtKpi label="异常补卡" value="3" unit="条" trend="待处理" tone="warning" />
    </XtGrid>
    <XtCard title="批次号" class="xt-section-gap">
      <div class="entry-batch-card">
        <input v-model="batchNo" aria-label="批次号" placeholder="扫码或输入批次号" @keyup.enter="openAdvancedForm" />
        <button type="button" data-testid="mobile-go-report" @click="openAdvancedForm">开始填报</button>
      </div>
    </XtCard>
    <XtCard title="快捷操作">
      <div class="command-action-grid">
        <button type="button" @click="openReportForm">快速填报</button>
        <button type="button" @click="openAdvancedForm">高级填报</button>
        <button type="button" @click="goDrafts">草稿</button>
        <button type="button" @click="goHistory">历史</button>
      </div>
    </XtCard>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

import { XtCard, XtGrid, XtKpi, XtPageHeader } from '../../components/xt'

const router = useRouter()
const batchNo = ref('')
const businessDate = new Date().toISOString().slice(0, 10)

function openReportForm() {
  router.push(`/entry/report/${businessDate}/1`)
}

function openAdvancedForm() {
  router.push(`/entry/advanced/${businessDate}/1`)
}

function goHistory() {
  router.push({ name: 'mobile-report-history' })
}

function goDrafts() {
  router.push({ name: 'entry-drafts' })
}
</script>

<style scoped>
.command-entry-home {
  display: grid;
  gap: var(--xt-space-5);
}

.entry-batch-card {
  display: flex;
  gap: var(--xt-space-3);
}

.entry-batch-card input {
  flex: 1;
  height: 40px;
  padding: 0 var(--xt-space-3);
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-md);
}

.entry-batch-card button,
.command-action-grid button {
  height: 40px;
  padding: 0 var(--xt-space-4);
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-md);
  background: var(--xt-bg-panel);
}

.command-action-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--xt-space-3);
}

.xt-section-gap {
  margin-top: var(--xt-space-2);
}
</style>
