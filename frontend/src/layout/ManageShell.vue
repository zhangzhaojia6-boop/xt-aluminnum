<template>
  <div
    class="xt-manage"
    :class="{
      'xt-manage--collapsed': collapsed,
      'xt-manage--auto-rail': isAutoRail,
      'xt-manage--mobile': isMobileViewport,
      'xt-manage--compact-topbar': isCompactTopbar
    }"
    :data-nav-mode="navMode"
    data-testid="manage-shell"
  >
    <aside class="xt-manage__sidebar">
      <RouterLink class="xt-manage__brand" to="/manage/today" aria-label="鑫泰铝业数据中枢">
        <XtLogo :variant="collapsed ? 'icon' : 'full'" />
        <span v-if="!collapsed || isAutoRail" class="xt-manage__brand-text">数据中枢</span>
      </RouterLink>

      <nav class="xt-manage__nav" aria-label="管理端导航">
        <section v-for="group in navGroups" :key="group.label" class="xt-manage__nav-group">
          <div v-if="!collapsed || isAutoRail" class="xt-manage__nav-group-label">{{ group.label }}</div>
          <RouterLink
            v-for="item in group.items"
            :key="item.path"
            :to="navTo(item.path)"
            class="xt-manage__nav-item"
            :class="{ 'is-active': isActive(item.path) }"
            :title="item.title"
            :aria-label="item.title"
            :aria-current="isActive(item.path) ? 'page' : undefined"
            :data-nav-title="item.title"
          >
            <el-icon><component :is="item.icon" /></el-icon>
            <span v-if="!collapsed || isAutoRail" class="xt-manage__nav-label">
              <span>{{ item.shortLabel || item.title }}</span>
              <small v-if="item.secondaryGroup">{{ item.secondaryGroup }}</small>
            </span>
          </RouterLink>
        </section>
      </nav>

      <button
        v-if="!isAutoRail && !isMobileViewport"
        class="xt-manage__collapse-btn"
        type="button"
        :aria-label="collapsed ? '展开侧边栏' : '收起侧边栏'"
        :aria-expanded="collapsed ? 'false' : 'true'"
        @click="toggleCollapse"
      >
        <el-icon><Fold v-if="!collapsed" /><Expand v-else /></el-icon>
      </button>
    </aside>

    <div class="xt-manage__main">
      <header class="xt-manage__topbar">
        <button class="xt-manage__hamburger" type="button" aria-label="打开导航" @click="drawerOpen = true">
          <el-icon><Menu /></el-icon>
        </button>
        <button class="xt-manage__search-trigger" type="button" @click="searchOpen = true">
          <el-icon><Search /></el-icon>
          <span>搜索</span>
          <kbd>Ctrl K</kbd>
        </button>
        <div class="xt-manage__topbar-right">
          <button class="xt-manage__settings-trigger" type="button" aria-label="设置" @click="settingsDrawerOpen = true">
            <el-icon><Setting /></el-icon>
          </button>
          <button class="xt-manage__assistant-trigger" type="button" @click="openAssistantFromTopbar">
            <el-icon><ChatDotRound /></el-icon>
            <span>AI 助手</span>
          </button>
          <el-dropdown trigger="click">
            <button class="xt-manage__user" type="button">
              <el-avatar :size="28">{{ userInitial }}</el-avatar>
              <span>{{ userName }}</span>
            </button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="router.push('/entry')">操作员端</el-dropdown-item>
                <el-dropdown-item divided @click="logout">退出登录</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <main class="xt-manage__content xt-page">
        <div class="xt-manage__container">
          <RouterView v-slot="{ Component }">
            <Transition name="xt-fade" mode="out-in">
              <component :is="Component" />
            </Transition>
          </RouterView>
        </div>
      </main>
    </div>

    <el-drawer v-model="drawerOpen" direction="ltr" :size="drawerSize" :with-header="false" class="xt-manage__drawer">
      <div class="xt-manage__drawer-head">
        <RouterLink class="xt-manage__drawer-brand" to="/manage/today" aria-label="鑫泰铝业数据中枢" @click="drawerOpen = false">
          <XtLogo variant="icon" />
          <span>数据中枢</span>
        </RouterLink>
        <button class="xt-manage__drawer-close" type="button" aria-label="关闭导航" @click="drawerOpen = false">
          <el-icon><Close /></el-icon>
        </button>
      </div>
      <nav class="xt-manage__drawer-nav" aria-label="移动端管理导航">
        <template v-for="group in navGroups" :key="group.label">
          <div class="xt-manage__nav-group-label">{{ group.label }}</div>
          <RouterLink
            v-for="item in group.items"
            :key="item.path"
            :to="navTo(item.path)"
            class="xt-manage__nav-item"
            :class="{ 'is-active': isActive(item.path) }"
            :aria-label="item.title"
            :aria-current="isActive(item.path) ? 'page' : undefined"
            @click="drawerOpen = false"
          >
            <el-icon><component :is="item.icon" /></el-icon>
            <span class="xt-manage__nav-label">
              <span>{{ item.shortLabel || item.title }}</span>
              <small v-if="item.secondaryGroup">{{ item.secondaryGroup }}</small>
            </span>
          </RouterLink>
        </template>
      </nav>
    </el-drawer>

    <el-dialog v-model="searchOpen" title="搜索" width="520px" class="xt-search-overlay">
      <el-input v-model="keyword" placeholder="搜索功能" :prefix-icon="Search" />
      <div class="xt-manage__search-list">
        <RouterLink
          v-for="item in filteredSearchItems"
          :key="item.path"
          :to="navTo(item.path)"
          class="xt-manage__search-item"
          @click="searchOpen = false"
        >
          <span>{{ item.shortLabel || item.title }}</span>
          <small>{{ item.group }}</small>
        </RouterLink>
      </div>
    </el-dialog>

    <AiAssistantDrawer
      v-model="assistantOpen"
      :context="assistantContext"
      :initial-prompt="assistantInitialPrompt"
      @prompt-consumed="assistantInitialPrompt = ''"
    />
    <SettingsDrawer v-model:open="settingsDrawerOpen" />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { ChatDotRound, Close, Expand, Fold, Menu, Search, Setting } from '@element-plus/icons-vue'

