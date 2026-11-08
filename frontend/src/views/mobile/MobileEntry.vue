<template>
  <div
    class="mobile-shell mobile-shell--entry"
    :class="{ 'mobile-shell--large-type': largeTypeMode }"
    data-testid="mobile-entry"
    data-visual-pass="stitch-image2-second-pass-mobile"
  >
    <!-- Pull to refresh indicator -->
    <div 
      class="mobile-pull-indicator" 
      :style="{ height: pullDistance + 'px', opacity: pullDistance / 80 }"
    >
      <div class="xt-execution-pulse" v-if="refreshing">同步中...</div>
      <div v-else>下拉刷新</div>
    </div>

    <section class="mobile-entry-stage" :style="{ transform: `translateY(${pullDistance}px)` }">
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
        <ol v-if="!isOwnerDailyEntry" class="mobile-shift-track" aria-label="班次">
          <li v-for="shift in SHIFT_TRACK" :key="shift" :class="{ 'is-current': currentShiftLabel.includes(shift) }">
            <i />
            <span>{{ shift }}</span>
          </li>
        </ol>

        <dl class="mobile-entry-stage__facts">
          <div v-for="fact in currentFacts" :key="fact.label" class="mobile-entry-stage__fact">
            <dt>{{ fact.label }}</dt>
            <dd>{{ fact.value }}</dd>
          </div>
        </dl>

        <section v-if="largeTypeMode" class="mobile-entry-stage__screen-summary" data-testid="mobile-screen-summary">
          <header>
            <span>现场屏幕</span>
            <strong>{{ screenSummaryTitle }}</strong>
          </header>
          <div>
            <article v-for="item in screenSummaryItems" :key="item.label">
              <span>{{ item.label }}</span>
              <strong>{{ item.value }}</strong>
            </article>
          </div>
        </section>

        <div class="mobile-entry-stage__cta">
          <el-button type="primary" size="large" data-testid="mobile-go-report" @click="goReport">
            开始填报
          </el-button>
          <el-button plain size="large" @click="goReportHistory">历史记录</el-button>
          <RouterLink v-if="procurementOn" class="mobile-entry-stage__link" to="/procurement">物资采购</RouterLink>
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
import { RouterLink, useRoute, useRouter } from 'vue-router'

import { fetchCurrentShift, fetchMobileBootstrap } from '../../api/mobile.js'
import { fetchProcurementMeta } from '../../api/procurement.js'
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

const SHIFT_TRACK = ['长白班', '小夜班', '大夜班']

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
const showReminderPanel = computed(() => Boolean(current.value?.can_submit || (current.value?.active_reminders || []).length))
const currentShiftLabel = computed(() => (
  isOwnerDailyEntry.value
    ? '每日一录'
    : formatShiftLabel(current.value?.shift_name || current.value?.shift_code, '-')
))
const inferredShift = ref(describeInferredShift())
const procurementOn = ref(false)
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
    return `按 09:30 起算，当前归属 ${inferOwnerDailyBusinessDate()}，每日一录。`
  }
  const wall = inferredShift.value
  if (!wall) return ''
  if (shiftMismatch.value && current.value?.shift_name) {
    return `当前时段属于 ${wall.code} ${wall.name}（${wall.businessDate}），页面将自动刷新最新任务。`
  }
  return `按 07:50 起算，当前是 ${wall.code} ${wall.name}（${wall.businessDate}）。`
})
const currentFacts = computed(() => [
  { label: '车间', value: current.value?.workshop_name || bootstrap.value?.workshop_name || '-' },
  { label: '日期', value: current.value?.business_date || '-' },
  { label: isMachineBound.value ? '机台' : '班组', value: isMachineBound.value ? (current.value?.machine_name || bootstrap.value?.machine_name || '-') : (current.value?.team_name || '-') },
  { label: '状态', value: formatStatusLabel(current.value?.report_status) }
])
const screenRoleBucket = computed(() => {
  if (auth.role === 'energy_stat' || transitionMapping.value.role_bucket === 'energy_stat') return 'energy'
  if (isOwnerDailyEntry.value) return 'owner'
  return 'operator'
})
const screenSummaryTitle = computed(() => {
  if (screenRoleBucket.value === 'energy') return '电工能耗填报'
  if (screenRoleBucket.value === 'owner') return '内勤每日填报'
  return '主操机列填报'
})
const screenSummaryItems = computed(() => {
  if (screenRoleBucket.value === 'energy') {
    return [
      { label: '归属日', value: current.value?.business_date || '-' },
      { label: '填报口径', value: '07:50循环' },
      { label: '当前状态', value: formatStatusLabel(current.value?.report_status) },
    ]
  }
  if (screenRoleBucket.value === 'owner') {
    return [
      { label: '归属日', value: current.value?.business_date || '-' },
      { label: '填报口径', value: '09:30循环' },
      { label: '录入方式', value: '每日一录' },
    ]
  }
  return [
    { label: '当前班次', value: currentShiftLabel.value },
    { label: '机列', value: current.value?.machine_name || bootstrap.value?.machine_name || '-' },
    { label: '历史', value: '整日可查' },
  ]
})
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
  fetchProcurementMeta().then(() => { procurementOn.value = true }).catch(() => {})
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
  overflow-wrap: anywhere;
  display: grid;
  gap: 32px;
  padding: 32px 20px 40px;
}

