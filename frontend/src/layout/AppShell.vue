<template>
  <el-container class="app-shell" :class="{ 'is-nav-open': navOpen }" :data-testid="shellTestId" :data-zone="props.zone">
    <el-aside id="app-shell-navigation" class="app-shell__aside" width="252px" :aria-label="`${zoneLabel}导航`">
      <div class="app-shell__brand">
        <div class="app-shell__brand-mark" :data-testid="props.zone === 'review' ? 'review-brand-mark' : undefined">
          <XtLogo variant="icon" />
        </div>
        <div>
          <p class="app-shell__brand-title" :data-testid="props.zone === 'review' ? 'review-brand-title' : undefined">鑫泰铝业 数据中枢</p>
          <p class="app-shell__brand-subtitle">{{ zoneLabel }}</p>
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
    <button v-if="navOpen" type="button" class="app-shell__scrim" aria-label="关闭导航" @click="navOpen = false" />

    <el-container>
      <el-header class="app-shell__topbar">
        <div class="app-shell__topbar-start">
          <el-button
            class="app-shell__menu-button"
            plain
            aria-controls="app-shell-navigation"
            :aria-expanded="navOpen ? 'true' : 'false'"
            @click="navOpen = !navOpen"
          >
            导航
          </el-button>
          <div>
            <div class="app-shell__meta">{{ currentMeta.group || zoneLabel }}</div>
            <h1 class="app-shell__title">{{ currentMeta.title || '系统中心' }}</h1>
          </div>
        </div>
        <div class="topbar-actions">
          <span class="topbar-user">{{ auth.displayName }}</span>
          <el-button v-if="showEntrySwitch" plain @click="goEntry">录入端</el-button>
          <el-button v-if="showReviewSwitch" plain @click="goReview">审阅端</el-button>
          <el-button v-if="showAdminSwitch" plain @click="goAdmin">管理端</el-button>
          <el-button v-if="showAssistant" type="primary" plain @click="assistantDrawerOpen = true">AI 助手</el-button>
          <el-button type="danger" plain @click="logout">退出</el-button>
        </div>
      </el-header>
      <el-main class="app-shell__main">
        <div class="app-shell__container">
          <slot />
        </div>
      </el-main>
    </el-container>

    <AiAssistantDrawer v-model="assistantDrawerOpen" :context="assistantContext" />
  </el-container>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'

import AiAssistantDrawer from '../components/ai/AiAssistantDrawer.vue'
import { XtLogo } from '../components/xt'
import { buildShellNavigation } from '../config/navigation'
import { useAuthStore } from '../stores/auth'

const props = defineProps({
  zone: {
    type: String,
    default: 'review'
  }
})

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const assistantDrawerOpen = ref(false)
const navOpen = ref(false)

const zoneLabel = computed(() => {
  if (props.zone === 'admin') return '管理控制台'
  if (props.zone === 'desktop') return '兼容配置台'
  return '审阅指挥台'
})
const shellTestId = computed(() => {
  if (props.zone === 'review') return 'review-shell'
  if (props.zone === 'admin') return 'admin-shell'
  return 'app-shell'
})
const navGroups = computed(() => buildShellNavigation(props.zone, auth))
const activeMenuIndex = computed(() => String(route.name || ''))
const currentMeta = computed(() => route.meta || {})
const showEntrySwitch = computed(() => props.zone !== 'entry' && auth.entrySurface && auth.superAdminSurface)
const showReviewSwitch = computed(() => props.zone !== 'review' && auth.reviewSurface)
const showAdminSwitch = computed(() => props.zone !== 'admin' && auth.isAdmin)
const showAssistant = computed(() => props.zone === 'review' && auth.reviewSurface)
const assistantContext = computed(() => ({
  route: route.path,
  scope: {
    type: 'route',
    key: route.path || '/manage/today'
  }
}))

function handleSelect(routeName) {
  if (!routeName) return
  navOpen.value = false
  if (routeName === route.name) return
  router.push({ name: routeName })
}

function goEntry() {
  navOpen.value = false
  router.push({ name: 'mobile-entry' })
}

function goReview() {
  navOpen.value = false
  router.push({ name: 'manage-today' })
}

function goAdmin() {
  navOpen.value = false
  router.push({ name: 'admin-ops-reliability' })
}

async function logout() {
  await ElMessageBox.confirm('确认退出当前账号吗？', '提示', { type: 'warning' })
  auth.logout()
  router.push({ name: 'login' })
}

watch(() => route.fullPath, () => {
  navOpen.value = false
})
</script>
