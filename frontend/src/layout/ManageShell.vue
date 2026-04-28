<template>
  <div class="xt-manage" :class="{ 'xt-manage--collapsed': collapsed }" data-testid="manage-shell">
    <aside class="xt-manage__sidebar">
      <RouterLink class="xt-manage__brand" to="/manage/overview" aria-label="鑫泰铝业管理控制台">
        <span class="xt-manage__brand-mark">鑫</span>
        <span v-if="!collapsed" class="xt-manage__brand-text">管理控制台</span>
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
            :title="collapsed ? item.title : undefined"
          >
            <el-icon><component :is="item.icon" /></el-icon>
            <span v-if="!collapsed" class="xt-manage__nav-label">{{ item.title }}</span>
          </RouterLink>
        </section>
      </nav>

      <button class="xt-manage__collapse-btn" type="button" @click="toggleCollapse">
        <el-icon><Fold v-if="!collapsed" /><Expand v-else /></el-icon>
      </button>
    </aside>

    <div class="xt-manage__main">
      <header class="xt-manage__topbar">
        <button class="xt-manage__hamburger" type="button" @click="drawerOpen = true">
          <el-icon><Menu /></el-icon>
        </button>
        <button class="xt-manage__search-trigger" type="button" @click="searchOpen = true">
          <el-icon><Search /></el-icon>
          <span>搜索</span>
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
            <span class="xt-manage__nav-label">{{ item.title }}</span>
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
          <span>{{ item.title }}</span>
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
  background: var(--xt-bg-page);
  color: var(--xt-text);
}

.xt-manage__sidebar {
  position: fixed;
  inset: 0 auto 0 0;
  z-index: 20;
  width: var(--xt-sidebar-width);
  display: flex;
  flex-direction: column;
  background: var(--xt-bg-panel);
  border-right: 1px solid var(--xt-border-light);
  transition: width var(--xt-motion-normal) var(--xt-ease);
}

.xt-manage--collapsed .xt-manage__sidebar {
  width: var(--xt-sidebar-collapsed);
}

.xt-manage__brand {
  height: var(--xt-topbar-height);
  display: flex;
  align-items: center;
  gap: var(--xt-space-3);
  padding: 0 var(--xt-space-4);
  color: var(--xt-text);
  text-decoration: none;
}

.xt-manage__brand-mark {
  width: 32px;
  height: 32px;
  flex: 0 0 32px;
  display: grid;
  place-items: center;
  border-radius: var(--xt-radius-lg);
  background: var(--xt-primary);
  color: var(--xt-text-inverse);
  font-weight: 800;
}

.xt-manage__brand-text {
  font-weight: 700;
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
  padding: var(--xt-space-2) var(--xt-space-3);
  font-size: var(--xt-text-xs);
  color: var(--xt-text-muted);
}

.xt-manage__nav-item {
  min-height: 40px;
  display: flex;
  align-items: center;
  gap: var(--xt-space-3);
  padding: 0 var(--xt-space-3);
  border-radius: var(--xt-radius-lg);
  color: var(--xt-text-secondary);
  text-decoration: none;
  transition: background var(--xt-motion-fast), color var(--xt-motion-fast);
}

.xt-manage__nav-item:hover,
.xt-manage__nav-item.is-active {
  background: var(--xt-primary-light);
  color: var(--xt-primary);
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
}

.xt-manage__collapse-btn {
  height: 44px;
  border-top: 1px solid var(--xt-border-light);
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
  background: color-mix(in srgb, var(--xt-bg-panel) 92%, transparent);
  border-bottom: 1px solid var(--xt-border-light);
  backdrop-filter: blur(12px);
}

.xt-manage__hamburger {
  display: none;
}

.xt-manage__search-trigger {
  min-width: 220px;
  height: 36px;
  display: flex;
  align-items: center;
  gap: var(--xt-space-2);
  padding: 0 var(--xt-space-3);
  border: 1px solid var(--xt-border);
  border-radius: var(--xt-radius-lg);
  color: var(--xt-text-muted);
  background: var(--xt-bg-panel-soft);
}

.xt-manage__topbar-right {
  margin-left: auto;
}

.xt-manage__user {
  display: flex;
  align-items: center;
  gap: var(--xt-space-2);
}

.xt-manage__content {
  padding: var(--xt-space-6);
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
  border-radius: var(--xt-radius-lg);
  color: var(--xt-text);
  text-decoration: none;
  background: var(--xt-bg-panel-soft);
}

.xt-manage__search-item small {
  color: var(--xt-text-muted);
}

@media (max-width: 1023px) {
  .xt-manage__sidebar {
    width: var(--xt-sidebar-collapsed);
  }

  .xt-manage__main,
  .xt-manage--collapsed .xt-manage__main {
    margin-left: var(--xt-sidebar-collapsed);
  }

  .xt-manage__nav-label,
  .xt-manage__nav-group-label,
  .xt-manage__brand-text {
    display: none;
  }

  .xt-manage__nav-item {
    justify-content: center;
    padding: 0;
  }
}

@media (max-width: 767px) {
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
  }

  .xt-manage__content {
    padding: var(--xt-space-4);
  }
}
</style>