import AiAssistantDrawer from '../components/ai/AiAssistantDrawer.vue'
import SettingsDrawer from '../components/manage/SettingsDrawer.vue'
import { XtLogo } from '../components/xt'
import { manageNavGroups } from '../config/manage-navigation'
import { useAuthStore } from '../stores/auth'
import { AI_ASSISTANT_OPEN_EVENT } from '../utils/assistantLauncher'
import { useHudTheme } from '../composables/useHudTheme.js'

useHudTheme()

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const SIDEBAR_RAIL_BREAKPOINT = 1180
const SIDEBAR_MOBILE_BREAKPOINT = 900
const TOPBAR_COMPACT_BREAKPOINT = 640
const userCollapsed = ref(localStorage.getItem('xt-sidebar-collapsed') === 'true')
const isAutoRail = ref(false)
const isMobileViewport = ref(false)
const isCompactTopbar = ref(false)
const drawerOpen = ref(false)
const searchOpen = ref(false)
const assistantOpen = ref(false)
const settingsDrawerOpen = ref(false)
const assistantContextOverride = ref(null)
const assistantInitialPrompt = ref('')
const keyword = ref('')

const userName = computed(() => auth.displayName || auth.user?.name || auth.user?.username || '用户')
const userInitial = computed(() => userName.value.slice(0, 1).toUpperCase())
const navGroups = computed(() => manageNavGroups(auth, { compact: isMobileViewport.value }))
const collapsed = computed(() => !isMobileViewport.value && (userCollapsed.value || isAutoRail.value))
const drawerSize = computed(() => (isMobileViewport.value ? 'min(312px, 88vw)' : '300px'))
const navMode = computed(() => {
  if (isMobileViewport.value) return 'drawer'
  if (isAutoRail.value) return 'auto-rail'
  return collapsed.value ? 'rail' : 'full'
})
const searchItems = computed(() => navGroups.value.flatMap((group) => group.items.map((item) => ({ ...item, group: group.label }))))
const filteredSearchItems = computed(() => {
  const value = keyword.value.trim().toLowerCase()
  if (!value) return searchItems.value
  return searchItems.value.filter((item) => item.title.toLowerCase().includes(value) || item.path.toLowerCase().includes(value))
})
const assistantContext = computed(() => assistantContextOverride.value || ({
  route: route.path,
  scope: {
    type: 'route',
    key: route.path || '/manage/today'
  }
}))

function isActive(path) {
  return route.path === path || route.path.startsWith(`${path}/`)
}

function navTo(path) {
  if (isMobileViewport.value && route.query.desktop === '1') {
    return { path, query: { desktop: '1' } }
  }
  return path
}

function toggleCollapse() {
  if (isAutoRail.value || isMobileViewport.value) return
  userCollapsed.value = !userCollapsed.value
  localStorage.setItem('xt-sidebar-collapsed', String(userCollapsed.value))
}

