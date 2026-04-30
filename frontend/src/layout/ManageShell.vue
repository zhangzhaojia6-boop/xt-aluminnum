<template>
  <div class="xt-manage" :class="{ 'xt-manage--collapsed': collapsed }" data-testid="manage-shell">
    <aside class="xt-manage__sidebar">
      <RouterLink class="xt-manage__brand" to="/manage/overview" aria-label="鑫泰铝业数据中枢">
        <XtLogo :variant="collapsed ? 'icon' : 'full'" />
        <span v-if="!collapsed" class="xt-manage__brand-text">数据中枢</span>
      </RouterLink>

      <nav class="xt-manage__nav" aria-label="管理端导航">
        <section v-for="group in navGroups" :key="group.label" class="xt-manage__nav-group">
          <div v-if="!collapsed" class="xt-manage__nav-group-label">{{ group.label }}</div>
          <RouterLink
            v-for="item in group.items"
            :key="item.path"
            :to="item.path"
            class="xt-manage__nav-item"
            :class="{ 'is-active': isActive(item.path) }"
            :title="item.title"
          >
            <el-icon><component :is="item.icon" /></el-icon>
            <span v-if="!collapsed" class="xt-manage__nav-label">
              <span>{{ item.shortLabel || item.title }}</span>
              <small v-if="item.secondaryGroup">{{ item.secondaryGroup }}</small>
            </span>
          </RouterLink>
        </section>
      </nav>

      <button class="xt-manage__collapse-btn" type="button" aria-label="切换侧边栏" @click="toggleCollapse">
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

    <el-drawer v-model="drawerOpen" direction="ltr" size="280px" :with-header="false" class="xt-manage__drawer">
      <nav class="xt-manage__drawer-nav" aria-label="移动端管理导航">
        <template v-for="group in navGroups" :key="group.label">
          <div class="xt-manage__nav-group-label">{{ group.label }}</div>
          <RouterLink
            v-for="item in group.items"
            :key="item.path"
            :to="item.path"
            class="xt-manage__nav-item"
            :class="{ 'is-active': isActive(item.path) }"
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
          :to="item.path"
          class="xt-manage__search-item"
          @click="searchOpen = false"
        >
          <span>{{ item.shortLabel || item.title }}</span>
          <small>{{ item.group }}</small>
        </RouterLink>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { Expand, Fold, Menu, Search } from '@element-plus/icons-vue'

import { XtLogo } from '../components/xt'
import { manageNavGroups } from '../config/manage-navigation'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const collapsed = ref(localStorage.getItem('xt-sidebar-collapsed') === 'true')
const drawerOpen = ref(false)
const searchOpen = ref(false)
const keyword = ref('')

const userName = computed(() => auth.displayName || auth.user?.name || auth.user?.username || '用户')
const userInitial = computed(() => userName.value.slice(0, 1).toUpperCase())
const navGroups = computed(() => manageNavGroups(auth))
const searchItems = computed(() => navGroups.value.flatMap((group) => group.items.map((item) => ({ ...item, group: group.label }))))
const filteredSearchItems = computed(() => {
  const value = keyword.value.trim().toLowerCase()
  if (!value) return searchItems.value
  return searchItems.value.filter((item) => item.title.toLowerCase().includes(value) || item.path.toLowerCase().includes(value))
})

function isActive(path) {
  return route.path === path || route.path.startsWith(`${path}/`)
}

function toggleCollapse() {
  collapsed.value = !collapsed.value
  localStorage.setItem('xt-sidebar-collapsed', String(collapsed.value))
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

onMounted(() => window.addEventListener('keydown', handleKeydown))
onBeforeUnmount(() => window.removeEventListener('keydown', handleKeydown))
</script>

<style scoped>
.xt-manage {
  min-height: 100vh;
  min-height: 100dvh;
  background: var(--xt-bg-shell);
  color: var(--xt-text);
}

.xt-manage__sidebar {
  position: fixed;
  inset: 0 auto 0 0;
  z-index: 20;
  width: var(--xt-sidebar-width);
  display: flex;
  flex-direction: column;
  background: var(--xt-command-surface-strong);
  border-right: 1px solid var(--xt-border-light);
  box-shadow: 1px 0 0 var(--xt-border-light);
  transition: width var(--xt-motion-normal) var(--xt-ease);
}

.xt-manage--collapsed .xt-manage__sidebar {
  width: var(--xt-sidebar-collapsed);
}

.xt-manage__brand {
  min-height: calc(var(--xt-topbar-height) + 8px);
  display: flex;
  align-items: center;
  gap: var(--xt-space-2);
  padding: 0 var(--xt-space-4);
  border-bottom: 1px solid var(--xt-border-light);
  color: var(--xt-text);
  text-decoration: none;
}

.xt-manage__brand-text {
  margin-left: auto;
  padding: 3px var(--xt-space-2);
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-pill);
  background: var(--xt-bg-ink);
  color: rgba(255, 255, 255, 0.82);
  font-size: var(--xt-text-xs);
  font-weight: 700;
  letter-spacing: 0;
  white-space: nowrap;
}

