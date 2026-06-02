<template>
  <div class="login-page">
    <LoginHudBackdrop
      class="login-page__backdrop"
      data-testid="login-hud-backdrop"
    />
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

      </div>

      <div class="login-card panel">
        <div class="login-card__head">
          <span>管理端</span>
          <strong>管理员登录</strong>
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
          v-if="loginError"
          :title="loginError"
          type="error"
          show-icon
          :closable="false"
          class="panel"
          data-testid="login-error"
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
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, defineAsyncComponent, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { XtFactoryMap, XtLogo } from '../components/xt'
import { useAuthStore } from '../stores/auth.js'
import { useHudTheme } from '../composables/useHudTheme.js'

useHudTheme({ force: true })
const LoginHudBackdrop = defineAsyncComponent(() => import('../components/hud/ParticleField.vue'))

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const formRef = ref()
const loading = ref(false)
const qrLoginPending = ref(false)
const dingtalkLoginPending = ref(false)
const loginError = ref('')

const form = reactive({
  username: '',
  password: ''
})

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

function isDingTalkRuntime() {
  if (typeof window === 'undefined') return false
  const userAgent = window.navigator?.userAgent || ''
  return Boolean(window.dd) || /DingTalk/i.test(userAgent)
}

function resolveDefaultLandingPath() {
  if (auth.adminSurface) return '/admin'
  if (auth.isWorkshopDirector) return '/manage/workshop-dashboard'
  return auth.reviewSurface ? '/manage/today' : '/login'
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

function resolveLoginError(error) {
  if (!error?.response) return '登录服务连接失败'
  if (error.response.status === 429) return '尝试次数过多，请稍后再试'
  if (error.response.status === 403) return '账号已停用'
  if (error.response.status === 400 || error.response.status === 401) return '账号或密码不正确'
  return '登录失败，请稍后再试'
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  loginError.value = ''
  try {
    await auth.login({ username: form.username, password: form.password })
    if (!auth.canAccessDesktop) {
      auth.logout()
      loginError.value = '当前账号不能进入管理端'
      ElMessage.error(loginError.value)
      return
    }
    ElMessage.success('登录成功')
    router.push(resolveRedirectPath())
  } catch (error) {
    loginError.value = resolveLoginError(error)
    ElMessage.error(loginError.value)
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
    ElMessage.success('扫码登录成功')
    await router.replace({ name: 'mobile-entry' })
  } catch {
    // error toast is handled by axios interceptor
  } finally {
    qrLoginPending.value = false
  }
}

onMounted(async () => {
  if (isDingTalkRuntime() && !resolveAuthCode()) {
    await router.replace({ name: 'mobile-entry', query: route.query })
    return
  }
  const dingtalkLoggedIn = await tryDingtalkLogin()
  if (dingtalkLoggedIn) return
  await tryQrLogin()
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
.login-card__head span {
  font-size: 12px;
  letter-spacing: 0;
  color: var(--xt-hud-text-muted, var(--app-muted));
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
  color: var(--xt-hud-text, var(--app-text));
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
}

.login-page__backdrop {
  position: absolute;
  inset: 0;
  z-index: 0;
  pointer-events: none;
}

.login-page {
  position: relative;
}
</style>