function syncSidebarViewport() {
  const width = window.innerWidth
  isMobileViewport.value = width <= SIDEBAR_MOBILE_BREAKPOINT
  isAutoRail.value = width <= SIDEBAR_RAIL_BREAKPOINT && width > SIDEBAR_MOBILE_BREAKPOINT
  isCompactTopbar.value = width <= TOPBAR_COMPACT_BREAKPOINT
  if (!isMobileViewport.value) drawerOpen.value = false
}

function logout() {
  auth.logout()
  router.push('/login')
}

function handleKeydown(event) {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault()
    searchOpen.value = true
  }
}

function handleAssistantOpen(event) {
  const detail = event.detail || {}
  assistantContextOverride.value = {
    route: route.path,
    scope: detail.scope || {
      type: 'route',
      key: route.path || '/manage/today'
    },
    freshness: detail.freshness || {}
  }
  assistantInitialPrompt.value = String(detail.question || '').trim()
  assistantOpen.value = true
}

function openAssistantFromTopbar() {
  assistantContextOverride.value = null
  assistantInitialPrompt.value = ''
  assistantOpen.value = true
}

onMounted(() => {
  syncSidebarViewport()
  window.addEventListener('resize', syncSidebarViewport, { passive: true })
  window.addEventListener('keydown', handleKeydown)
  window.addEventListener(AI_ASSISTANT_OPEN_EVENT, handleAssistantOpen)
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeydown)
  window.removeEventListener(AI_ASSISTANT_OPEN_EVENT, handleAssistantOpen)
  window.removeEventListener('resize', syncSidebarViewport)
})
</script>

