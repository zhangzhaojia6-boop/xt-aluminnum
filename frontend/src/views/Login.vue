<template>
  <div class="login-page">
    <section class="login-stage" data-testid="login-page">
      <div class="login-stage__hero">
        <div class="login-brand" data-testid="login-brand">
          <XtLogo variant="full" />
          <span class="login-brand__tag">数据中枢</span>
        </div>

        <div class="login-stage__headline">
          <span v-if="false">02 登录与角色入口</span>
          <span class="login-stage__eyebrow">全厂作战地图</span>
          <h2>鑫泰铝业 数据中枢</h2>
        </div>

        <XtFactoryMap
          class="login-stage__map"
          compact
          :nodes="loginMapNodes"
          :lines="loginMapLines"
          :alerts="loginMapAlerts"
          active-key="ai"
        />

        <div class="login-stage__role-grid">
          <button
            v-for="option in surfaceOptions"
            :key="option.value"
            type="button"
            :class="['login-stage__role-card', { 'is-accent': selectedSurface === option.value }]"
            :data-testid="`login-surface-${option.value}`"
            :aria-pressed="selectedSurface === option.value"
            @click="selectedSurface = option.value"
          >
            <div class="login-stage__role-top">
              <span>{{ option.label }}</span>
              <em>{{ option.badge }}</em>
            </div>
            <strong>{{ option.title }}</strong>
          </button>
        </div>
      </div>

      <div class="login-card panel">
        <div class="login-card__head">
          <span>审阅端 / 管理端</span>
          <strong>账号登录</strong>
        </div>

        <el-alert
          v-if="dingtalkLoginPending"
          title="正在识别钉钉身份"
          type="success"
          show-icon
          :closable="false"
          class="panel"
        />

        <el-alert
          v-else-if="hasRuntimeCode"
          title="已收到钉钉授权码"
          type="info"
          show-icon
          :closable="false"
          class="panel"
        />

        <el-alert
          v-if="qrLoginPending"
          title="正在识别机台"
          type="info"
          show-icon
          :closable="false"
          class="panel"
        />

        <el-alert
          v-if="workshopHint"
          :title="workshopHint"
          type="info"
          show-icon
          :closable="false"
          class="panel"
        />

        <el-form ref="formRef" :model="form" :rules="rules" class="login-card__form" @submit.prevent="submit">
          <el-form-item prop="username">
            <el-input
              v-model="form.username"
              data-testid="login-username"
              placeholder="账号"
              size="large"
              autocomplete="username"
            />
          </el-form-item>
          <el-form-item prop="password">
            <el-input
              v-model="form.password"
              data-testid="login-password"
              type="password"
              placeholder="密码"
              size="large"
              show-password
              autocomplete="current-password"
            />
          </el-form-item>
          <el-button
            data-testid="login-submit"
            type="primary"
            size="large"
            :loading="loading"
            :disabled="qrLoginPending || dingtalkLoginPending"
            native-type="submit"
            style="width: 100%"
          >
            进入系统
          </el-button>
        </el-form>

        <div class="login-card__foot">
          <span>录入端走钉钉</span>
          <span>审阅端</span>
          <span>管理端</span>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { XtFactoryMap, XtLogo } from '../components/xt'
import { useAuthStore } from '../stores/auth.js'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const formRef = ref()
const loading = ref(false)
const qrLoginPending = ref(false)
const dingtalkLoginPending = ref(false)
const workshopHint = ref('')
const selectedSurface = ref('review')

const form = reactive({
  username: '',
  password: ''
})

const surfaceOptions = [
  { value: 'entry', label: '录入端', badge: '钉钉', title: '现场填报' },
  { value: 'review', label: '审阅端', badge: '桌面', title: '生产审阅' },
  { value: 'admin', label: '管理端', badge: '桌面', title: '系统配置' }
]

const loginMapNodes = [
  { key: 'furnace', label: '熔铸炉', short: '炉', status: 'normal', x: '15%', y: '24%' },
  { key: 'casting', label: '铸锭线', short: '铸', status: 'normal', x: '55%', y: '40%' },
  { key: 'batch', label: '批次链', short: '批', status: 'warning', x: '31%', y: '70%' },
  { key: 'ai', label: 'AI 总管', short: 'AI', status: 'normal', x: '78%', y: '66%' }
]

const loginMapLines = [
  { key: 'entry', label: '岗位直录', value: '在线', status: 'normal' },
  { key: 'validation', label: '自动校验', value: '运行', status: 'normal' },
  { key: 'publish', label: '日报发布', value: '待命', status: 'warning' }
]

const loginMapAlerts = [
  { key: 'loop', label: '闭环', value: '发现 → 判断 → 执行', status: 'warning' }
]

const rules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const hasRuntimeCode = computed(() => Boolean(resolveAuthCode()))

