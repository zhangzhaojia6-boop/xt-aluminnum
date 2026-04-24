<template>
  <div class="mobile-bottom-nav-wrap">
    <div v-if="pendingCount > 0 || syncing" class="mobile-sync-banner">
      <span>{{ syncing ? '正在同步离线数据...' : `${pendingCount}条待同步` }}</span>
      <el-button link :loading="syncing" @click="replayPendingRequests">重新同步</el-button>
    </div>
    <nav
      class="mobile-bottom-nav"
      aria-label="移动导航"
      :style="{ '--mobile-nav-columns': String(navItems.length) }"
    >
      <button
        v-for="item in navItems"
        :key="item.to?.name || item.label"
        type="button"
        :class="['mobile-bottom-nav__item', { 'is-active': isActiveNavItem(item) }]"
        :aria-label="navItemAriaLabel(item)"
        :aria-current="isActiveNavItem(item) ? 'page' : undefined"
        :title="navItemTitle(item)"
        @click="go(item)"
      >
        <span class="mobile-bottom-nav__content">
          <el-icon v-if="item.icon" class="mobile-bottom-nav__icon">
            <component :is="item.icon" />
          </el-icon>
          <span class="mobile-bottom-nav__label">{{ item.label }}</span>
        </span>
        <span v-if="item.badge > 0" class="mobile-bottom-nav__badge">{{ item.badge }}</span>
      </button>
    </nav>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Clock, DocumentCopy, HomeFilled, Tickets } from '@element-plus/icons-vue'

import { useRetryQueue } from '../../composables/useRetryQueue'
import { fetchCurrentShift } from '../../api/mobile'

const route = useRoute()
const router = useRouter()
const { pendingCount, replayPendingRequests, syncing } = useRetryQueue()
const pendingAttendanceCount = ref(0)

const navItems = computed(() => {
  return [
    { to: { name: 'mobile-entry' }, name: 'mobile-entry', label: '首页', badge: 0, icon: HomeFilled },
    { to: { name: 'mobile-attendance-confirm' }, name: 'mobile-attendance-confirm', label: '异常', badge: pendingAttendanceCount.value, icon: Clock },
    { to: { name: 'mobile-report-history' }, name: 'mobile-report-history', label: '历史', badge: 0, icon: Tickets },
    { to: { name: 'entry-drafts' }, name: 'entry-drafts', label: '草稿', badge: 0, icon: DocumentCopy }
  ]
})

async function loadBadge() {
  try {
    const currentShift = await fetchCurrentShift()
    pendingAttendanceCount.value = Number(currentShift?.attendance_pending_count || 0)
  } catch {
    pendingAttendanceCount.value = 0
  }
}

function go(item) {
  const itemName = item.to?.name
  const itemQuery = item.to?.query || {}
  if (route.name === itemName && hasTargetQueries(route.query, itemQuery)) return
  router.push(item.to)
}

function navItemTitle(item) {
  if (item.badge > 0) {
    return `${item.label}（有 ${item.badge} 条待同步）`
  }
  return item.label
}

function navItemAriaLabel(item) {
  const badgeText = item.badge > 0 ? `，待同步 ${item.badge} 条` : ''
  return `${item.label}${badgeText}`
}

function hasTargetQueries(routeQuery, targetQuery = {}) {
  const normalized = { ...targetQuery }
  return Object.keys(normalized).every((key) => routeQuery[key] === normalized[key])
}

function isActiveNavItem(item) {
  return route.name === item.to?.name && hasTargetQueries(route.query, item.to?.query)
}

watch(
  () => route.fullPath,
  () => {
    loadBadge()
  }
)

onMounted(loadBadge)
</script>
