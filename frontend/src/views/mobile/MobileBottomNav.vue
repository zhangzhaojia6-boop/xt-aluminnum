<template>
  <div class="mobile-bottom-nav-wrap">
    <div v-if="pendingCount > 0 || syncing" class="mobile-sync-banner">
      <span>{{ syncing ? '正在同步离线数据...' : `${pendingCount}条待同步` }}</span>
      <el-button link :loading="syncing" @click="replayPendingRequests">重新同步</el-button>
    </div>
    <nav class="mobile-bottom-nav" aria-label="移动导航">
      <button
        v-for="item in navItems"
        :key="item.name"
        type="button"
        :class="['mobile-bottom-nav__item', { 'is-active': route.name === item.name }]"
        @click="go(item)"
      >
        <span class="mobile-bottom-nav__label">{{ item.label }}</span>
        <span v-if="item.badge > 0" class="mobile-bottom-nav__badge">{{ item.badge }}</span>
      </button>
    </nav>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useRetryQueue } from '../../composables/useRetryQueue'
import { fetchCurrentShift } from '../../api/mobile'

const route = useRoute()
const router = useRouter()
const { pendingCount, replayPendingRequests, syncing } = useRetryQueue()
const pendingAttendanceCount = ref(0)

const navItems = computed(() => [
  { name: 'mobile-entry', label: '入口', badge: 0 },
  { name: 'mobile-attendance-confirm', label: '考勤', badge: pendingAttendanceCount.value },
  { name: 'mobile-report-history', label: '历史', badge: 0 }
])

async function loadBadge() {
  try {
    const currentShift = await fetchCurrentShift()
    pendingAttendanceCount.value = Number(currentShift?.attendance_pending_count || 0)
  } catch {
    pendingAttendanceCount.value = 0
  }
}

function go(item) {
  if (route.name === item.name) return
  router.push({ name: item.name })
}

watch(
  () => route.fullPath,
  () => {
    loadBadge()
  }
)

onMounted(loadBadge)
</script>
