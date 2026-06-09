<template>
  <div
    class="mobile-shell mobile-shell--entry"
    :class="{ 'mobile-shell--large-type': largeTypeMode }"
    data-testid="mobile-entry"
  >
    <!-- Pull to refresh indicator -->
    <div 
      class="mobile-pull-indicator" 
      :style="{ height: pullDistance + 'px', opacity: pullDistance / 80 }"
    >
      <div class="xt-execution-pulse" v-if="refreshing">同步中...</div>
      <div v-else>下拉刷新</div>
    </div>

    <section class="mobile-entry-stage panel" :style="{ transform: `translateY(${pullDistance}px)` }">
      <div class="mobile-entry-stage__top">
        <div>
          <div v-if="false" class="mobile-kicker">03 独立填报端</div>
          <h1>{{ pageTitle }}</h1>
          <p>{{ pageSubtitle }}</p>
        </div>
        <button class="mobile-entry-stage__mode-toggle" type="button" @click="toggleLargeTypeMode">
          {{ largeTypeMode ? '标准模式' : '大字模式' }}
        </button>
      </div>

      <el-alert
        v-if="authenticating"
        title="正在校验身份"
        type="info"
        show-icon
        :closable="false"
        class="panel"
      />

      <el-alert
        v-else-if="authError"
        :title="authError"
        type="error"
        show-icon
        :closable="false"
        class="panel"
      />

      <el-alert
        v-else-if="showDebugBootstrap"
        :title="bootstrapTip"
        :type="bootstrap.entry_mode === 'web_debug' ? 'info' : 'success'"
        show-icon
        :closable="false"
        class="panel"
      />

      <el-alert
        v-if="!authenticating && !authError && !loading && !loadError && hasCurrentShift && shiftHint"
        :title="shiftHint"
        :type="shiftMismatch ? 'warning' : 'info'"
        show-icon
        :closable="false"
        class="panel"
        data-testid="shift-clock-hint"
      />

      <div v-if="authenticating" class="mobile-entry-stage__empty">
        <XtSkeleton :loading="true" :rows="2" />
      </div>
      <div v-else-if="authError" class="mobile-entry-stage__empty">
        <p>{{ authError }}</p>
        <p>请重试钉钉鉴权，或改用账号登录。</p>
        <div class="mobile-entry-stage__action-row">
          <el-button
            :loading="retryingAuth"
            type="primary"
            plain
            class="mobile-inline-action"
            @click="retryAuth"
          >
            重试鉴权
          </el-button>
          <el-button plain class="mobile-inline-action" @click="goLogin">改用账号登录</el-button>
          <el-button plain class="mobile-inline-action" @click="load">重新加载</el-button>
        </div>
      </div>
      <div v-else-if="loading" class="mobile-entry-stage__empty">
        <XtSkeleton :loading="true" :rows="4" />
      </div>
      <div v-else-if="loadError" class="mobile-entry-stage__empty">
        <p>{{ loadError }}</p>
        <div class="mobile-entry-stage__action-row">
          <el-button type="primary" plain class="mobile-inline-action" :loading="loading" @click="load">重试加载</el-button>
          <el-button v-if="auth.adminSurface" plain class="mobile-inline-action" @click="goManage">进入管理端</el-button>
          <el-button plain class="mobile-inline-action" @click="goLogin">改用账号登录</el-button>
        </div>
      </div>
      <div v-else-if="!hasCurrentShift" class="mobile-entry-stage__empty">
        <p>当前账号暂未拿到可显示的班次任务。</p>
        <div class="mobile-entry-stage__action-row">
          <el-button type="primary" plain class="mobile-inline-action" @click="load">刷新任务</el-button>
        </div>
      </div>
      <div v-else-if="current.can_submit === false" class="mobile-entry-stage__empty">
        <p>{{ current.ownership_note || '当前账号暂未开启可填报岗位。' }}</p>
        <p>先联系管理员同步，或先看历史记录。</p>
        <div class="mobile-entry-stage__action-row">
          <el-button type="primary" plain class="mobile-inline-action" @click="load">刷新任务</el-button>
          <el-button plain class="mobile-inline-action" @click="goReportHistory">查看历史</el-button>
        </div>
      </div>
      <div v-else class="mobile-entry-stage__hero" data-testid="mobile-current-shift">
        <div class="mobile-entry-stage__identity" :style="{ '--role-color': roleColor }">
          <div class="mobile-entry-stage__identity-main">
            <strong>{{ roleBucketMeta.title }}</strong>
            <span>{{ current.workshop_name || bootstrap.workshop_name || '-' }}</span>
          </div>
          <div class="mobile-entry-stage__identity-shift">
            <span>{{ currentShiftLabel }}</span>
            <span>{{ current.business_date || '-' }}</span>
          </div>
        </div>

        <div v-if="isMachineBound" class="mobile-entry-stage__machine">
          <strong>{{ current.machine_name || bootstrap.machine_name || '-' }}</strong>
          <span>{{ auth.user?.username || '-' }}</span>
        </div>

        <div class="mobile-entry-stage__facts">
          <article v-for="fact in currentFacts" :key="fact.label" class="mobile-entry-stage__fact">
            <span>{{ fact.label }}</span>
            <strong>{{ fact.value }}</strong>
          </article>
        </div>

        <div class="mobile-entry-stage__cta">
          <el-button type="primary" size="large" data-testid="mobile-go-report" @click="goReport">
            开始填报
          </el-button>
          <div class="mobile-entry-stage__status">
            <span>状态</span>
            <strong>{{ formatStatusLabel(current.report_status) }}</strong>
          </div>
        </div>

        <div class="mobile-entry-stage__quick-grid">
          <el-button plain @click="goReportHistory">历史记录</el-button>
        </div>
      </div>
    </section>

    <el-card v-if="showReminderPanel" class="panel mobile-card">
      <template #header>提醒</template>
      <XtSkeleton :loading="loading" :rows="2">
        <ReminderList :items="current.active_reminders || []" empty-text="当前没有提醒。" />
      </XtSkeleton>
    </el-card>

  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { fetchCurrentShift, fetchMobileBootstrap } from '../../api/mobile.js'
