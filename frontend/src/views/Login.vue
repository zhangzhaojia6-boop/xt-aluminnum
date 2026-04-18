<template>
  <div class="login-page">
    <div class="login-card panel" data-testid="login-page">
      <div class="login-brand" data-testid="login-brand">
        <div class="login-mark">鑫</div>
        <div>
          <h1>鑫泰铝业</h1>
          <p>河南鑫泰铝业有限公司 · 生产数据管理平台</p>
        </div>
      </div>

      <el-alert
        v-if="wecomLoginPending"
        title="正在通过企业微信识别身份，请稍候。"
        type="success"
        show-icon
        :closable="false"
        class="panel"
        style="margin-bottom: 18px"
      />

      <el-alert
        v-else-if="hasWecomCode"
        title="已收到企业微信授权码，正在准备自动登录。"
        type="info"
        show-icon
        :closable="false"
        class="panel"
        style="margin-bottom: 18px"
      />

      <el-alert
        v-if="qrLoginPending"
        title="正在识别机台二维码并自动登录，请稍候。"
        type="info"
        show-icon
        :closable="false"
        class="panel"
        style="margin-bottom: 18px"
      />

      <el-alert
        title="手机端默认从企业微信工作台进入；浏览器账号登录和机台二维码登录仅保留为调试/兜底入口。"
        type="warning"
        show-icon
        :closable="false"
        class="panel"
        style="margin-bottom: 18px"
      />

      <el-form ref="formRef" :model="form" :rules="rules" @submit.prevent="submit">
        <el-form-item prop="username">
          <el-input
            v-model="form.username"
            data-testid="login-username"
            placeholder="请输入账号"
            size="large"
            autocomplete="username"
          />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            data-testid="login-password"
            type="password"
            placeholder="请输入密码"
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
          :disabled="qrLoginPending || wecomLoginPending"
          native-type="submit"
          style="width: 100%"
        >
          登录系统
        </el-button>
      </el-form>

      <div class="login-tip">
        一线机台与班组岗位请优先从企业微信工作台进入手机填报。<br />
        管理员、观察者与实施人员使用桌面后台查看结果、处理异常和维护配置。
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import { useAuthStore } from '../stores/auth.js'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()
const formRef = ref()
const loading = ref(false)
const qrLoginPending = ref(false)
const wecomLoginPending = ref(false)

const form = reactive({
  username: '',
  password: ''
})

const rules = {
  username: [{ required: true, message: '请输入账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }]
}

const hasWecomCode = computed(() => Boolean(resolveQueryValue('code')))

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

function resolveRedirectPath() {
  const fallback = auth.canAccessDesktop ? '/dashboard/factory' : '/mobile'
  if (!(typeof route.query.redirect === 'string' && route.query.redirect)) {
    return fallback
  }

  try {
    const parsed = new URL(route.query.redirect, window.location.origin)
    parsed.searchParams.delete('code')
    parsed.searchParams.delete('state')
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

async function tryWecomLogin() {
  const code = resolveQueryValue('code')
  if (!code) return false

  wecomLoginPending.value = true
  try {
    await auth.wecomLogin(code)
    ElMessage.success('企业微信登录成功')
    await router.replace(resolveRedirectPath())
    return true
  } catch {
    return false
  } finally {
    wecomLoginPending.value = false
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

onMounted(async () => {
  const wecomLoggedIn = await tryWecomLogin()
  if (wecomLoggedIn) return
  await tryQrLogin()
})
</script>
