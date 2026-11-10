<template>
  <div
    class="xt-manage"
    :class="{
      'xt-manage--collapsed': collapsed,
      'xt-manage--auto-rail': isAutoRail,
      'xt-manage--mobile': isMobileViewport,
      'xt-manage--compact-topbar': isCompactTopbar,
      'xt-manage--today-wall': isTodayWall,
      'xt-manage--dashboard-wall': isDashboardWall
    }"
    :data-nav-mode="navMode"
    data-testid="manage-shell"
  >
    <aside class="xt-manage__sidebar">
      <RouterLink class="xt-manage__brand" :to="navTo(manageHomePath)" aria-label="鑫泰铝业数据中枢">
        <XtLogo :variant="collapsed ? 'icon' : 'full'" />
        <span v-if="!collapsed || isAutoRail" class="xt-manage__brand-text">数据中枢</span>
      </RouterLink>

      <nav class="xt-manage__nav" aria-label="管理端导航">
        <section v-for="group in navGroups" :key="group.label" class="xt-manage__nav-group">
          <button
            v-if="group.label && group.collapsible && !collapsed"
            class="xt-manage__nav-group-label xt-manage__nav-group-toggle"
            type="button"
            :aria-expanded="isGroupOpen(group) ? 'true' : 'false'"
            @click="toggleGroup(group)"
          >
            <span>{{ group.label }}</span>
            <el-icon><ArrowDown v-if="isGroupOpen(group)" /><ArrowRight v-else /></el-icon>
          </button>
          <div v-else-if="group.label && (!collapsed || isAutoRail)" class="xt-manage__nav-group-label">{{ group.label }}</div>
          <RouterLink
            v-for="item in visibleItems(group)"
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
            <component :is="Component" :key="route.path" />
          </RouterView>
        </div>
      </main>
    </div>

    <Transition name="xt-drawer">
      <div v-if="drawerOpen" class="xt-manage__drawer-overlay" @click.self="drawerOpen = false">
        <aside class="xt-manage__drawer" role="dialog" aria-modal="true" aria-label="管理端移动导航" :style="{ width: drawerSize }">
          <div class="xt-manage__drawer-head">
            <RouterLink class="xt-manage__drawer-brand" :to="navTo(manageHomePath)" aria-label="鑫泰铝业数据中枢" @click="closeDrawerAfterNavigation">
              <XtLogo variant="icon" />
              <span>数据中枢</span>
            </RouterLink>
            <button class="xt-manage__drawer-close" type="button" aria-label="关闭导航" @click="drawerOpen = false">
              <el-icon><Close /></el-icon>
            </button>
          </div>
          <nav class="xt-manage__drawer-nav" aria-label="移动端管理导航">
            <template v-for="group in navGroups" :key="group.label">
              <div v-if="group.label" class="xt-manage__nav-group-label">{{ group.label }}</div>
              <RouterLink
                v-for="item in group.items"
                :key="item.path"
                :to="navTo(item.path)"
                class="xt-manage__nav-item"
                :class="{ 'is-active': isActive(item.path) }"
                :aria-label="item.title"
                :aria-current="isActive(item.path) ? 'page' : undefined"
                @click="closeDrawerAfterNavigation"
              >
                <el-icon><component :is="item.icon" /></el-icon>
                <span class="xt-manage__nav-label">
                  <span>{{ item.title }}</span>
                  <small v-if="item.secondaryGroup">{{ item.secondaryGroup }}</small>
                </span>
              </RouterLink>
            </template>
          </nav>
        </aside>
      </div>
    </Transition>

    <el-dialog v-model="searchOpen" title="搜索" width="min(520px, calc(100vw - 32px))" class="xt-search-overlay">
      <el-input v-model="keyword" placeholder="搜索功能" :prefix-icon="Search" />
      <div class="xt-manage__search-list">
        <RouterLink
          v-for="item in filteredSearchItems"
          :key="item.path"
          :to="navTo(item.path)"
          class="xt-manage__search-item"
          @click="closeSearchAfterNavigation"
        >
          <span>{{ item.shortLabel || item.title }}</span>
          <small>{{ item.group }}</small>
        </RouterLink>
      </div>
    </el-dialog>

    <AiAssistantDrawer
      v-if="assistantOpen"
      v-model="assistantOpen"
      :context="assistantContext"
      :initial-prompt="assistantInitialPrompt"
      @prompt-consumed="assistantInitialPrompt = ''"
    />
  </div>