import { useAuthStore } from '../../stores/auth.js'
import { usePullRefresh } from '../../composables/usePullRefresh.js'
import { usePerformance } from '../../composables/usePerformance.js'
import XtSkeleton from '../../components/xt/XtSkeleton.vue'
import { formatScopeLabel, formatShiftLabel, formatStatusLabel } from '../../utils/display.js'
import {
  buildMobileTransitionMapping,
  describeTransitionRoleBucket
} from '../../utils/mobileTransition.js'
import { describeInferredShift, inferOwnerDailyBusinessDate, isShiftMismatch } from '../../utils/shiftClock.js'
import ReminderList from './ReminderList.vue'

// Performance monitoring
usePerformance('MobileEntry')

const ROLE_COLOR_MAP = {
  machine_operator: 'var(--m-role-operator)',
  energy_stat: 'var(--m-role-energy)',
  consumable_stat: 'var(--m-role-consumable)',
  qc: 'var(--m-role-qc)',
  utility_manager: 'var(--m-role-utility)',
  inventory_keeper: 'var(--m-role-inventory)',
  contracts: 'var(--m-role-contracts)',
  quality_owner: 'var(--m-role-qc)',
  planning_owner: 'var(--m-role-contracts)',
  energy_chief: 'var(--m-role-energy)',
  storage_owner: 'var(--m-role-inventory)',
  shipment_outflow_owner: 'var(--m-role-utility)',
  recovery_owner: 'var(--m-role-consumable)',
  overhaul_owner: 'var(--m-role-utility)',
}

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const isDev = import.meta.env.DEV
const loading = ref(true)
const authenticating = ref(false)
const retryingAuth = ref(false)
const authError = ref('')
const loadError = ref('')
const bootstrap = ref({})
const current = ref({})
const hasCurrentShift = computed(() => Boolean(current.value?.shift_id))
const largeTypeMode = ref(readLargeTypeMode())

// Pull refresh setup
const { pullDistance, refreshing } = usePullRefresh(load)