<style scoped>
.xt-manage {
  --manage-accent: #00f2ff;
  --manage-accent-soft: rgba(0, 242, 255, 0.12);
  --manage-bg: #03101f;
  --manage-bg-strong: #010a15;
  --manage-panel: #061a31;
  --manage-panel-strong: #082642;
  --manage-line: rgba(0, 242, 255, 0.16);
  --manage-line-strong: rgba(0, 242, 255, 0.34);
  --manage-muted: rgba(185, 223, 235, 0.64);
  --manage-sidebar-expanded: clamp(220px, 17vw, var(--xt-sidebar-width));
  --manage-sidebar-rail: var(--xt-sidebar-collapsed);
  --manage-text: rgba(225, 253, 255, 0.92);
  --manage-warn: #ffab00;
  --xt-bg-page: transparent;
  --xt-bg-shell: var(--manage-bg);
  --xt-bg-panel: rgba(6, 26, 49, 0.88);
  --xt-bg-panel-soft: rgba(9, 36, 63, 0.74);
  --xt-bg-panel-muted: rgba(12, 45, 78, 0.78);
  --xt-bg-panel-strong: rgba(10, 38, 66, 0.95);
  --xt-bg-depth: var(--manage-bg-strong);
  --xt-bg-ink: #020812;
  --xt-bg-ink-soft: #061d35;
  --xt-bg-ink-panel: #081d34;
  --xt-text: var(--manage-text);
  --xt-text-secondary: var(--manage-muted);
  --xt-text-muted: rgba(156, 190, 212, 0.62);
  --xt-text-soft: rgba(208, 230, 242, 0.86);
  --xt-border: var(--manage-line);
  --xt-border-light: rgba(0, 242, 255, 0.1);
  --xt-border-strong: var(--manage-line-strong);
  min-height: 100vh;
  min-height: 100dvh;
  background:
    radial-gradient(circle at 16% 0%, rgba(0, 118, 255, 0.2), transparent 26%),
    radial-gradient(circle at 86% 7%, rgba(0, 242, 255, 0.13), transparent 30%),
    linear-gradient(135deg, var(--manage-bg) 0%, #061d35 48%, var(--manage-bg-strong) 100%);
  color: var(--manage-text);
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

.xt-manage__sidebar {
  position: fixed;
  inset: 0 auto 0 0;
  z-index: 20;
  width: min(var(--manage-sidebar-expanded), 100vw);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background:
    radial-gradient(circle at 0% 0%, rgba(0, 242, 255, 0.14), transparent 34%),
    linear-gradient(180deg, rgba(6, 32, 56, 0.98), rgba(2, 12, 25, 0.98));
  border-right: 1px solid var(--manage-line);
  box-shadow:
    inset -1px 0 0 rgba(255, 255, 255, 0.04),
    18px 0 46px rgba(0, 18, 42, 0.34);
  transition: width var(--xt-motion-normal) var(--xt-ease);
}

.xt-manage__sidebar::before {
  position: absolute;
  inset: 0;
  opacity: 0.24;
  background:
    linear-gradient(rgba(0, 242, 255, 0.07) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 242, 255, 0.07) 1px, transparent 1px);
  background-size: 32px 32px;
  content: "";
  pointer-events: none;
}

.xt-manage__brand,
.xt-manage__nav,
.xt-manage__collapse-btn {
  position: relative;
  z-index: 1;
}

.xt-manage--collapsed .xt-manage__sidebar {
  width: var(--manage-sidebar-rail);
}

.xt-manage--collapsed .xt-manage__brand {
  justify-content: center;
  padding: 0;
}

.xt-manage__brand {
  min-height: var(--xt-topbar-height);
  display: flex;
  align-items: center;
  gap: var(--xt-space-2);
  padding: 0 var(--xt-space-4);
  border-bottom: 1px solid var(--manage-line);
  background:
    linear-gradient(90deg, rgba(0, 242, 255, 0.08), transparent 58%),
    rgba(1, 16, 31, 0.54);
  color: var(--manage-text);
  text-decoration: none;
}

.xt-manage__brand-text {
  margin-left: auto;
  padding: var(--xt-space-1) var(--xt-space-2);
  border: 1px solid var(--manage-line-strong);
  border-radius: 6px;
  background: var(--manage-accent-soft);
  color: #74f5ff;
  box-shadow: 0 0 18px rgba(0, 242, 255, 0.08);
  font-size: var(--xt-text-xs);
  font-weight: 700;
  white-space: nowrap;
}

.xt-manage__nav,
.xt-manage__drawer-nav {
  min-height: 0;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 12px 10px;
  overflow-y: auto;
  overscroll-behavior: contain;
  scrollbar-width: thin;
  scrollbar-color: rgba(0, 242, 255, 0.36) transparent;
}

.xt-manage__nav {
  padding-bottom: max(12px, env(safe-area-inset-bottom));
}

.xt-manage__nav-group {
  display: grid;
  gap: 4px;
}

.xt-manage__nav-group-label {
  padding: 7px 10px 2px;
  font-size: var(--xt-text-xs);
  color: rgba(116, 245, 255, 0.72);
  font-weight: 850;
  letter-spacing: 0.08em;
}

.xt-manage__nav-item {
  position: relative;
  min-height: 40px;
  min-width: 0;
  display: flex;
  align-items: center;
  gap: var(--xt-space-2);
  padding: 0 var(--xt-space-3);
  overflow: hidden;
  border: 1px solid transparent;
  border-radius: 10px;
  color: var(--manage-muted);
  font-size: var(--xt-text-sm);
  font-weight: 600;
  text-decoration: none;
  touch-action: manipulation;
  transition:
    background-color var(--xt-motion-fast) var(--xt-ease),
    border-color var(--xt-motion-fast) var(--xt-ease),
    box-shadow var(--xt-motion-fast) var(--xt-ease),
    color var(--xt-motion-fast) var(--xt-ease),
    transform var(--xt-motion-fast) var(--xt-ease);
}

.xt-manage__nav-item::before {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: currentcolor;
  box-shadow: 0 0 12px currentcolor;
  opacity: 0;
  transform: scale(0.65);
  transition:
    opacity var(--xt-motion-fast) var(--xt-ease),
    transform var(--xt-motion-fast) var(--xt-ease);
  content: "";
}

.xt-manage__nav-item .el-icon {
  flex: 0 0 auto;
  font-size: 17px;
  color: currentcolor;
}

.xt-manage__nav-item:active {
  transform: scale(0.97);
}

@media (hover: hover) {
  .xt-manage__nav-item:hover {
    border-color: rgba(0, 242, 255, 0.18);
    background: rgba(0, 242, 255, 0.07);
    color: rgba(225, 253, 255, 0.9);
  }
}

.xt-manage__nav-item.is-active {
  border-color: var(--manage-line-strong);
  background:
    linear-gradient(90deg, rgba(0, 242, 255, 0.16), rgba(0, 242, 255, 0.05)),
    rgba(1, 16, 31, 0.72);
  color: #e1fdff;
  font-weight: 700;
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.04),
    0 0 24px rgba(0, 242, 255, 0.1);
}

.xt-manage__nav-item.is-active::before {
  opacity: 1;
  transform: scale(1);
}

.xt-manage__nav-item:focus-visible {
  outline: 2px solid rgba(116, 245, 255, 0.72);
  outline-offset: 2px;
}

.xt-manage__nav-label {
  min-width: 0;
  display: grid;
  gap: 1px;
  line-height: 1.15;
}