</template>

<script setup>
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { ArrowDown, ArrowRight, ChatDotRound, Close, Expand, Fold, Menu, Search } from '@element-plus/icons-vue'

const AiAssistantDrawer = defineAsyncComponent(() => import('../components/ai/AiAssistantDrawer.vue'))
import { XtLogo } from '../components/xt'
import { manageNavGroups, manageSearchGroups } from '../config/manage-navigation'
import { useAuthStore } from '../stores/auth'
import { AI_ASSISTANT_OPEN_EVENT, buildAssistantScope } from '../utils/assistantLauncher'
import { useHudTheme } from '../composables/useHudTheme.js'

useHudTheme()

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const SIDEBAR_RAIL_BREAKPOINT = 1180
const SIDEBAR_MOBILE_BREAKPOINT = 900
const TOPBAR_COMPACT_BREAKPOINT = 640
const DASHBOARD_WALL_PATHS = new Set(['/manage/live', '/manage/today', '/manage/production', '/manage/coils', '/manage/fill-details', '/manage/energy'])
const userCollapsed = ref(localStorage.getItem('xt-sidebar-collapsed') === 'true')
const isAutoRail = ref(false)
const isMobileViewport = ref(false)
const isCompactTopbar = ref(false)
const drawerOpen = ref(false)
const searchOpen = ref(false)
const assistantOpen = ref(false)
const openGroups = ref(readOpenGroups())
const assistantContextOverride = ref(null)
const assistantInitialPrompt = ref('')
const keyword = ref('')

const userName = computed(() => auth.displayName || auth.user?.name || auth.user?.username || '用户')
const userInitial = computed(() => userName.value.slice(0, 1).toUpperCase())
const manageHomePath = computed(() => auth.isWorkshopDirector ? '/manage/workshop-dashboard' : '/manage/today')
const navGroups = computed(() => manageNavGroups(auth, { compact: isMobileViewport.value }))
const collapsed = computed(() => !isMobileViewport.value && (userCollapsed.value || isAutoRail.value))
const isTodayWall = computed(() => route.path === '/manage/today')
const isDashboardWall = computed(() => DASHBOARD_WALL_PATHS.has(route.path))
const drawerSize = computed(() => (isMobileViewport.value ? 'min(312px, 88vw)' : '300px'))
const navMode = computed(() => {
  if (isMobileViewport.value) return 'drawer'
  if (isAutoRail.value) return 'auto-rail'
  return collapsed.value ? 'rail' : 'full'
})
const searchItems = computed(() => manageSearchGroups(auth).flatMap((group) => group.items.map((item) => ({ ...item, group: group.label }))))
const filteredSearchItems = computed(() => {
  const value = keyword.value.trim().toLowerCase()
  if (!value) return searchItems.value
  return searchItems.value.filter((item) => item.title.toLowerCase().includes(value) || item.path.toLowerCase().includes(value))
})
const assistantContext = computed(() => assistantContextOverride.value || ({
  route: route.path,
  scope: buildAssistantScope(route)
}))

function isActive(path) {
  return route.path === path || route.path.startsWith(`${path}/`)
}

function readOpenGroups() {
  try {
    return new Set(JSON.parse(localStorage.getItem('xt-nav-open-groups') || '[]'))
  } catch {
    return new Set()
  }
}

// 折叠的组里有当前页面时自动展开；收起成图标栏（含自动窄栏）时全部显示
function isGroupOpen(group) {
  if (!group.collapsible || collapsed.value) return true
  return openGroups.value.has(group.label) || group.items.some((item) => isActive(item.path))
}

function visibleItems(group) {
  return isGroupOpen(group) ? group.items : []
}

