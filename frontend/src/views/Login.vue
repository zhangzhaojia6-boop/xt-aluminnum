<template>
  <div class="login-page">
    <header class="login-top" data-testid="login-brand">
      <XtLogo variant="icon" aria-hidden="true" />
      <span>鑫泰铝业</span>
    </header>

    <main class="login-stage" data-testid="login-page">
      <h1 class="login-stage__title">数据中枢</h1>

      <div class="login-form">
        <h2>管理员登录</h2>

        <el-alert
          v-if="dingtalkLoginPending"
          title="正在识别钉钉身份"
          type="success"
          show-icon
          :closable="false"
        />

        <el-alert
          v-else-if="hasRuntimeCode"
          title="已收到钉钉授权码"
          type="info"
          show-icon
          :closable="false"
        />

        <el-alert
          v-if="qrLoginPending"
          title="正在识别扫码入口"
          type="info"
          show-icon
          :closable="false"
        />

        <el-alert
          v-if="workshopNotice"
          :title="workshopNotice"
          type="info"
          show-icon
          :closable="false"
          data-testid="login-workshop-notice"
        />

        <el-alert
          v-if="loginError"
          :title="loginError"
          type="error"
          show-icon
          :closable="false"
          data-testid="login-error"
        />

        <el-form ref="formRef" :model="form" :rules="rules" label-position="top" hide-required-asterisk @submit.prevent="submit">
          <el-form-item label="账号" prop="username">
            <el-input
              v-model="form.username"
              data-testid="login-username"
              size="large"
              autocomplete="username"
            />
          </el-form-item>
          <el-form-item label="密码" prop="password">
            <el-input
              v-model="form.password"
              data-testid="login-password"
              type="password"
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
            class="login-form__submit"
          >
            进入系统
          </el-button>
        </el-form>
      </div>
    </main>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { XtLogo } from '../components/xt'
import { formatApiErrorMessage } from '../api/index.js'
import { useAuthStore } from '../stores/auth.js'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const formRef = ref()
const loading = ref(false)
const qrLoginPending = ref(false)
const dingtalkLoginPending = ref(false)
const loginError = ref('')
const workshopNotice = ref('')

const form = reactive({
  username: '',
  password: ''
})

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
  if (!error?.response) return formatApiErrorMessage(error)
  if (error.response.status === 429) return '尝试次数过多，请稍后再试'
  if (error.response.status === 403) return '账号已停用'
  if (error.response.status === 400 || error.response.status === 401) return '账号或密码不正确'
  return formatApiErrorMessage(error)
}

function setWorkshopNotice(workshopNameOrCode) {
  const value = String(workshopNameOrCode || '').trim()
  workshopNotice.value = value ? `车间：${value}，请用该车间的角色账号登录` : ''
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  loginError.value = ''
  workshopNotice.value = ''
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
  if (!qrCode) return false

  qrLoginPending.value = true
  workshopNotice.value = ''
  try {
    const result = await auth.qrLogin(qrCode)
    if (result?.type === 'workshop_redirect') {
      setWorkshopNotice(result.workshop_name || result.workshop_code)
      return true
    }
    ElMessage.success('扫码登录成功')
    await router.replace(auth.isWorkshopDirector ? { name: 'manage-workshop-dashboard' } : { name: 'mobile-entry' })
    return true
  } catch {
    // error toast is handled by axios interceptor
    return true
  } finally {
    qrLoginPending.value = false
  }
}

onMounted(async () => {
  const qrHandled = await tryQrLogin()
  if (qrHandled) return

  if (isDingTalkRuntime() && !resolveAuthCode()) {
    await router.replace({ name: 'mobile-entry', query: route.query })
    return
  }
  const dingtalkLoggedIn = await tryDingtalkLogin()
  if (dingtalkLoggedIn) return
  if (!resolveQueryValue('machine')) {
    setWorkshopNotice(resolveQueryValue('workshop'))
  }
})
</script>

<style scoped>
.login-page {
  display: grid;
  grid-template-rows: auto 1fr;
  min-height: 100vh;
  min-height: 100dvh;
  padding: 32px 64px 64px;
  background: var(--xt-bg-page);
  color: var(--xt-text);
}

.login-top {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
  color: var(--xt-text-secondary);
}

.login-stage {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: 64px;
  align-items: center;
  width: min(1080px, 100%);
  margin: 0 auto;
}

.login-stage__title {
  margin: 0;
  color: var(--xt-primary);
  font-size: 72px;
  font-weight: 600;
  line-height: 1.1;
  letter-spacing: 0.02em;
}

.login-form {
  display: grid;
  gap: 24px;
  padding-left: 64px;
  border-left: 1px solid var(--xt-border);
  box-sizing: content-box;
}

.login-form h2 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.login-form__submit {
  width: 100%;
  margin-top: 8px;
}

.login-form :deep(.el-form-item) {
  margin-bottom: 20px;
}

.login-form :deep(.el-form-item__label) {
  color: var(--xt-text-secondary);
  font-size: 14px;
}

.login-form :deep(.el-input__wrapper) {
  min-height: 44px;
  border-radius: 4px;
  box-shadow: 0 0 0 1px var(--xt-border) inset;
}

.login-form :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px var(--xt-primary) inset;
}

.login-form :deep(.el-button) {
  min-height: 44px;
  border-radius: 4px;
  box-shadow: none;
}

.login-form :deep(.el-alert) {
  border-radius: 4px;
}

@media (max-width: 860px) {
  .login-page {
    padding: 20px 20px 40px;
  }

  .login-stage {
    grid-template-columns: minmax(0, 1fr);
    gap: 40px;
    align-content: center;
  }

  .login-stage__title {
    font-size: 48px;
  }

  .login-form {
    padding-left: 0;
    border-left: 0;
  }
}
</style>
