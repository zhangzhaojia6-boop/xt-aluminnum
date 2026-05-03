<template>
  <main class="team-lead-shell" data-testid="team-lead-shell">
    <header class="team-lead-shell__head">
      <div>
        <span>班长一屏</span>
        <strong>{{ targetDate }}</strong>
      </div>
      <el-button :icon="Refresh" :loading="loading" circle aria-label="刷新" @click="loadOverview" />
    </header>

    <TeamLeadOverview :payload="overview" :loading="loading" />
  </main>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

import { fetchTeamLeadOverview } from '../../api/team-lead'
import TeamLeadOverview from './TeamLeadOverview.vue'

const targetDate = ref(localDate())
const loading = ref(false)
const overview = ref({
  scheduled_count: 0,
  attended_count: 0,
  reported_count: 0,
  returned_count: 0,
  reminder_count: 0,
  escalation_count: 0,
  pending_list: [],
  returned_list: [],
  reminder_list: [],
  shift_health: 'green'
})
let timer = 0

function localDate() {
  const now = new Date()
  const local = new Date(now.getTime() - now.getTimezoneOffset() * 60000)
  return local.toISOString().slice(0, 10)
}

async function loadOverview() {
  loading.value = true
  try {
    overview.value = await fetchTeamLeadOverview({ date: targetDate.value })
  } catch {
    ElMessage.error('加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadOverview()
  timer = window.setInterval(loadOverview, 30000)
})

onBeforeUnmount(() => {
  if (timer) window.clearInterval(timer)
})
</script>

<style scoped>
.team-lead-shell {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  gap: 12px;
  min-height: 100vh;
  padding: 14px;
  background: var(--xt-bg-shell);
}

.team-lead-shell__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 58px;
  padding: 0 4px;
}

.team-lead-shell__head span {
  display: block;
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-weight: 850;
}

.team-lead-shell__head strong {
  display: block;
  color: var(--xt-text);
  font-size: 24px;
  font-weight: 900;
  line-height: 1.15;
}
</style>