function resolveQueryValue(key) {
  if (typeof route.query[key] === 'string' && route.query[key]) {
    return route.query[key]
  }

  if (typeof route.query.redirect === 'string' && route.query.redirect) {
    try {
      const parsed = new URL(route.query.redirect, window.location.origin)
      return parsed.searchParams.get(key) || ''
    } catch {
      return ''
    }
  }

  return ''
}

function resolveAuthCode() {
  return resolveQueryValue('authCode') || resolveQueryValue('auth_code') || resolveQueryValue('code')
}

function surfaceLandingPath(surface) {
  if (surface === 'entry' && auth.entrySurface) return '/entry'
  if (surface === 'review' && auth.reviewSurface) return '/manage/overview'
  if (surface === 'admin' && auth.adminSurface) return '/admin'
  return ''
}

function resolveDefaultLandingPath() {
  const selectedLanding = surfaceLandingPath(selectedSurface.value)
  if (selectedLanding) return selectedLanding
  if (auth.defaultSurface === 'entry') return '/entry'
  if (auth.defaultSurface === 'admin') return '/admin'
  if (auth.defaultSurface === 'review') return '/manage/overview'
  return auth.canAccessDesktop ? '/manage/overview' : '/entry'
}

function resolveRedirectPath() {
  const fallback = resolveDefaultLandingPath()
  if (!(typeof route.query.redirect === 'string' && route.query.redirect)) {
    return fallback
  }

  try {
    const parsed = new URL(route.query.redirect, window.location.origin)
    parsed.searchParams.delete('code')
    parsed.searchParams.delete('state')
    parsed.searchParams.delete('authCode')
    parsed.searchParams.delete('auth_code')
    const cleanPath = `${parsed.pathname}${parsed.search}${parsed.hash}`
    return cleanPath || fallback
  } catch {
    return fallback
  }
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    await auth.login({ username: form.username, password: form.password })
    ElMessage.success('登录成功')
    router.push(resolveRedirectPath())
  } finally {
    loading.value = false
  }
}

async function tryDingtalkLogin() {
  const code = resolveAuthCode()
  if (!code) return false

  dingtalkLoginPending.value = true
  try {
    await auth.dingtalkLogin(code)
    ElMessage.success('钉钉登录成功')
    await router.replace(resolveRedirectPath())
    return true
  } catch {
    return false
  } finally {
    dingtalkLoginPending.value = false
  }
}

async function tryQrLogin() {
  const qrCode = resolveQueryValue('machine')
  if (!qrCode) return

  qrLoginPending.value = true
  try {
    await auth.qrLogin(qrCode)
    ElMessage.success('机台登录成功')
    await router.replace({ name: 'mobile-entry' })
  } catch {
    // error toast is handled by axios interceptor
  } finally {
    qrLoginPending.value = false
  }
}

function applyWorkshopContext() {
  const wsCode = resolveQueryValue('workshop')
  if (!wsCode) return
  workshopHint.value = `车间：${wsCode}，请用该车间的角色账号登录`
}

onMounted(async () => {
  const dingtalkLoggedIn = await tryDingtalkLogin()
  if (dingtalkLoggedIn) return
  await tryQrLogin()
  applyWorkshopContext()
})
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  min-height: 100dvh;
  display: grid;
  place-items: center;
  padding: 32px;
  background: var(--xt-bg-shell);
}

.login-stage {
  width: min(1120px, 100%);
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(360px, 0.75fr);
  gap: 16px;
  align-items: stretch;
}

.login-stage__hero,
.login-card,
.login-stage__headline,
.login-stage__role-grid,
.login-card__head,
.login-card__form {
  display: grid;
  gap: 16px;
}

.login-stage__hero {
  position: relative;
  overflow: hidden;
  padding: 32px;
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-2xl);
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-md);
}

.login-brand {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--xt-space-4);
}

.login-brand__tag {
  display: inline-flex;
  align-items: center;
  min-height: 28px;
  padding: 0 var(--xt-space-3);
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-pill);
  background: var(--xt-bg-panel-soft);
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-xs);
  font-weight: 800;
}

.login-stage__eyebrow,
.login-card__head span,
.login-stage__role-top span {
  font-size: 12px;
  letter-spacing: 0;
  color: var(--app-muted);
}

.login-stage__headline h2 {
  margin: 0;
  color: var(--xt-text);
  font-family: var(--xt-font-display);
  font-size: 46px;
  font-weight: 900;
  line-height: 1.05;
  letter-spacing: 0;
}

.login-stage__map {
  position: relative;
  min-height: 260px;
  overflow: hidden;
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-2xl);
  background:
    linear-gradient(90deg, rgba(15, 23, 42, 0.035) 1px, transparent 1px),
    linear-gradient(rgba(15, 23, 42, 0.03) 1px, transparent 1px),
    var(--xt-bg-panel-soft);
  background-size: 28px 28px;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.86);
}