.xt-manage__nav-label > span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.xt-manage__nav-label small {
  color: rgba(185, 223, 235, 0.5);
  font-size: var(--xt-text-xs);
  font-weight: 760;
}

.xt-manage--collapsed .xt-manage__nav-item {
  justify-content: center;
  padding: 0;
}

.xt-manage--collapsed .xt-manage__nav-item::before {
  position: absolute;
  left: 8px;
}

.xt-manage--auto-rail .xt-manage__sidebar {
  contain: layout paint;
  will-change: width;
}

.xt-manage--auto-rail .xt-manage__brand-text,
.xt-manage--auto-rail .xt-manage__nav-group-label,
.xt-manage--auto-rail .xt-manage__nav-label {
  opacity: 0;
  transform: translateX(-6px);
  transition:
    opacity var(--xt-motion-fast) var(--xt-ease),
    transform var(--xt-motion-fast) var(--xt-ease);
}

.xt-manage--auto-rail .xt-manage__sidebar:is(:hover, :focus-within) {
  z-index: 30;
  width: min(var(--manage-sidebar-expanded), calc(100vw - 12px));
  box-shadow:
    inset -1px 0 0 rgba(255, 255, 255, 0.04),
    26px 0 56px rgba(0, 18, 42, 0.46);
}

.xt-manage__collapse-btn,
.xt-manage__drawer-close,
.xt-manage__hamburger,
.xt-manage__search-trigger,
.xt-manage__assistant-trigger,
.xt-manage__settings-trigger,
.xt-manage__user {
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  touch-action: manipulation;
  transition:
    background-color var(--xt-motion-fast) var(--xt-ease),
    border-color var(--xt-motion-fast) var(--xt-ease),
    box-shadow var(--xt-motion-fast) var(--xt-ease),
    color var(--xt-motion-fast) var(--xt-ease),
    transform var(--xt-motion-fast) var(--xt-ease);
}

.xt-manage__collapse-btn:active,
.xt-manage__drawer-close:active,
.xt-manage__hamburger:active,
.xt-manage__search-trigger:active,
.xt-manage__assistant-trigger:active,
.xt-manage__settings-trigger:active,
.xt-manage__user:active {
  transform: scale(0.96);
}

.xt-manage__collapse-btn {
  height: 44px;
  border-top: 1px solid var(--manage-line);
  color: var(--manage-muted);
  background: rgba(1, 16, 31, 0.62);
}

@media (hover: hover) {
  .xt-manage__collapse-btn:hover,
  .xt-manage__drawer-close:hover,
  .xt-manage__hamburger:hover,
  .xt-manage__search-trigger:hover,
  .xt-manage__assistant-trigger:hover,
  .xt-manage__settings-trigger:hover,
  .xt-manage__user:hover {
    border-color: var(--manage-line-strong);
    background: rgba(0, 242, 255, 0.08);
    color: var(--manage-text);
  }
}

.xt-manage__main {
  min-height: 100vh;
  margin-left: var(--manage-sidebar-expanded);
  background:
    radial-gradient(circle at 22% 0%, rgba(0, 118, 255, 0.12), transparent 30%),
    linear-gradient(180deg, rgba(5, 21, 39, 0.62), transparent 280px);
  transition: margin-left var(--xt-motion-normal) var(--xt-ease);
}

.xt-manage--collapsed .xt-manage__main {
  margin-left: var(--manage-sidebar-rail);
}

.xt-manage__topbar {
  position: sticky;
  top: 0;
  z-index: 10;
  height: var(--xt-topbar-height);
  display: flex;
  align-items: center;
  gap: var(--xt-space-3);
  padding: 0 max(var(--xt-space-5), env(safe-area-inset-right)) 0 max(var(--xt-space-5), env(safe-area-inset-left));
  overflow: hidden;
  background:
    linear-gradient(90deg, rgba(2, 17, 32, 0.98), rgba(7, 38, 66, 0.94)),
    radial-gradient(circle at 82% 0%, rgba(0, 242, 255, 0.12), transparent 34%);
  border-bottom: 1px solid var(--manage-line);
  box-shadow:
    inset 0 -1px 0 rgba(255, 255, 255, 0.04),
    0 14px 38px rgba(0, 18, 42, 0.26);
}

.xt-manage__topbar::before {
  position: absolute;
  inset: auto 0 0;
  height: 1px;
  background: linear-gradient(90deg, transparent, rgba(0, 242, 255, 0.72), transparent);
  content: "";
  animation: xtManageEnergyLine 5s linear infinite;
}