const isMachineBound = computed(() => Boolean(current.value?.is_machine_bound || bootstrap.value?.is_machine_bound || auth.isMachineBound))
const transitionMapping = computed(() => buildMobileTransitionMapping({
  role: auth.role,
  isMachineBound: isMachineBound.value,
  reportStatus: current.value?.report_status,
}))
const OWNER_DAILY_BUCKETS = new Set([
  'quality_owner',
  'planning_owner',
  'energy_chief',
  'storage_owner',
  'consumable_stat',
  'shipment_outflow_owner',
  'recovery_owner',
  'overhaul_owner',
])
const isOwnerDailyEntry = computed(() => OWNER_DAILY_BUCKETS.has(transitionMapping.value.role_bucket))
const roleBucketMeta = computed(() => describeTransitionRoleBucket(transitionMapping.value.role_bucket))
const pageTitle = computed(() => roleBucketMeta.value.title)
const pageSubtitle = computed(() => roleBucketMeta.value.subtitle)
const roleColor = computed(() => ROLE_COLOR_MAP[bootstrap.value?.user_role || auth.role] || 'var(--m-role-operator)')
const showReminderPanel = computed(() => Boolean(current.value?.can_submit || (current.value?.active_reminders || []).length))
const currentShiftLabel = computed(() => (
  isOwnerDailyEntry.value
    ? '每日一录'
    : formatShiftLabel(current.value?.shift_name || current.value?.shift_code, '-')
))
const inferredShift = ref(describeInferredShift())
const shiftClockTimer = ref(null)
const shiftMismatch = computed(() => {
  if (isOwnerDailyEntry.value) {
    const ownerBusinessDate = inferOwnerDailyBusinessDate()
    return Boolean(current.value?.business_date && current.value.business_date !== ownerBusinessDate)
  }
  const wall = inferredShift.value
  if (current.value?.business_date && wall?.businessDate && current.value.business_date !== wall.businessDate) return true
  return isShiftMismatch(current.value?.shift_code)
})
const shiftHint = computed(() => {
  if (isOwnerDailyEntry.value) {
    return `按 10:00 起算，当前归属 ${inferOwnerDailyBusinessDate()}，每日一录。`
  }
  const wall = inferredShift.value
  if (!wall) return ''
  if (shiftMismatch.value && current.value?.shift_name) {
    return `当前时段属于 ${wall.code} ${wall.name}（${wall.businessDate}），页面将自动刷新最新任务。`
  }
  return `按 07:30 起算，当前是 ${wall.code} ${wall.name}（${wall.businessDate}）。`
})
const currentFacts = computed(() => [
  { label: '日期', value: current.value?.business_date || '-' },
  { label: isMachineBound.value ? '机台' : '班组', value: isMachineBound.value ? (current.value?.machine_name || bootstrap.value?.machine_name || '-') : (current.value?.team_name || '-') },
  { label: '状态', value: formatStatusLabel(current.value?.report_status) }
])
const showDebugBootstrap = computed(() => (
  auth.isLoggedIn &&
  isDev &&
  route.query.debug === '1' &&
  Boolean(bootstrap.value.current_identity_source)
))

function resolveAuthCode() {
  const candidates = [route.query.authCode, route.query.auth_code, route.query.code]
  const code = candidates.find((value) => typeof value === 'string' && value.trim())
  return code ? code.trim() : ''
}

function isDingTalkRuntime() {
  if (typeof window === 'undefined') return false
  const userAgent = window.navigator?.userAgent || ''
  return Boolean(window.dd) || /DingTalk/i.test(userAgent)
}

function resolveDingTalkCorpId() {
  if (typeof window === 'undefined') return ''
  return import.meta.env.VITE_DINGTALK_CORP_ID || window.__DINGTALK_CORP_ID__ || ''
}

async function loadDingTalkJsApi() {
  if (window.dd) return window.dd
  if (typeof window.loadDingTalkJsApi === 'function') {
    return window.loadDingTalkJsApi()
  }
  await new Promise((resolve, reject) => {
    const script = document.createElement('script')
    script.src = '/dingtalk-jsapi-loader.js'
    script.async = true
    script.onload = resolve
    script.onerror = () => reject(new Error('dingtalk_jsapi_loader_failed'))
    document.head.appendChild(script)
  })
  return window.loadDingTalkJsApi()
}