function toggleGroup(group) {
  const next = new Set(openGroups.value)
  if (isGroupOpen(group)) next.delete(group.label)
  else next.add(group.label)
  openGroups.value = next
  try {
    localStorage.setItem('xt-nav-open-groups', JSON.stringify([...next]))
  } catch {
    // 浏览器禁止本地存储时只在本次会话记住
  }
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
    scope: buildAssistantScope(route, detail.scope),
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

function closeDrawerAfterNavigation() {
  window.setTimeout(() => {
    drawerOpen.value = false
  }, 0)
}

function closeSearchAfterNavigation() {
  window.setTimeout(() => {
    searchOpen.value = false
  }, 0)
}

watch(() => route.path, () => {
  drawerOpen.value = false
  searchOpen.value = false
  assistantOpen.value = false
  keyword.value = ''
})

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
  --manage-sidebar-expanded: 184px;
  --manage-sidebar-rail: 64px;
  min-height: 100dvh;
  background: var(--xt-bg-page);
  color: var(--xt-text);
  font-family: var(--el-font-family);
  letter-spacing: 0;
}
.xt-manage__sidebar {
  position: fixed;
  inset: 0 auto 0 0;
  z-index: 20;
  width: var(--manage-sidebar-expanded);
  display: flex;
  flex-direction: column;
  background: var(--xt-bg-page);
  border-right: 1px solid var(--xt-border);
}
.xt-manage__brand, .xt-manage__drawer-brand {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 64px;
  padding: 0 20px;
  color: var(--xt-text);
}
.xt-manage__brand :deep(.xt-logo__en) { display: none; }
.xt-manage__brand-text { color: var(--xt-text-secondary); font-size: 14px; white-space: nowrap; }
.xt-manage__nav { flex: 1; overflow-y: auto; overflow-x: hidden; padding: 16px 12px; }
.xt-manage__nav-group { margin-bottom: 20px; }
.xt-manage__nav-group-label { padding: 0 12px 8px; color: var(--xt-text-muted); font-size: 12px; }
.xt-manage__nav-group-toggle { display: flex; align-items: center; justify-content: space-between; width: 100%; min-height: 32px; border: 0; border-radius: 4px; background: none; font: inherit; font-size: 12px; cursor: pointer; }
.xt-manage__nav-group-toggle:hover { color: var(--xt-text); }
.xt-manage__nav-group-toggle:focus-visible { outline: 2px solid var(--xt-primary); outline-offset: 2px; }
.xt-manage--collapsed .xt-manage__nav-group + .xt-manage__nav-group { padding-top: 12px; border-top: 1px solid var(--xt-border); }
.xt-manage__nav-item {
  display: flex;
  align-items: center;
  gap: 11px;
  min-height: 44px;
  margin-bottom: 4px;
  padding: 10px 12px;
  border-radius: 4px;
  color: var(--xt-text-secondary);
  font-size: 14px;
  text-decoration: none;
  line-height: 1.4;
}
.xt-manage__nav-item .el-icon { flex-shrink: 0; font-size: 17px; }
.xt-manage__nav-item:hover { background: var(--xt-bg-panel-soft); color: var(--xt-text); }
.xt-manage__nav-item.is-active { background: var(--xt-primary-light); color: var(--xt-primary); font-weight: 600; }
.xt-manage__nav-label { display: flex; flex-direction: column; min-width: 0; }
.xt-manage__nav-label small { font-size: 12px; font-weight: 400; color: var(--xt-text-muted); }
.xt-manage__collapse-btn {
  display: grid;
  place-items: center;
  width: 36px;
  height: 36px;
  margin: 12px;
  border: 1px solid var(--xt-border);
  border-radius: 4px;
  background: transparent;
  color: var(--xt-text-secondary);
  cursor: pointer;
}
.xt-manage__main { min-width: 0; min-height: 100dvh; margin-left: var(--manage-sidebar-expanded); }
.xt-manage--collapsed .xt-manage__sidebar { width: var(--manage-sidebar-rail); }
.xt-manage--collapsed .xt-manage__main { margin-left: var(--manage-sidebar-rail); }
.xt-manage--collapsed .xt-manage__brand { justify-content: center; padding: 0; }
.xt-manage--collapsed .xt-manage__nav-item { justify-content: center; padding: 12px; }
.xt-manage--collapsed .xt-manage__nav-group-label,
.xt-manage--collapsed .xt-manage__nav-label,
.xt-manage--collapsed .xt-manage__brand-text { display: none; }
.xt-manage--auto-rail .xt-manage__sidebar:is(:hover, :focus-within) { width: var(--manage-sidebar-expanded); box-shadow: var(--xt-shadow-md); }
.xt-manage--auto-rail .xt-manage__sidebar:is(:hover, :focus-within) .xt-manage__nav-group-label,
.xt-manage--auto-rail .xt-manage__sidebar:is(:hover, :focus-within) .xt-manage__nav-label,
.xt-manage--auto-rail .xt-manage__sidebar:is(:hover, :focus-within) .xt-manage__brand-text { display: block; }
.xt-manage--auto-rail .xt-manage__sidebar:is(:hover, :focus-within) .xt-manage__nav-item { justify-content: flex-start; }
.xt-manage__topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  height: 64px;
  padding: 0 40px;
  border-bottom: 1px solid var(--xt-border);
  background: var(--xt-bg-page);
}
.xt-manage__topbar-right { display: flex; align-items: center; gap: 12px; }
.xt-manage__topbar button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 34px;
  padding: 0 10px;
  border: 1px solid transparent;
  border-radius: 4px;
  background: transparent;
  color: var(--xt-text-secondary);
  cursor: pointer;
  font: inherit;
  font-size: 14px;
}
.xt-manage__topbar button:hover { background: var(--xt-bg-panel-soft); }
.xt-manage__search-trigger kbd { margin-left: 36px; padding: 1px 5px; border: 1px solid var(--xt-border); border-radius: 4px; color: var(--xt-text-muted); font-size: 12px; }
.xt-manage__topbar .xt-manage__assistant-trigger { color: var(--xt-primary); }
.xt-manage__user :deep(.el-avatar) { background: var(--xt-primary-light); color: var(--xt-primary); font-size: 12px; }
.xt-manage__topbar .xt-manage__hamburger { display: none; width: 36px; padding: 0; }
.xt-manage__content { padding: 40px; background: var(--xt-bg-page); }
.xt-manage__content::before, .xt-manage__content::after { content: none; }
.xt-manage__container { max-width: 1440px; margin: 0 auto; min-width: 0; }
.xt-manage__drawer-overlay { position: fixed; inset: 0; z-index: 2200; background: #171b244d; }
.xt-manage__drawer { height: 100dvh; max-width: 88vw; overflow-y: auto; background: var(--xt-bg-page); box-shadow: var(--xt-shadow-md); }
.xt-manage__drawer-head { display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--xt-border); }
.xt-manage__drawer-close { display: grid; place-items: center; width: 36px; height: 36px; margin-right: 12px; background: transparent; border: 0; color: var(--xt-text-secondary); cursor: pointer; }
.xt-manage__drawer-nav { padding: 18px 12px; }
.xt-manage__drawer-nav .xt-manage__nav-label { display: flex; }
.xt-manage__drawer-nav .xt-manage__nav-group-label { display: block; margin-top: 12px; }
.xt-manage__search-list { display: grid; gap: 4px; padding-top: 12px; max-height: 60vh; overflow-y: auto; }
.xt-manage__search-item { display: flex; justify-content: space-between; gap: 12px; padding: 12px; color: var(--xt-text); border-radius: 4px; text-decoration: none; }
.xt-manage__search-item:hover { background: var(--xt-bg-panel-soft); }
.xt-manage__search-item small { color: var(--xt-text-muted); }
button:focus-visible, a:focus-visible { outline: 2px solid var(--xt-primary); outline-offset: 3px; }
@media (max-width: 900px) {
  .xt-manage__sidebar { display: none; }
  .xt-manage__main, .xt-manage--collapsed .xt-manage__main { margin-left: 0; }
  .xt-manage__topbar { padding: 0 16px; }
  .xt-manage__topbar .xt-manage__hamburger { display: inline-flex; }
  .xt-manage__search-trigger { margin-right: auto; }
  .xt-manage__content { padding: 24px 20px; }
}
@media (max-width: 640px) {
  .xt-manage__topbar { padding: 0 12px; gap: 4px; }
  .xt-manage__topbar-right { gap: 4px; }
  .xt-manage__search-trigger kbd, .xt-manage__assistant-trigger span, .xt-manage__user > span { display: none; }
  .xt-manage__content { padding: 20px 14px; }
}
@media print {
  .xt-manage__sidebar, .xt-manage__topbar, .xt-manage__drawer-overlay { display: none; }
  .xt-manage__main, .xt-manage--collapsed .xt-manage__main { min-height: auto; margin-left: 0; }
  .xt-manage__content { padding: 0; }
}
</style>