.xt-manage__hamburger {
  display: none;
  width: 40px;
  height: 40px;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--manage-line);
  border-radius: 10px;
  color: var(--manage-text);
  background: rgba(1, 16, 31, 0.72);
}

.xt-manage__search-trigger {
  min-width: 260px;
  flex: 0 1 320px;
  height: 38px;
  display: flex;
  align-items: center;
  gap: var(--xt-space-2);
  padding: 0 var(--xt-space-3);
  border: 1px solid var(--manage-line);
  border-radius: 10px;
  color: var(--manage-muted);
  background: rgba(1, 16, 31, 0.72);
  box-shadow: inset 0 -1px 0 rgba(0, 242, 255, 0.14);
}

.xt-manage__search-trigger kbd {
  margin-left: auto;
  padding: 1px var(--xt-space-2);
  border: 1px solid var(--manage-line-strong);
  border-radius: var(--xt-radius-pill);
  background: var(--manage-accent-soft);
  color: rgba(225, 253, 255, 0.78);
  font-family: var(--xt-font-mono);
  font-size: var(--xt-text-xs);
  font-weight: 700;
  line-height: 1.5;
}

.xt-manage__topbar-right {
  margin-left: auto;
  min-width: 0;
  flex: 0 0 auto;
  display: flex;
  align-items: center;
  gap: var(--xt-space-2);
}

.xt-manage__assistant-trigger {
  min-height: 36px;
  display: inline-flex;
  align-items: center;
  gap: var(--xt-space-2);
  padding: 0 var(--xt-space-3);
  border: 1px solid rgba(0, 242, 255, 0.4);
  border-radius: 10px;
  background:
    linear-gradient(180deg, rgba(0, 242, 255, 0.18), rgba(0, 104, 153, 0.18)),
    rgba(1, 16, 31, 0.82);
  color: #e1fdff;
  box-shadow: 0 0 22px rgba(0, 242, 255, 0.12);
  font-size: var(--xt-text-sm);
  font-weight: 850;
}

.xt-manage__settings-trigger {
  width: 36px;
  height: 36px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid transparent;
  border-radius: 10px;
  color: var(--manage-muted);
}

.xt-manage__user {
  display: flex;
  align-items: center;
  gap: var(--xt-space-2);
  min-height: 36px;
  padding: 0 var(--xt-space-2);
  border: 1px solid transparent;
  border-radius: 999px;
  color: var(--manage-muted);
}

.xt-manage__user :deep(.el-avatar) {
  background: linear-gradient(180deg, rgba(116, 245, 255, 0.34), rgba(0, 118, 255, 0.22));
  color: #e1fdff;
  font-weight: 800;
}

.xt-manage__content {
  padding: var(--xt-space-5);
}

.xt-manage__container {
  max-width: var(--xt-content-max);
  margin: 0 auto;
}

.xt-manage__search-list {
  display: grid;
  gap: var(--xt-space-2);
  margin-top: var(--xt-space-4);
}

.xt-manage__search-item {
  display: flex;
  justify-content: space-between;
  padding: var(--xt-space-3);
  border: 1px solid rgba(0, 242, 255, 0.12);
  border-radius: 10px;
  color: var(--manage-text);
  text-decoration: none;
  background: rgba(1, 16, 31, 0.72);
}

.xt-manage__search-item small {
  color: var(--manage-muted);
}

:deep(.xt-manage__drawer) {
  --manage-accent: #00f2ff;
  --manage-accent-soft: rgba(0, 242, 255, 0.12);
  --manage-bg: #03101f;
  --manage-bg-strong: #010a15;
  --manage-panel: #061a31;
  --manage-panel-strong: #082642;
  --manage-line: rgba(0, 242, 255, 0.16);
  --manage-line-strong: rgba(0, 242, 255, 0.34);
  --manage-muted: rgba(185, 223, 235, 0.64);
  --manage-text: rgba(225, 253, 255, 0.92);
  --manage-warn: #ffab00;
  background:
    radial-gradient(circle at 0% 0%, rgba(0, 242, 255, 0.14), transparent 34%),
    linear-gradient(180deg, rgba(6, 32, 56, 0.98), rgba(2, 12, 25, 0.98));
}

:deep(.xt-manage__drawer .el-drawer__body) {
  min-height: 100%;
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
  background: transparent;
}

.xt-manage__drawer-head {
  position: relative;
  min-height: 64px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-3);
  padding: 0 max(14px, env(safe-area-inset-right)) 0 max(14px, env(safe-area-inset-left));
  border-bottom: 1px solid var(--manage-line);
  background:
    linear-gradient(90deg, rgba(0, 242, 255, 0.12), transparent 62%),
    rgba(1, 16, 31, 0.62);
}