function getDingTalkAuthCode(dd, corpId) {
  return new Promise((resolve, reject) => {
    const onSuccess = (result) => {
      const code = result?.code || result?.authCode || result?.auth_code || ''
      if (code) {
        resolve(code)
      } else {
        reject(new Error('dingtalk_auth_code_missing'))
      }
    }
    const onFail = (error) => reject(error || new Error('dingtalk_auth_failed'))

    if (typeof dd.config === 'function') {
      dd.config({
        corpId,
        jsApiList: ['runtime.permission.requestAuthCode', 'biz.util.scan']
      })
    }
    if (dd.runtime?.permission?.requestAuthCode) {
      dd.runtime.permission.requestAuthCode({ corpId, onSuccess, onFail })
      return
    }
    if (typeof dd.getAuthCode === 'function') {
      dd.getAuthCode({ corpId, success: onSuccess, fail: onFail })
      return
    }
    reject(new Error('dingtalk_auth_api_missing'))
  })
}

async function resolveRuntimeAuthCode() {
  const queryCode = resolveAuthCode()
  if (queryCode || !isDingTalkRuntime()) return queryCode
  const corpId = resolveDingTalkCorpId()
  if (!corpId) return ''
  const dd = await loadDingTalkJsApi()
  return getDingTalkAuthCode(dd, corpId)
}

function parseErrorMessage(error, fallback) {
  const detail = error?.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || item).join('；')
  }
  if (detail && typeof detail === 'object') {
    return detail.message || detail.msg || fallback
  }
  if (typeof detail === 'string' && detail.trim()) {
    if (detail.trim() === 'Mobile access denied') {
      return '当前账号是管理端账号，请进入管理端查看数据。'
    }
    return detail.trim()
  }
  return error?.message || fallback
}

  const bootstrapTip = computed(() => {
    const scopeSummary = bootstrap.value.current_scope_summary || {}
    const scopeLabel = formatScopeLabel(scopeSummary.data_scope_type)
    const entryModeMap = {
      dingtalk_h5: '钉钉工作台',
      web_debug: '浏览器调试'
    }
    const identitySourceMap = {
      dingtalk_oauth: '钉钉免登',
      dingtalk_runtime: '钉钉运行时',
      dingtalk_binding: '钉钉绑定',
      signed_query: '签名参数',
    dev_fallback: '本地调试'
  }
  const entryMode = entryModeMap[bootstrap.value.entry_mode] || '浏览器调试'
  const identitySource = identitySourceMap[bootstrap.value.current_identity_source] || '本地调试'
  return `入口 ${entryMode} · 身份 ${identitySource} · 范围 ${scopeLabel}`
})

async function ensureDingtalkSession() {
  if (auth.isLoggedIn) return true
  authenticating.value = true
  authError.value = ''
  try {
    const code = await resolveRuntimeAuthCode()
    if (!code) return true
    await auth.dingtalkLogin(code)
    const nextQuery = { ...route.query }
    delete nextQuery.code
    delete nextQuery.authCode
    delete nextQuery.auth_code
    delete nextQuery.state
    await router.replace({ name: 'mobile-entry', query: nextQuery })
    return true
  } catch (error) {
    authError.value = isDingTalkRuntime()
      ? '钉钉鉴权失败，改用账号登录'
      : parseErrorMessage(error, '钉钉登录失败，请联系管理员检查账号映射。')
    return false
  } finally {
    authenticating.value = false
  }
}

async function load() {
  const ready = await ensureDingtalkSession()
  if (!ready) {
    loading.value = false
    return
  }
  loading.value = true
  loadError.value = ''
  authError.value = ''
  try {
    current.value = {}
    bootstrap.value = {}
    const [bootstrapData, currentData] = await Promise.all([
      fetchMobileBootstrap(),
      fetchCurrentShift()
    ])
    bootstrap.value = bootstrapData
    current.value = currentData
  } catch (error) {
    bootstrap.value = {}
    current.value = {}
    loadError.value = parseErrorMessage(error, '加载当前班次失败，请稍后重试或改用账号登录。')
  } finally {
    loading.value = false
  }
}

async function retryAuth() {
  if (retryingAuth.value) return
  retryingAuth.value = true
  try {
    const ready = await ensureDingtalkSession()
    if (ready) {
      await load()
    }
  } finally {
    retryingAuth.value = false
  }
}

