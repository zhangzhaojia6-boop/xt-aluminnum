<template>
  <el-container class="shell" data-testid="app-shell">
    <el-aside width="272px" class="side-panel">
      <div class="brand" data-testid="desktop-brand">
        <div class="brand-badge">鑫</div>
        <div>
          <div class="brand-title">鑫泰铝业</div>
          <div class="brand-subtitle">智能生产数据系统</div>
        </div>
      </div>
      <div class="brand-meta-strip">
        <span>Phase 1</span>
        <span>企业微信主入口</span>
        <span>智能体自动汇总</span>
      </div>

      <el-menu :default-active="route.path" router class="side-menu">
        <template v-if="auth.canAccessFactoryDashboard">
          <el-menu-item index="/dashboard/factory">
            <el-icon><DataBoard /></el-icon>
            <span>厂长驾驶舱</span>
          </el-menu-item>
        </template>

        <template v-if="auth.canAccessWorkshopDashboard">
          <el-menu-item index="/dashboard/workshop">
            <el-icon><Monitor /></el-icon>
            <span>车间主任看板</span>
          </el-menu-item>
        </template>

        <template v-if="auth.isAdmin || auth.isManager">
          <el-sub-menu index="master">
            <template #title>
              <el-icon><Setting /></el-icon>
              <span>主数据维护</span>
            </template>
            <el-menu-item index="/master/workshop">
              <el-icon><DataBoard /></el-icon>
              <span>车间管理</span>
            </el-menu-item>
            <el-menu-item v-if="auth.isAdmin" index="/master/users">
              <el-icon><UserIcon /></el-icon>
              <span>用户管理</span>
            </el-menu-item>
            <el-menu-item v-if="auth.isAdmin" index="/master/workshop-template">
              <el-icon><Document /></el-icon>
              <span>车间模板</span>
            </el-menu-item>
            <el-menu-item index="/master/equipment">
              <el-icon><Setting /></el-icon>
              <span>机台管理</span>
            </el-menu-item>
            <el-menu-item index="/master/shift-config">
              <el-icon><Clock /></el-icon>
              <span>班次配置</span>
            </el-menu-item>
          </el-sub-menu>
        </template>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="topbar">
        <div class="topbar-shell">
          <div>
            <div class="topbar-title">{{ route.meta.title || '后台管理' }}</div>
            <div class="topbar-subtitle">{{ roleSubtitle }}</div>
          </div>
          <div class="topbar-badges">
            <span v-for="badge in topbarBadges" :key="badge" class="topbar-badge">{{ badge }}</span>
          </div>
        </div>
        <div class="topbar-actions">
          <el-button v-if="auth.canAccessMobile" plain @click="goMobile">企业微信填报入口</el-button>
          <div class="topbar-user">{{ auth.displayName }}</div>
          <el-button type="danger" plain @click="logout">退出登录</el-button>
        </div>
      </el-header>
      <el-main class="main-area">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { ElMessageBox } from 'element-plus'
import {
  Clock,
  DataBoard,
  Document,
  Monitor,
  Setting,
  User as UserIcon,
} from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '../stores/auth'
import { formatRoleLabel, formatScopeLabel } from '../utils/display'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const roleSubtitle = computed(() => {
  const roleLabel = formatRoleLabel(auth.role)
  const scopeLabel = formatScopeLabel(auth.user?.data_scope_type)
  if (auth.isAdmin) return '管理端：配置岗位责任、班次模板和异常规则'
  if (auth.isManager) return `驾驶舱：${roleLabel}，聚焦智能体联动、趋势留存与异常闭环`
  if (auth.isMobileUser) return `填报端：${roleLabel}，岗位直录后由系统自动接力`
  return `${roleLabel} / ${scopeLabel}`
})

const topbarBadges = computed(() => {
  const badges = ['直录优先', '自动校验', '自动汇总']
  if (auth.canAccessManagerDashboard) badges.push('趋势留存')
  if (auth.isAdmin) badges.push('规则收口')
  return badges
})

onMounted(() => {
  if (auth.token && !auth.user) {
    auth.fetchProfile().catch(() => auth.logout())
  }
})

function goMobile() {
  router.push({ name: 'mobile-entry' })
}

async function logout() {
  await ElMessageBox.confirm('确认退出当前账号吗？', '提示', { type: 'warning' })
  auth.logout()
  router.push('/login')
}
</script>