.xt-manage__drawer-head::after {
  position: absolute;
  inset: auto 12px 0;
  height: 1px;
  background: linear-gradient(90deg, rgba(0, 242, 255, 0.68), transparent);
  content: "";
}

.xt-manage__drawer-brand {
  min-width: 0;
  display: inline-flex;
  align-items: center;
  gap: var(--xt-space-2);
  color: var(--manage-text);
  font-size: var(--xt-text-sm);
  font-weight: 850;
  letter-spacing: 0.08em;
  text-decoration: none;
}

.xt-manage__drawer-brand span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.xt-manage__drawer-close {
  width: 38px;
  height: 38px;
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--manage-line);
  border-radius: 10px;
  background: rgba(1, 16, 31, 0.72);
  color: var(--manage-text);
}

:deep(.xt-search-overlay) {
  --manage-accent: #00f2ff;
  --manage-accent-soft: rgba(0, 242, 255, 0.12);
  --manage-line: rgba(0, 242, 255, 0.16);
  --manage-muted: rgba(185, 223, 235, 0.64);
  --manage-text: rgba(225, 253, 255, 0.92);
}

:deep(.xt-search-overlay),
:deep(.xt-search-overlay .el-dialog) {
  border: 1px solid var(--manage-line, rgba(0, 242, 255, 0.16));
  border-radius: 16px;
  background:
    linear-gradient(180deg, rgba(6, 32, 56, 0.98), rgba(2, 12, 25, 0.98));
  color: var(--manage-text, rgba(225, 253, 255, 0.92));
}

:deep(.xt-search-overlay .el-dialog__title) {
  color: var(--manage-text, rgba(225, 253, 255, 0.92));
}

:deep(.xt-search-overlay .el-input__wrapper) {
  border-radius: 10px;
  background: rgba(1, 16, 31, 0.72);
  box-shadow:
    inset 0 -1px 0 rgba(0, 242, 255, 0.22),
    inset 0 0 0 1px var(--manage-line, rgba(0, 242, 255, 0.16));
}

:deep(.xt-search-overlay .el-input__inner) {
  color: var(--manage-text, rgba(225, 253, 255, 0.92));
}

@keyframes xtManageEnergyLine {
  0% { transform: translateX(-40%); opacity: 0.34; }
  50% { opacity: 1; }
  100% { transform: translateX(40%); opacity: 0.34; }
}

@media (max-width: 1180px) {
  .xt-manage__sidebar {
    width: var(--manage-sidebar-rail);
  }

  .xt-manage__brand {
    justify-content: center;
    padding: 0;
  }

  .xt-manage__brand :deep(.xt-logo__text),
  .xt-manage__brand-text,
  .xt-manage__nav-group-label,
  .xt-manage__nav-label {
    display: none;
  }

  .xt-manage__nav,
  .xt-manage__drawer-nav {
    gap: var(--xt-space-2);
    padding: 12px 8px;
  }

  .xt-manage__nav-item {
    justify-content: center;
    padding: 0;
  }

  .xt-manage__nav-item::before {
    position: absolute;
    left: 8px;
  }

  .xt-manage__collapse-btn {
    display: none;
  }

  .xt-manage--auto-rail .xt-manage__sidebar:is(:hover, :focus-within) .xt-manage__brand {
    justify-content: flex-start;
    padding: 0 var(--xt-space-4);
  }

  .xt-manage--auto-rail .xt-manage__sidebar:is(:hover, :focus-within) .xt-manage__brand-text {
    display: inline-flex;
    opacity: 1;
    transform: none;
  }

  .xt-manage--auto-rail .xt-manage__sidebar:is(:hover, :focus-within) .xt-manage__nav-group-label {
    display: block;
    opacity: 1;
    transform: none;
  }

  .xt-manage--auto-rail .xt-manage__sidebar:is(:hover, :focus-within) .xt-manage__nav-label {
    display: grid;
    opacity: 1;
    transform: none;
  }

  .xt-manage--auto-rail .xt-manage__sidebar:is(:hover, :focus-within) .xt-manage__nav-item {
    justify-content: flex-start;
    padding: 0 var(--xt-space-3);
  }

  .xt-manage--auto-rail .xt-manage__sidebar:is(:hover, :focus-within) .xt-manage__nav-item::before {
    position: static;
  }

  .xt-manage__main,
  .xt-manage--collapsed .xt-manage__main {
    margin-left: var(--manage-sidebar-rail);
  }

  .xt-manage__hamburger {
    display: none;
  }

  .xt-manage__search-trigger {
    flex-basis: 280px;
    min-width: 0;
    width: min(320px, 100%);
  }

  .xt-manage__content {
    padding: var(--xt-space-4);
  }
}