.login-stage__track {
  position: absolute;
  right: 9%;
  left: 9%;
  height: 18px;
  border-radius: var(--xt-radius-pill);
  background: rgba(11, 99, 246, 0.10);
  box-shadow: inset 0 0 0 1px rgba(11, 99, 246, 0.08);
}

.login-stage__track--top {
  top: 28%;
  transform: rotate(-5deg);
}

.login-stage__track--middle {
  top: 52%;
  transform: rotate(2deg);
}

.login-stage__track--bottom {
  top: 75%;
  transform: rotate(-2deg);
}

.login-stage__node {
  position: absolute;
  width: 58px;
  height: 58px;
  display: grid;
  place-items: center;
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-xl);
  background: var(--xt-bg-panel);
  color: var(--xt-primary);
  font-size: var(--xt-text-xl);
  font-weight: 900;
  box-shadow: var(--xt-shadow-md);
}

.login-stage__node.is-furnace {
  top: 19%;
  left: 12%;
  color: var(--xt-accent);
}

.login-stage__node.is-cast {
  top: 42%;
  right: 18%;
}

.login-stage__node.is-ingot {
  bottom: 11%;
  left: 29%;
}

.login-stage__ai {
  position: absolute;
  right: 20px;
  bottom: 18px;
  display: grid;
  gap: 4px;
  min-width: 180px;
  padding: var(--xt-space-3);
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-xl);
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-sm);
}

.login-stage__ai span {
  color: var(--xt-text-secondary);
  font-size: var(--xt-text-xs);
  font-weight: 800;
}

.login-stage__ai strong {
  color: var(--xt-text);
  font-size: var(--xt-text-sm);
}

.login-stage__role-grid {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.login-stage__role-card {
  display: grid;
  gap: 12px;
  min-height: 122px;
  padding: 16px;
  text-align: left;
  font: inherit;
  cursor: pointer;
  border-radius: var(--xt-radius-xl);
  background: var(--xt-bg-panel-soft);
  border: 1px solid var(--xt-border-light);
  box-shadow: var(--app-shadow-xs);
  transition:
    transform var(--app-motion-base) var(--app-motion-curve),
    background-color var(--app-motion-base) var(--app-motion-curve),
    border-color var(--app-motion-base) ease,
    color var(--app-motion-base) ease;
}

.login-stage__role-card:focus-visible {
  outline: 3px solid rgba(37, 99, 235, 0.22);
  outline-offset: 3px;
}

@media (hover: hover) {
  .login-stage__role-card:hover {
    transform: translateY(-2px);
    border-color: rgba(11, 99, 246, 0.22);
    background: #ffffff;
  }
}

.login-stage__role-card:active {
  transform: scale(0.98);
}

.login-stage__role-card.is-accent {
  border-color: rgba(11, 99, 246, 0.28);
  background: var(--xt-primary-light);
}

.login-stage__role-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.login-stage__role-top em {
  font-style: normal;
  font-size: 12px;
  font-weight: 600;
  color: var(--xt-primary);
  background: var(--xt-primary-soft);
  border: 1px solid rgba(11, 99, 246, 0.18);
  border-radius: 999px;
  min-height: 26px;
  padding: 0 10px;
  display: inline-flex;
  align-items: center;
}

.login-stage__role-card strong {
  font-size: 24px;
  line-height: 1.12;
  letter-spacing: 0;
  color: var(--app-text);
}

.login-card {
  align-content: start;
  padding: 28px;
  border-radius: var(--xt-radius-2xl);
  box-shadow: var(--xt-shadow-md);
}

.login-card :deep(.el-alert) {
  border-radius: 18px;
}

.login-card__head strong {
  font-size: 30px;
  line-height: 1;
  letter-spacing: 0;
  color: var(--app-text);
  font-family: var(--xt-font-display);
  font-weight: 900;
}

.login-card :deep(.el-input__wrapper) {
  min-height: 46px;
  border-radius: 12px;
}

.login-card :deep(.el-button) {
  border-radius: 12px;
}

.login-card__foot {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.login-card__foot span {
  display: inline-flex;
  align-items: center;
  min-height: 34px;
  padding: 0 12px;
  border-radius: 999px;
  background: rgba(15, 23, 42, 0.04);
  color: var(--app-muted);
  font-size: 13px;
  font-weight: 600;
}

@media (max-width: 980px) {
  .login-page {
    padding: 16px;
  }

  .login-stage {
    grid-template-columns: 1fr;
  }

  .login-stage__hero {
    padding: 24px;
  }

  .login-brand {
    align-items: flex-start;
    flex-direction: column;
  }

  .login-stage__headline h2 {
    font-size: 32px;
  }

  .login-stage__map {
    min-height: 220px;
  }

  .login-stage__role-grid {
    grid-template-columns: 1fr;
  }
}
</style>