function goReport() {
  const bucket = transitionMapping.value.role_bucket
  const ROLE_BUCKETS_USING_UNIFIED = new Set([
    'machine_operator',
    'energy_stat',
    'quality_owner',
    'planning_owner',
    'energy_chief',
    'storage_owner',
    'consumable_stat',
    'shipment_outflow_owner',
    'recovery_owner',
    'overhaul_owner',
  ])
  if (!current.value?.shift_id && !ROLE_BUCKETS_USING_UNIFIED.has(bucket)) return
  if (ROLE_BUCKETS_USING_UNIFIED.has(bucket)) {
    router.push({ name: 'mobile-unified-entry' })
    return
  }
  router.push({
    name: 'mobile-report-form',
    params: {
      businessDate: current.value.business_date,
      shiftId: current.value.shift_id
    }
  })
}

function goLogin() {
  router.push({ name: 'login', query: { redirect: '/entry' } })
}

function readLargeTypeMode() {
  const queryValue = route.query.view || route.query.screen || route.query.large
  if (['large', 'big', '1', 'true'].includes(String(queryValue || '').toLowerCase())) return true
  if (typeof window === 'undefined') return false
  return window.localStorage?.getItem('xt-mobile-large-type') === '1'
}

function toggleLargeTypeMode() {
  largeTypeMode.value = !largeTypeMode.value
  if (typeof window !== 'undefined') {
    window.localStorage?.setItem('xt-mobile-large-type', largeTypeMode.value ? '1' : '0')
  }
}

function goManage() {
  router.push({ name: 'admin-ops-reliability' })
}

function goReportHistory() {
  router.push({ name: 'mobile-report-history' })
}

async function refreshShiftClock() {
  inferredShift.value = describeInferredShift()
  if (!shiftMismatch.value || loading.value || authenticating.value || retryingAuth.value) return
  await load()
}

onMounted(() => {
  load()
  shiftClockTimer.value = setInterval(() => {
    refreshShiftClock()
  }, 60 * 1000)
})

onUnmounted(() => {
  if (shiftClockTimer.value) {
    clearInterval(shiftClockTimer.value)
    shiftClockTimer.value = null
  }
})
</script>

<style scoped>
.mobile-shell--entry {
  overflow-x: hidden;
}

.mobile-pull-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  color: var(--xt-primary);
  font-size: 13px;
  font-weight: 800;
  transition: height 0.1s ease;
  text-shadow: 0 0 14px rgba(0, 242, 255, 0.28);
}

.mobile-entry-stage,
.mobile-entry-stage__top,
.mobile-entry-stage__hero,
.mobile-entry-stage__facts,
.mobile-entry-stage__cta {
  display: grid;
  gap: 12px;
}

.mobile-entry-stage {
  position: relative;
  overflow: hidden;
  padding: var(--xt-space-3);
  background:
    linear-gradient(145deg, rgba(9, 27, 50, 0.94), rgba(3, 12, 24, 0.84)),
    radial-gradient(circle at 18% 0%, rgba(0, 242, 255, 0.16), transparent 42%);
  border-color: rgba(0, 242, 255, 0.18);
  border-radius: var(--xt-radius-2xl);
  box-shadow: 0 24px 54px rgba(0, 0, 0, 0.26), inset 0 1px 0 rgba(255, 255, 255, 0.07);
  transition: transform 0.1s ease;
}

.mobile-entry-stage::before {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(115deg, transparent 0 34%, rgba(0, 242, 255, 0.12) 48%, transparent 62% 100%);
  opacity: 0.42;
  transform: translateX(-75%);
  animation: mobileEntrySweep 6.8s ease-in-out infinite;
}

.mobile-entry-stage__top {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
  gap: 6px;
}

.mobile-logout-btn {
  font-size: 12px;
  color: var(--xt-text-muted);
  margin-top: 6px;
}

.mobile-entry-stage__top h1 {
  margin: 4px 0 0;
  font-size: var(--xt-text-2xl);
  font-family: var(--xt-font-display);
  font-weight: 950;
  line-height: 1.22;
  color: var(--xt-text);
  text-shadow: 0 0 22px rgba(0, 242, 255, 0.2);
}

.mobile-entry-stage__mode-toggle {
  position: relative;
  z-index: 1;
  min-height: 38px;
  border: 1px solid rgba(0, 242, 255, 0.28);
  border-radius: var(--xt-radius-pill);
  padding: 0 12px;
  background: rgba(3, 12, 24, 0.54);
  color: rgba(225, 253, 255, 0.9);
  font-size: var(--xt-text-sm);
  font-weight: 900;
}

.mobile-entry-stage__top p {
  max-width: 30ch;
  font-size: var(--xt-text-lg);
  line-height: 1.4;
}

