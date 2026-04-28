<template>
  <div class="cmd-page cmd-login" data-module="02" data-testid="login-page">
    <section class="cmd-login__stage">
      <div class="cmd-login__card">
        <div class="cmd-login__brand-block" data-testid="login-brand">
          <span v-html="commandLogoMark" />
          <strong>鑫泰铝业生产协同系统</strong>
        </div>
        <el-form ref="formRef" :model="form" :rules="rules" @submit.prevent="submit">
          <el-form-item prop="username">
            <el-input v-model="form.username" data-testid="login-username" placeholder="账号" size="large" autocomplete="username" />
          </el-form-item>
          <el-form-item prop="password">
            <el-input v-model="form.password" data-testid="login-password" type="password" placeholder="密码" size="large" show-password autocomplete="current-password" />
          </el-form-item>
          <el-button data-testid="login-submit" class="cmd-login__submit" type="primary" size="large" :loading="loading" native-type="submit">
            进入系统
          </el-button>
        </el-form>
        <div class="cmd-login__surface-list" aria-label="权限落点">
          <span>录入端</span>
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

import { useAuthStore } from '../../stores/auth.js'
import { commandLogoMark } from '../assets/logo.js'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const formRef = ref()
const loading = ref(false)
const qrLoginPending = ref(false)
const dingtalkLoginPending = ref(false)

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

function defaultLandingPath() {
  if (typeof route.query.redirect === 'string' && route.query.redirect) return route.query.redirect
  if (auth.defaultSurface === 'entry') return '/entry'
  if (auth.defaultSurface === 'admin') return '/admin'
  if (auth.defaultSurface === 'review') return '/review/overview'
  if (auth.reviewSurface) return '/review/overview'
  if (auth.entrySurface) return '/entry'
  return '/login'
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    await auth.login({ username: form.username, password: form.password })
    ElMessage.success('登录成功')
    await router.push(defaultLandingPath())
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
    await router.replace(defaultLandingPath())
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
    // The axios interceptor owns the visible error.
  } finally {
    qrLoginPending.value = false
  }
}

onMounted(async () => {
  const dingtalkLoggedIn = await tryDingtalkLogin()
  if (dingtalkLoggedIn) return
  await tryQrLogin()
})
</script>