.xt-manage__nav,
.xt-manage__drawer-nav {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--xt-space-3);
  padding: var(--xt-space-3);
  overflow-y: auto;
}

.xt-manage__nav-group {
  display: grid;
  gap: var(--xt-space-1);
}

.xt-manage__nav-group-label {
  padding: var(--xt-space-2) var(--xt-space-3) var(--xt-space-1);
  font-size: var(--xt-text-xs);
  color: var(--xt-text-muted);
  font-weight: 850;
}

.xt-manage__nav-item {
  min-height: 44px;
  display: flex;
  align-items: center;
  gap: var(--xt-space-2);
  padding: 0 var(--xt-space-3);
  border-radius: var(--xt-radius-md);
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-sm);
  font-weight: 600;
  text-decoration: none;
  transition:
    background-color var(--xt-motion-fast) var(--xt-ease),
    color var(--xt-motion-fast) var(--xt-ease),
    transform var(--xt-motion-fast) var(--xt-ease);
}

.xt-manage__nav-item:active {
  transform: scale(0.97);
}

@media (hover: hover) {
  .xt-manage__nav-item:hover {
    background: var(--xt-bg-panel-soft);
    color: var(--xt-text);
  }
}

.xt-manage__nav-item.is-active {
  background: var(--xt-primary-light);
  color: var(--xt-primary);
  font-weight: 700;
  box-shadow: inset 0 0 0 1px var(--xt-primary-border);
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
  color: var(--xt-text-muted);
  font-size: 10px;
  font-weight: 760;
}

.xt-manage--collapsed .xt-manage__nav-item {
  justify-content: center;
  padding: 0;
}

.xt-manage__collapse-btn,
.xt-manage__hamburger,
.xt-manage__search-trigger,
.xt-manage__user {
  border: 0;
  background: transparent;
  color: inherit;
  cursor: pointer;
  transition:
    background-color var(--xt-motion-fast) var(--xt-ease),
    color var(--xt-motion-fast) var(--xt-ease),
    transform var(--xt-motion-fast) var(--xt-ease);
}

.xt-manage__collapse-btn:active,
.xt-manage__hamburger:active,
.xt-manage__search-trigger:active,
.xt-manage__user:active {
  transform: scale(0.96);
}

.xt-manage__collapse-btn {
  height: 48px;
  border-top: 1px solid var(--xt-border-light);
  color: var(--xt-text-muted);
}

@media (hover: hover) {
  .xt-manage__collapse-btn:hover,
  .xt-manage__hamburger:hover,
  .xt-manage__search-trigger:hover,
  .xt-manage__user:hover {
    background: var(--xt-bg-panel-soft);
    color: var(--xt-text);
  }
}

.xt-manage__main {
  min-height: 100vh;
  margin-left: var(--xt-sidebar-width);
  transition: margin-left var(--xt-motion-normal) var(--xt-ease);
}

.xt-manage--collapsed .xt-manage__main {
  margin-left: var(--xt-sidebar-collapsed);
}

.xt-manage__topbar {
  position: sticky;
  top: 0;
  z-index: 10;
  height: var(--xt-topbar-height);
  display: flex;
  align-items: center;
  gap: var(--xt-space-3);
  padding: 0 var(--xt-space-5);
  background: color-mix(in srgb, var(--xt-bg-panel) 90%, var(--xt-bg-shell));
  border-bottom: 1px solid var(--xt-border-light);
  box-shadow: 0 1px 0 var(--xt-border-light);
}

.xt-manage__hamburger {
  display: none;
}

.xt-manage__search-trigger {
  min-width: 260px;
  height: 38px;
  display: flex;
  align-items: center;
  gap: var(--xt-space-2);
  padding: 0 var(--xt-space-3);
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-pill);
  color: var(--xt-text-muted);
  background: var(--xt-bg-panel-soft);
}

.xt-manage__search-trigger kbd {
  margin-left: auto;
  padding: 1px var(--xt-space-2);
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-pill);
  background: var(--xt-bg-panel);
  color: var(--xt-text-muted);
  font-family: var(--xt-font-mono);
  font-size: 11px;
  font-weight: 700;
  line-height: 1.5;
}

.xt-manage__topbar-right {
  margin-left: auto;
}

.xt-manage__user {
  display: flex;
  align-items: center;
  gap: var(--xt-space-2);
  min-height: 36px;
  padding: 0 var(--xt-space-2);
  border-radius: var(--xt-radius-pill);
  color: var(--xt-text-secondary);
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
  border-radius: var(--xt-radius-md);
  color: var(--xt-text);
  text-decoration: none;
  background: var(--xt-bg-panel-soft);
}

.xt-manage__search-item small {
  color: var(--xt-text-muted);
}

@media (max-width: 1180px) {
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

  .xt-manage__search-trigger {
    min-width: 0;
    width: min(320px, 100%);
  }

  .xt-manage__content {
    padding: var(--xt-space-4);
  }
}

@media (max-width: 767px) {
  .xt-manage__search-trigger kbd {
    display: none;
  }
}
</style>
