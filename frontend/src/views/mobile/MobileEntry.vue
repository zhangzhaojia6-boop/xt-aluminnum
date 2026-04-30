<template>
  <div class="mobile-shell mobile-shell--entry" data-testid="mobile-entry">
    <section class="mobile-entry-stage panel">
      <div class="mobile-entry-stage__top">
        <div>
          <div v-if="false" class="mobile-kicker">03 独立填报端</div>
          <h1>{{ pageTitle }}</h1>
          <p>{{ pageSubtitle }}</p>
        </div>
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

      <div v-if="authenticating" class="mobile-entry-stage__empty">正在校验身份…</div>
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
        <p>正在加载当前任务…</p>
        <p>可稍后重试。</p>
        <div class="mobile-entry-stage__action-row">
          <el-button type="primary" plain class="mobile-inline-action" :loading="loading" @click="load">再次尝试</el-button>
        </div>
      </div>
      <div v-else-if="loadError" class="mobile-entry-stage__empty">
        <p>{{ loadError }}</p>
        <div class="mobile-entry-stage__action-row">
          <el-button type="primary" plain class="mobile-inline-action" :loading="loading" @click="load">重试加载</el-button>
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
            <span>{{ current.shift_name || current.shift_code || '-' }}</span>
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
            {{ transitionMapping.primary_cta }}
          </el-button>
          <div class="mobile-entry-stage__status">
            <span>状态</span>
            <strong>{{ formatStatusLabel(current.report_status) }}</strong>
          </div>
        </div>

        <div class="mobile-entry-stage__quick-grid">
          <el-button type="primary" plain @click="goReport">快速填报</el-button>
          <el-button plain @click="goAdvancedReport">高级填报</el-button>
          <el-button plain :disabled="!ocrSupported || !current.shift_id" @click="goOcr">OCR</el-button>
          <el-button plain @click="goReportHistory">历史记录</el-button>
        </div>
      </div>
    </section>

    <el-card v-if="showReminderPanel" class="panel mobile-card">
      <template #header>提醒</template>
      <ReminderList :items="current.active_reminders || []" empty-text="当前没有提醒。" />
    </el-card>

  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { fetchCurrentShift, fetchMobileBootstrap, fetchWorkshopTemplate } from '../../api/mobile.js'
import { useAuthStore } from '../../stores/auth.js'
import { formatScopeLabel, formatStatusLabel } from '../../utils/display.js'
import {
  buildMobileTransitionMapping,
  describeTransitionRoleBucket
} from '../../utils/mobileTransition.js'
import ReminderList from './ReminderList.vue'