.mobile-entry-stage__top p,
.mobile-entry-stage__empty,
.mobile-entry-stage__fact span,
.mobile-entry-stage__machine span,
.mobile-entry-stage__status span {
  margin: 0;
  color: var(--app-muted);
}

.mobile-entry-stage__identity {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: var(--xt-space-4);
  border-radius: var(--xt-radius-xl);
  background: linear-gradient(135deg, rgba(0, 242, 255, 0.12), rgba(4, 16, 31, 0.88));
  border: 1px solid rgba(0, 242, 255, 0.2);
  border-left: 3px solid var(--role-color, var(--xt-primary));
  box-shadow: 0 16px 34px rgba(0, 0, 0, 0.24), inset 0 1px 0 rgba(255, 255, 255, 0.08);
}

.mobile-entry-stage__identity::after {
  content: '';
  position: absolute;
  right: 14px;
  top: 14px;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--xt-primary);
  box-shadow: 0 0 0 4px rgba(0, 242, 255, 0.1), 0 0 18px rgba(0, 242, 255, 0.7);
  animation: mobileEntryLed 1.9s ease-in-out infinite;
}

.mobile-entry-stage__identity-main {
  display: grid;
  gap: 2px;
}

.mobile-entry-stage__identity-main strong {
  color: rgba(255, 255, 255, 0.92);
  font-family: var(--xt-font-display);
  font-size: var(--xt-text-xl);
  font-weight: 850;
  letter-spacing: -0.012em;
  line-height: 1.18;
}

.mobile-entry-stage__identity-main span {
  color: rgba(255, 255, 255, 0.55);
  font-size: var(--xt-text-sm);
}

.mobile-entry-stage__identity-shift {
  display: grid;
  gap: 2px;
  text-align: right;
}

.mobile-entry-stage__identity-shift span {
  color: rgba(255, 255, 255, 0.55);
  font-size: var(--xt-text-sm);
}

.mobile-entry-stage__identity-shift span:first-child {
  color: rgba(255, 255, 255, 0.82);
  font-family: var(--xt-font-number);
  font-size: var(--xt-text-lg);
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}

.mobile-entry-stage__empty {
  display: grid;
  gap: var(--xt-space-2);
  padding: var(--xt-space-4);
  border: 1px solid var(--xt-border-light);
  border-radius: var(--xt-radius-xl);
  background: var(--xt-bg-panel-soft);
}

.mobile-entry-stage__empty p + p {
  font-size: var(--xt-text-sm);
}

.mobile-entry-stage__action-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.mobile-entry-stage__action-row .el-button {
  border-radius: var(--xt-radius-lg);
  min-height: 48px;
  min-width: 122px;
}

.mobile-entry-stage__machine {
  display: grid;
  gap: var(--xt-space-1);
  padding: var(--xt-space-3);
  border-radius: var(--xt-radius-lg);
  background: rgba(0, 242, 255, 0.07);
  border: 1px solid rgba(0, 242, 255, 0.14);
}

.mobile-entry-stage__machine strong {
  color: var(--app-text);
}

.mobile-entry-stage__facts {
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.mobile-entry-stage__fact {
  display: grid;
  gap: var(--xt-space-1);
  padding: var(--xt-space-3);
  border-radius: var(--xt-radius-lg);
  background: rgba(3, 12, 24, 0.54);
  border: 1px solid rgba(0, 242, 255, 0.12);
}

.mobile-entry-stage__fact strong {
  color: var(--app-text);
  font-family: var(--xt-font-number);
  font-variant-numeric: tabular-nums;
  text-shadow: 0 0 16px rgba(0, 242, 255, 0.14);
}

.mobile-entry-stage__cta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.mobile-entry-stage__cta .el-button {
  position: relative;
  overflow: hidden;
  min-height: 52px;
  min-width: 156px;
  border-radius: var(--xt-radius-lg);
  font-size: var(--xt-text-lg);
  font-weight: 900;
}

.mobile-entry-stage__cta .el-button::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(110deg, transparent, rgba(255, 255, 255, 0.32), transparent);
  transform: translateX(-110%);
  animation: mobileEntryButtonSweep 4.2s ease-in-out infinite;
}