.mobile-pull-indicator {
  display: grid;
  place-items: center;
  overflow: hidden;
  color: var(--xt-text-muted);
  font-size: 12px;
}

.mobile-entry-stage {
  display: grid;
  gap: 32px;
}

.mobile-entry-stage__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.mobile-entry-stage__top h1 {
  margin: 0;
  font-size: 32px;
  font-weight: 600;
  line-height: 1.2;
}

.mobile-entry-stage__top p {
  margin: 4px 0 0;
  color: var(--xt-text-secondary);
}

.mobile-entry-stage__mode-toggle {
  flex: none;
  min-height: 44px;
  padding: 0 4px;
  border: 0;
  background: transparent;
  color: var(--xt-primary);
  font: inherit;
  font-size: 14px;
  cursor: pointer;
  touch-action: manipulation;
}

.mobile-entry-stage__empty {
  display: grid;
  gap: 8px;
  color: var(--xt-text-secondary);
}

.mobile-entry-stage__empty p {
  margin: 0;
}

.mobile-entry-stage__action-row {
  display: grid;
  gap: 12px;
  margin-top: 16px;
}

.mobile-entry-stage__action-row .el-button {
  width: 100%;
  margin: 0;
}

.mobile-entry-stage__hero {
  display: grid;
  gap: 32px;
}

.mobile-shift-track {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 4px;
  margin: 0;
  padding: 0;
  list-style: none;
}

.mobile-shift-track li {
  display: grid;
  gap: 8px;
  color: var(--xt-text-muted);
  font-size: 14px;
}

.mobile-shift-track i {
  display: block;
  height: 8px;
  border-radius: 2px;
  background: var(--xt-bg-depth);
}

.mobile-shift-track .is-current {
  color: var(--xt-primary);
  font-weight: 600;
}

.mobile-shift-track .is-current i {
  background: var(--xt-primary);
  transform-origin: left;
  animation: mobile-shift-grow 700ms cubic-bezier(0.16, 1, 0.3, 1) backwards;
}

.mobile-entry-stage__facts {
  display: grid;
  margin: 0;
}

.mobile-entry-stage__fact {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 0;
  border-bottom: 1px solid var(--xt-border);
}

.mobile-entry-stage__fact dt {
  color: var(--xt-text-secondary);
}

.mobile-entry-stage__fact dd {
  margin: 0;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  text-align: right;
}

.mobile-entry-stage__screen-summary {
  display: grid;
  gap: 16px;
  padding: 24px 20px;
  border-radius: 4px;
  background: var(--xt-primary);
  color: #fff;
}

.mobile-entry-stage__screen-summary header {
  display: grid;
  gap: 4px;
}

.mobile-entry-stage__screen-summary header strong {
  font-size: 24px;
  font-weight: 600;
}

.mobile-entry-stage__screen-summary > div {
  display: grid;
  gap: 12px;
}

.mobile-entry-stage__screen-summary article {
  display: flex;
  justify-content: space-between;
  gap: 16px;
}

.mobile-entry-stage__screen-summary article strong {
  font-size: 20px;
  font-weight: 600;
}

.mobile-entry-stage__cta {
  display: grid;
  gap: 12px;
}

.mobile-entry-stage__cta .el-button {
  width: 100%;
  min-height: 56px;
  margin: 0;
  font-size: 18px;
}

.mobile-entry-stage__link {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 48px;
  color: var(--xt-primary);
  text-decoration: none;
}

.mobile-shell--large-type {
  font-size: 18px;
}

.mobile-shell--large-type .mobile-entry-stage__top h1 {
  font-size: 40px;
}

.mobile-shell--large-type .mobile-entry-stage__fact dd {
  font-size: 22px;
}

.mobile-shell--large-type .mobile-entry-stage__cta .el-button {
  min-height: 72px;
  font-size: 24px;
}

@keyframes mobile-shift-grow {
  from {
    transform: scaleX(0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .mobile-shift-track .is-current i {
    animation: none;
  }
}
</style>
