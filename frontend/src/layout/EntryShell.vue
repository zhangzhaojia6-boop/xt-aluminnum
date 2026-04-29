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
  max-width: 600px;
  margin: 0 auto;
  background: var(--xt-bg-page);
  color: var(--xt-text);
  border-right: 1px solid var(--xt-border-light);
  border-left: 1px solid var(--xt-border-light);
}

.xt-entry__topbar {
  position: sticky;
  top: 0;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: var(--xt-space-3);
  min-height: 56px;
  padding: calc(var(--xt-space-2) + env(safe-area-inset-top)) var(--xt-space-4) var(--xt-space-2);
  background: var(--xt-bg-panel);
  border-bottom: 1px solid var(--xt-border-light);
}

.xt-entry__brand {
  display: inline-flex;
  align-items: center;
  gap: var(--xt-space-2);
  color: var(--xt-text);
  font-size: var(--xt-text-sm);
  font-weight: 700;
  text-decoration: none;
}

.xt-entry__mark {
  width: 28px;
  height: 28px;
  display: grid;
  place-items: center;
  border-radius: var(--xt-radius-md);
  background: var(--xt-primary);
  color: var(--xt-text-inverse);
  box-shadow: 0 1px 2px rgba(11, 99, 246, 0.18);
}

.xt-entry__shift {
  padding: 3px var(--xt-space-2);
  border-radius: 999px;
  background: var(--xt-bg-panel-soft);
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-xs);
  font-weight: 600;
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
  width: min(100%, 600px);
  min-height: calc(var(--xt-tabbar-height) + env(safe-area-inset-bottom));
  display: flex;
  align-items: center;
  justify-content: space-around;
  gap: var(--xt-space-1);
  padding: var(--xt-space-1) var(--xt-space-2) calc(var(--xt-space-1) + env(safe-area-inset-bottom));
  background: var(--xt-bg-panel);
  border-top: 1px solid var(--xt-border-light);
  box-shadow: 0 -1px 3px rgba(15, 23, 42, 0.06);
  transform: translateX(-50%);
}

.xt-entry__tab {
  min-width: 64px;
  min-height: 44px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  justify-content: center;
  padding: var(--xt-space-1) var(--xt-space-3);
  border-radius: var(--xt-radius-md);
  color: var(--xt-text-muted);
  font-size: 10px;
  font-weight: 700;
  text-decoration: none;
  transition:
    background-color var(--xt-motion-fast) var(--xt-ease),
    color var(--xt-motion-fast) var(--xt-ease),
    transform var(--xt-motion-fast) var(--xt-ease);
}

.xt-entry__tab .el-icon {
  font-size: 20px;
}

.xt-entry__tab.is-active {
  background: var(--xt-primary-light);
  color: var(--xt-primary);
}

.xt-entry__tab:active {
  transform: scale(0.96);
}

@media (hover: hover) {
  .xt-entry__tab:hover {
    background: var(--xt-bg-panel-soft);
    color: var(--xt-text);
  }
}

@media (max-width: 600px) {
  .xt-entry {
    border-right: 0;
    border-left: 0;
  }
}
</style>