@media (max-width: 900px) {
  .xt-manage__sidebar {
    display: none;
  }

  .xt-manage__main,
  .xt-manage--collapsed .xt-manage__main {
    margin-left: 0;
  }

  .xt-manage__hamburger {
    display: inline-flex;
  }

  .xt-manage__drawer-nav .xt-manage__nav-group-label,
  .xt-manage__drawer-nav .xt-manage__nav-label {
    display: grid;
  }

  .xt-manage__drawer-nav .xt-manage__nav-item {
    min-height: 44px;
    justify-content: flex-start;
    padding: 0 var(--xt-space-3);
  }

  .xt-manage__drawer-nav .xt-manage__nav-item::before {
    position: static;
  }

  .xt-manage__drawer-nav {
    padding: 16px max(12px, env(safe-area-inset-right)) max(20px, env(safe-area-inset-bottom)) max(12px, env(safe-area-inset-left));
  }
}

@media (max-height: 760px) and (min-width: 901px) {
  .xt-manage__brand {
    min-height: var(--xt-topbar-height);
  }

  .xt-manage__nav {
    gap: var(--xt-space-1);
    padding-block: var(--xt-space-2);
  }

  .xt-manage__nav-item {
    min-height: 38px;
  }
}

@media (max-height: 620px) and (min-width: 901px) {
  .xt-manage__brand {
    min-height: 52px;
  }

  .xt-manage__nav {
    gap: 4px;
    padding-block: 8px;
  }

  .xt-manage__nav-group {
    gap: 4px;
  }

  .xt-manage__nav-group-label {
    padding: 4px 10px 0;
    font-size: 11px;
  }

  .xt-manage__nav-item {
    min-height: 34px;
  }

  .xt-manage__collapse-btn {
    height: 40px;
  }
}

@media (max-height: 560px) and (min-width: 901px) {
  .xt-manage__nav-group-label,
  .xt-manage__nav-label small {
    display: none;
  }

  .xt-manage__nav {
    gap: 3px;
    padding-block: 6px;
  }
}

@media (max-width: 767px) {
  .xt-manage__topbar {
    gap: var(--xt-space-2);
    padding: 0 max(var(--xt-space-3), env(safe-area-inset-right)) 0 max(var(--xt-space-3), env(safe-area-inset-left));
  }

  .xt-manage__topbar-right {
    gap: var(--xt-space-1);
  }

  .xt-manage__search-trigger {
    max-width: 180px;
    flex: 1 1 auto;
    padding: 0 10px;
  }

  .xt-manage__search-trigger span {
    max-width: 4em;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .xt-manage__search-trigger kbd {
    display: none;
  }

  .xt-manage__assistant-trigger span,
  .xt-manage__user span {
    display: none;
  }

  .xt-manage__assistant-trigger {
    width: 38px;
    justify-content: center;
    padding: 0;
  }
}

@media (max-width: 520px) {
  .xt-manage__topbar {
    padding: 0 max(10px, env(safe-area-inset-right)) 0 max(10px, env(safe-area-inset-left));
  }

  .xt-manage__search-trigger {
    width: 38px;
    max-width: 38px;
    flex: 0 0 38px;
    justify-content: center;
    padding: 0;
  }

  .xt-manage__search-trigger span {
    display: none;
  }

  .xt-manage__settings-trigger,
  .xt-manage__assistant-trigger {
    width: 36px;
  }
}

@media print {
  .xt-manage {
    min-height: auto;
    background: #fff;
    color: #000;
  }

  .xt-manage__sidebar,
  .xt-manage__topbar,
  :deep(.xt-manage__drawer) {
    display: none !important;
  }

  .xt-manage__main,
  .xt-manage--collapsed .xt-manage__main {
    min-height: auto;
    margin-left: 0;
    background: #fff;
  }

  .xt-manage__content {
    padding: 0;
    background: #fff;
  }

  .xt-manage__container {
    max-width: none;
    margin: 0;
  }
}

@media (prefers-reduced-motion: reduce) {
  .xt-manage__topbar::before {
    animation: none;
  }

  .xt-manage__sidebar,
  .xt-manage__main,
  .xt-manage__nav-item,
  .xt-manage__collapse-btn,
  .xt-manage__hamburger,
  .xt-manage__search-trigger,
  .xt-manage__assistant-trigger,
  .xt-manage__settings-trigger,
  .xt-manage__user {
    transition: none;
  }
}
</style>
