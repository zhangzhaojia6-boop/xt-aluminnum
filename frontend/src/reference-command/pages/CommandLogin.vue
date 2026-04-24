<template>
  <div class="cmd-page cmd-login" data-module="02" data-testid="login-page">
    <section class="cmd-login-reference">
      <img class="cmd-login-reference__visual" :src="loginRoleHandoffImage" alt="" />
      <div class="cmd-login__functional">
        <div class="cmd-module-page__title cmd-login__functional-title">
          <span class="cmd-login__number">02</span>
          <h1>登录与角色入口</h1>
        </div>
        <div class="cmd-login__roles" aria-label="角色入口">
          <button
            v-for="option in surfaceOptions"
            :key="option.value"
            type="button"
            :class="['cmd-login__role', { 'is-active': selectedSurface === option.value }]"
            :data-testid="`login-surface-${option.value}`"
            @click="selectedSurface = option.value"
          >
            <strong>{{ option.label }}</strong>
            <span>{{ option.title }}</span>
          </button>
        </div>
        <el-form ref="formRef" :model="form" :rules="rules" @submit.prevent="submit">
          <el-form-item prop="username">
            <el-input v-model="form.username" data-testid="login-username" placeholder="账号" size="large" autocomplete="username" />
          </el-form-item>
          <el-form-item prop="password">
            <el-input v-model="form.password" data-testid="login-password" type="password" placeholder="密码" size="large" show-password autocomplete="current-password" />
          </el-form-item>
          <el-button data-testid="login-submit" type="primary" size="large" :loading="loading" native-type="submit" style="width: 100%">
            进入系统
          </el-button>
        </el-form>
        <div class="cmd-action-bar" style="justify-content: space-between">
          <span class="cmd-status">统一身份认证</span>
          <span class="cmd-status">权限自动分流</span>
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
import loginRoleHandoffImage from '../assets/login-role-handoff.png'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const formRef = ref()
const loading = ref(false)
const qrLoginPending = ref(false)
const dingtalkLoginPending = ref(false)
const selectedSurface = ref('review')

const form = reactive({
  username: '',
  password: ''
})

const surfaceOptions = [
  { value: 'entry', label: '录入端', title: '现场直接报数' },
  { value: 'review', label: '审阅端', title: '异常审阅处置' },
  { value: 'admin', label: '管理端', title: '系统配置治理' }
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
  if (surface === 'admin' && auth.adminSurface) return '/admin'
  if (surface === 'review' && auth.reviewSurface) return '/review/overview'
  return ''
}

function resolveRedirectPath() {
  const selected = surfaceLandingPath(selectedSurface.value)
  if (selected) return selected
  if (typeof route.query.redirect === 'string' && route.query.redirect) return route.query.redirect
  if (auth.defaultSurface === 'entry') return '/entry'
  if (auth.defaultSurface === 'admin') return '/admin'
  return '/review/overview'
}

async function submit() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return
  loading.value = true
  try {
    await auth.login({ username: form.username, password: form.password })
    ElMessage.success('登录成功')
    await router.push(resolveRedirectPath())
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