const ROLE_COLOR_MAP = {
  shift_leader: 'var(--m-role-operator)',
  mobile_user: 'var(--m-role-operator)',
  energy_stat: 'var(--m-role-energy)',
  maintenance_lead: 'var(--m-role-maintenance)',
  hydraulic_lead: 'var(--m-role-hydraulic)',
  consumable_stat: 'var(--m-role-consumable)',
  qc: 'var(--m-role-qc)',
  weigher: 'var(--m-role-weigher)',
  utility_manager: 'var(--m-role-utility)',
  inventory_keeper: 'var(--m-role-inventory)',
  contracts: 'var(--m-role-contracts)',
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
const ocrSupported = ref(false)
const hasCurrentShift = computed(() => Boolean(current.value?.shift_id))

const isMachineBound = computed(() => Boolean(current.value?.is_machine_bound || bootstrap.value?.is_machine_bound || auth.isMachineBound))
const transitionMapping = computed(() => buildMobileTransitionMapping({
  role: auth.role,
  isMachineBound: isMachineBound.value,
  reportStatus: current.value?.report_status,
  ocrSupported: ocrSupported.value
}))
const roleBucketMeta = computed(() => describeTransitionRoleBucket(transitionMapping.value.role_bucket))
const pageTitle = computed(() => roleBucketMeta.value.title)
const pageSubtitle = computed(() => roleBucketMeta.value.subtitle)
const roleColor = computed(() => ROLE_COLOR_MAP[bootstrap.value?.user_role || auth.role] || 'var(--m-role-operator)')
const showReminderPanel = computed(() => Boolean(current.value?.can_submit || (current.value?.active_reminders || []).length))
const advancedRoleBuckets = [
  'machine_operator',
  'weigher',
  'qc',
  'energy_stat',
  'maintenance_lead',
  'hydraulic_lead',
  'contracts',
  'inventory_keeper',
  'utility_manager'
]
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

function parseErrorMessage(error, fallback) {
  const detail = error?.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || item).join('；')
  }
  if (detail && typeof detail === 'object') {
    return detail.message || detail.msg || fallback
  }
  if (typeof detail === 'string' && detail.trim()) {
    return detail.trim()
  }
  return error?.message || fallback
}

  const bootstrapTip = computed(() => {
    const scopeSummary = bootstrap.value.current_scope_summary || {}
    const scopeLabel = formatScopeLabel(scopeSummary.data_scope_type)
    const entryModeMap = {
      dingtalk_h5: '钉钉工作台',
      wecom_h5: '钉钉工作台',
      web_debug: '浏览器调试'
    }
    const identitySourceMap = {
      wecom_oauth: '钉钉免登',
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
  const code = resolveAuthCode()
  if (auth.isLoggedIn || !code) return true

  authenticating.value = true
  authError.value = ''
  try {
    await auth.dingtalkLogin(code)
    const nextQuery = { ...route.query }
    delete nextQuery.code
    delete nextQuery.authCode
    delete nextQuery.auth_code
    delete nextQuery.state
    await router.replace({ name: 'mobile-entry', query: nextQuery })
    return true
  } catch (error) {
    authError.value = parseErrorMessage(error, '钉钉登录失败，请联系管理员检查账号映射。')
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

    const templateKey = currentData?.workshop_code || currentData?.workshop_type
    if (templateKey) {
      try {
        const template = await fetchWorkshopTemplate(templateKey)
        ocrSupported.value = Boolean(template?.supports_ocr)
      } catch {
        ocrSupported.value = false
      }
    } else {
      ocrSupported.value = false
    }
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
  if (!current.value?.shift_id) return
  const reportRouteName = advancedRoleBuckets.includes(transitionMapping.value.role_bucket)
    ? 'mobile-report-form-advanced'
    : 'mobile-report-form'
  router.push({
    name: reportRouteName,
    params: {
      businessDate: current.value.business_date,
      shiftId: current.value.shift_id
    }
  })
}

function goAdvancedReport() {
  if (!current.value?.shift_id) return
  router.push({
    name: 'mobile-report-form-advanced',
    params: {
      businessDate: current.value.business_date,
      shiftId: current.value.shift_id
    }
  })
}

function goOcr() {
  if (!current.value?.shift_id || !ocrSupported.value) return
  router.push({
    name: 'mobile-ocr-capture',
    params: {
      businessDate: current.value.business_date,
      shiftId: current.value.shift_id
    }
  })
}

function goLogin() {
  router.push({ name: 'login', query: { redirect: '/entry' } })
}

function goReportHistory() {
  router.push({ name: 'mobile-report-history' })
}

onMounted(load)
</script>

<style scoped>
.mobile-entry-stage,
.mobile-entry-stage__top,
.mobile-entry-stage__hero,
.mobile-entry-stage__facts,
.mobile-entry-stage__cta {
  display: grid;
  gap: 12px;
}

.mobile-entry-stage {
  padding: var(--xt-space-3);
  background: var(--xt-bg-panel);
  border-color: var(--xt-border-light);
  border-radius: var(--xt-radius-2xl);
}

.mobile-entry-stage__top {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
  gap: 6px;
}

.mobile-entry-stage__top h1 {
  margin: 4px 0 0;
  font-size: var(--xt-text-2xl);
  font-family: var(--xt-font-display);
  font-weight: 950;
  line-height: 1.22;
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
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: var(--xt-space-4);
  border-radius: var(--xt-radius-xl);
  background: var(--xt-bg-ink);
  border-left: 3px solid var(--role-color, var(--xt-primary));
  box-shadow: var(--xt-shadow-md);
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
  background: var(--xt-bg-panel-soft);
  border: 1px solid var(--xt-border-light);
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
  background: var(--xt-bg-panel);
  border: 1px solid var(--xt-border-light);
}

.mobile-entry-stage__fact strong {
  color: var(--app-text);
  font-family: var(--xt-font-number);
  font-variant-numeric: tabular-nums;
}

.mobile-entry-stage__cta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.mobile-entry-stage__cta .el-button {
  min-height: 52px;
  min-width: 156px;
  border-radius: var(--xt-radius-lg);
  font-size: var(--xt-text-lg);
  font-weight: 900;
}

.mobile-entry-stage__status {
  display: grid;
  gap: var(--xt-space-1);
  padding: var(--xt-space-3);
  border-radius: var(--xt-radius-lg);
  background: var(--xt-bg-panel);
  border: 1px solid var(--xt-border-light);
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

.mobile-entry-stage__action-row :deep(.el-button--primary.is-plain),
.mobile-entry-stage__quick-grid :deep(.el-button--primary.is-plain) {
  border-color: rgba(0, 113, 227, 0.34);
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
