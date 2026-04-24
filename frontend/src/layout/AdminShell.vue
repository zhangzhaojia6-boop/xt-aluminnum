<template>
  <el-container class="app-shell app-shell--admin" data-testid="admin-shell">
    <el-aside class="app-shell__aside" width="252px">
      <div class="app-shell__brand">
        <div class="app-shell__brand-mark">鑫</div>
        <div>
          <p class="app-shell__brand-title">鑫泰铝业协同平台</p>
          <p class="app-shell__brand-subtitle">管理控制台</p>
        </div>
      </div>

      <div v-for="group in navGroups" :key="group.key" class="app-nav-group">
        <div class="app-nav-group__title">{{ group.label }}</div>
        <el-menu :default-active="activeMenuIndex" class="side-menu" @select="handleSelect">
          <el-menu-item v-for="item in group.items" :key="item.routeName" :index="item.routeName">
            <span>{{ item.label }}</span>
          </el-menu-item>
        </el-menu>
      </div>
    </el-aside>

    <el-container>
      <el-header class="app-shell__topbar">
        <div>
          <div class="app-shell__meta">{{ currentMeta.group || '管理控制台' }}</div>
          <h1 class="app-shell__title">{{ currentMeta.title || '管理控制台' }}</h1>
        </div>
        <div class="topbar-actions">
          <span class="topbar-user">{{ auth.displayName }}</span>
          <el-button v-if="auth.entrySurface && auth.superAdminSurface" plain @click="goEntry">录入端</el-button>
          <el-button v-if="auth.reviewSurface" plain @click="goReview">审阅端</el-button>
          <el-button type="danger" plain @click="logout">退出</el-button>
        </div>
      </el-header>
      <el-main class="app-shell__main">
        <div class="app-shell__container">
          <router-view />
        </div>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import { buildShellNavigation } from '../config/navigation'
import { useAuthStore } from '../stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const navGroups = computed(() => buildShellNavigation('admin', auth))
const activeMenuIndex = computed(() => String(route.name || ''))
const currentMeta = computed(() => route.meta || {})

function handleSelect(routeName) {
  if (!routeName || routeName === route.name) return
  router.push({ name: routeName })
}

function goEntry() {
  router.push({ name: 'mobile-entry' })
}

function goReview() {
  router.push({ name: 'review-overview-home' })
}

async function logout() {
  await ElMessageBox.confirm('确认退出当前账号吗？', '提示', { type: 'warning' })
  auth.logout()
  router.push({ name: 'login' })
}
</script>
