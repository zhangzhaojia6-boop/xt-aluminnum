<template>
  <div class="xt-entry" data-testid="entry-shell">
    <header class="xt-entry__topbar">
      <RouterLink class="xt-entry__brand" to="/entry" aria-label="鑫泰铝业独立填报端">
        <span class="xt-entry__mark">鑫</span>
        <span>独立填报端</span>
      </RouterLink>
      <div class="xt-entry__shift">{{ currentShift }}</div>
      <span class="xt-entry__user">{{ userName }}</span>
    </header>

    <main class="xt-entry__content">
      <RouterView v-slot="{ Component }">
        <Transition name="xt-fade" mode="out-in">
          <component :is="Component" />
        </Transition>
      </RouterView>
    </main>

    <nav class="xt-entry__tabbar" aria-label="录入端导航">
      <RouterLink
        v-for="tab in tabs"
        :key="tab.path"
        :to="tab.path"
        class="xt-entry__tab"
        :class="{ 'is-active': isActive(tab.path) }"
      >
        <el-icon><component :is="tab.icon" /></el-icon>
        <span>{{ tab.label }}</span>
      </RouterLink>
    </nav>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { Document, EditPen, HomeFilled, User } from '@element-plus/icons-vue'

import { useAuthStore } from '../stores/auth'

const route = useRoute()
const auth = useAuthStore()

const userName = computed(() => auth.displayName || auth.user?.name || auth.user?.username || '操作员')
const currentShift = computed(() => auth.machineContext?.machine_name || auth.machineContext?.machine_code || '当前班次')

const tabs = [
  { path: '/entry', label: '首页', icon: HomeFilled },
  { path: '/entry/report', label: '录入', icon: EditPen },
  { path: '/entry/drafts', label: '草稿', icon: Document },
  { path: '/entry/profile', label: '我的', icon: User }
]

function isActive(path) {
  if (path === '/entry') return route.path === '/entry'
  return route.path.startsWith(path)
}
</script>

<style scoped>
.xt-entry {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  min-height: 100dvh;
  max-width: 560px;
  margin: 0 auto;
  background: var(--xt-bg-page);
  color: var(--xt-text);
}

.xt-entry__topbar {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: var(--xt-space-3);
  padding: var(--xt-space-3) var(--xt-space-4);
  background: var(--xt-bg-panel);
  border-bottom: 1px solid var(--xt-border-light);
}

.xt-entry__brand {
  display: inline-flex;
  align-items: center;
  gap: var(--xt-space-2);
  color: var(--xt-text);
  font-weight: 700;
  text-decoration: none;
}

.xt-entry__mark {
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  border-radius: var(--xt-radius-lg);
  background: var(--xt-primary);
  color: var(--xt-text-inverse);
}

.xt-entry__shift {
  padding: 2px var(--xt-space-2);
  border-radius: 999px;
  background: var(--xt-gray-100);
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-xs);
}

.xt-entry__user {
  margin-left: auto;
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-sm);
}

.xt-entry__content {
  flex: 1;
  padding: var(--xt-space-4);
  padding-bottom: calc(var(--xt-tabbar-height) + var(--xt-space-5) + env(safe-area-inset-bottom));
}

.xt-entry__tabbar {
  position: fixed;
  bottom: 0;
  left: 50%;
  z-index: 100;
  width: min(100%, 560px);
  min-height: var(--xt-tabbar-height);
  display: flex;
  align-items: center;
  justify-content: space-around;
  padding-bottom: env(safe-area-inset-bottom);
  background: var(--xt-bg-panel);
  border-top: 1px solid var(--xt-border-light);
  transform: translateX(-50%);
}

.xt-entry__tab {
  min-width: 64px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: var(--xt-space-1) var(--xt-space-3);
  color: var(--xt-text-muted);
  font-size: 10px;
  text-decoration: none;
  transition: color var(--xt-motion-fast);
}

.xt-entry__tab .el-icon {
  font-size: 20px;
}

.xt-entry__tab.is-active {
  color: var(--xt-primary);
}
</style>