.mobile-entry-stage__status {
  position: relative;
  display: grid;
  gap: var(--xt-space-1);
  padding: var(--xt-space-3) var(--xt-space-3) var(--xt-space-3) 28px;
  border-radius: var(--xt-radius-lg);
  background: rgba(3, 12, 24, 0.54);
  border: 1px solid rgba(0, 242, 255, 0.12);
}

.mobile-entry-stage__status::before {
  content: '';
  position: absolute;
  left: 12px;
  top: 50%;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--xt-primary);
  box-shadow: 0 0 14px rgba(0, 242, 255, 0.68);
  transform: translateY(-50%);
}

.mobile-entry-stage__status strong {
  color: var(--app-text);
}

.mobile-entry-stage__quick-grid {
  display: grid;
  gap: 8px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.mobile-entry-stage__quick-grid .el-button {
  min-height: 48px;
  border-radius: var(--xt-radius-lg);
  font-size: var(--xt-text-lg);
}

.mobile-shell--large-type .mobile-entry-stage {
  min-height: min(720px, calc(100dvh - 24px));
}

.mobile-shell--large-type .mobile-entry-stage__top h1 {
  font-size: clamp(32px, 9vw, 54px);
  line-height: 1.08;
}

.mobile-shell--large-type .mobile-entry-stage__top p {
  font-size: clamp(18px, 4.5vw, 26px);
}

.mobile-shell--large-type .mobile-entry-stage__identity {
  align-items: stretch;
}

.mobile-shell--large-type .mobile-entry-stage__identity-main strong {
  font-size: clamp(28px, 7vw, 44px);
}

.mobile-shell--large-type .mobile-entry-stage__identity-main span,
.mobile-shell--large-type .mobile-entry-stage__identity-shift span {
  font-size: clamp(16px, 4vw, 22px);
}

.mobile-shell--large-type .mobile-entry-stage__identity-shift span:first-child {
  font-size: clamp(24px, 6vw, 36px);
}

.mobile-shell--large-type .mobile-entry-stage__machine strong,
.mobile-shell--large-type .mobile-entry-stage__fact strong,
.mobile-shell--large-type .mobile-entry-stage__status strong {
  font-size: clamp(24px, 6.5vw, 38px);
  line-height: 1.08;
}

.mobile-shell--large-type .mobile-entry-stage__fact span,
.mobile-shell--large-type .mobile-entry-stage__machine span,
.mobile-shell--large-type .mobile-entry-stage__status span {
  font-size: clamp(15px, 4vw, 21px);
}

.mobile-shell--large-type .mobile-entry-stage__facts {
  grid-template-columns: 1fr;
}

.mobile-shell--large-type .mobile-entry-stage__cta {
  display: grid;
  grid-template-columns: 1fr;
}

.mobile-shell--large-type .mobile-entry-stage__cta .el-button,
.mobile-shell--large-type .mobile-entry-stage__quick-grid .el-button {
  width: 100%;
  min-height: 68px;
  font-size: clamp(20px, 5.5vw, 30px);
}

@keyframes mobileEntrySweep {
  0%, 52% { transform: translateX(-82%); }
  100% { transform: translateX(82%); }
}

@keyframes mobileEntryLed {
  0%, 100% { opacity: 0.58; transform: scale(0.92); }
  50% { opacity: 1; transform: scale(1.08); }
}

@keyframes mobileEntryButtonSweep {
  0%, 48% { transform: translateX(-110%); }
  100% { transform: translateX(110%); }
}

.mobile-entry-stage__action-row :deep(.el-button--primary.is-plain),
.mobile-entry-stage__quick-grid :deep(.el-button--primary.is-plain) {
  border-color: var(--xt-primary-border);
  background: var(--xt-bg-panel);
  color: var(--xt-primary);
}

.mobile-entry-stage__action-row :deep(.el-button--primary.is-plain:hover),
.mobile-entry-stage__quick-grid :deep(.el-button--primary.is-plain:hover) {
  background: var(--xt-primary-light);
}

@media (max-width: 720px) {
  .mobile-entry-stage__top,
  .mobile-entry-stage__cta {
    grid-template-columns: 1fr;
    display: grid;
  }

  .mobile-entry-stage__action-row {
    display: grid;
    grid-template-columns: 1fr;
  }

  .mobile-entry-stage__facts {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .mobile-entry-stage__quick-grid {
    grid-template-columns: 1fr;
  }
}
</style>
