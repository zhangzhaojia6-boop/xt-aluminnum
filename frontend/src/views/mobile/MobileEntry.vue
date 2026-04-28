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
        <div class="mobile-entry-stage__brand">
          <span class="mobile-entry-stage__mark">鑫</span>
          <div>
            <strong>当前任务</strong>
            <p>{{ current.workshop_name || bootstrap.workshop_name || '-' }} · {{ current.shift_name || current.shift_code || '-' }}</p>
          </div>
        </div>

        <div class="mobile-entry-stage__facts">
          <article v-for="fact in currentFacts" :key="fact.label" class="mobile-entry-stage__fact">
            <span>{{ fact.label }}</span>
            <strong>{{ fact.value }}</strong>
          </article>
        </div>

        <div v-if="isMachineBound" class="mobile-entry-stage__machine">
          <strong>{{ current.machine_name || bootstrap.machine_name || '-' }}</strong>
          <span>账号 {{ auth.user?.username || '-' }}</span>
        </div>

        <div class="mobile-entry-stage__role" data-testid="mobile-role-bucket">
          <span>当前角色</span>
          <strong>{{ roleBucketMeta.title }}</strong>
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

        <div class="mobile-entry-stage__summary-grid">
          <article class="mobile-entry-stage__summary-item">
            <span>今日班次</span>
            <strong>{{ current.shift_name || current.shift_code || '-' }}</strong>
          </article>
          <article class="mobile-entry-stage__summary-item">
            <span>待填报任务</span>
            <strong>{{ pendingTaskCount }}</strong>
          </article>
          <article class="mobile-entry-stage__summary-item">
            <span>已提交任务</span>
            <strong>{{ submittedTaskCount }}</strong>
          </article>
          <article class="mobile-entry-stage__summary-item">
            <span>异常待补项</span>
            <strong>{{ anomalyPendingCount }}</strong>
          </article>
          <article class="mobile-entry-stage__summary-item">
            <span>最近提交状态</span>
            <strong>{{ lastSubmitStatus }}</strong>
          </article>
        </div>

        <div class="mobile-entry-stage__quick-grid">
          <el-button type="primary" plain @click="goReport">快速填报</el-button>
          <el-button plain @click="goAdvancedReport">高级填报</el-button>
          <el-button plain :disabled="!ocrSupported || !current.shift_id" @click="goOcr">OCR</el-button>
          <el-button plain @click="goReportHistory">历史记录</el-button>
          <el-button plain @click="goDrafts">草稿箱</el-button>
        </div>

        <div class="mobile-entry-stage__ai">
          <span>智能提示</span>
          <ul>
            <li v-for="item in aiHints" :key="item">{{ item }}</li>
          </ul>
        </div>
      </div>
    </section>

    <el-card v-if="showReminderPanel" class="panel mobile-card">
      <template #header>提醒</template>
      <ReminderList :items="current.active_reminders || []" empty-text="当前没有提醒。" />
    </el-card>

    <MobileBottomNav />
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
import MobileBottomNav from './MobileBottomNav.vue'
import ReminderList from './ReminderList.vue'

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
const pendingTaskCount = computed(() => Number(current.value?.can_submit === false ? 0 : 1))
const submittedTaskCount = computed(() => ['submitted', 'reviewed', 'auto_confirmed'].includes(String(current.value?.report_status || '')) ? 1 : 0)
const anomalyPendingCount = computed(() => Number(current.value?.active_reminders?.length || 0))
const lastSubmitStatus = computed(() => formatStatusLabel(current.value?.report_status))
const aiHints = computed(() => {
  const hints = []
  const status = String(current.value?.report_status || '')
  const reminderCount = anomalyPendingCount.value

  if (status === 'returned') {
    hints.push('上次提交已被退回，建议先补齐异常说明和现场图片。')
  }
  if (status === 'late' || status === 'unreported') {
    hints.push('当前班次处于待补报状态，先提交关键原始值再补扩展字段。')
  }
  if (reminderCount > 0) {
    hints.push(`有 ${reminderCount} 条异常待补项，建议优先处理后再提交。`)
  }
  if (!hints.length) {
    hints.push('本班任务状态正常，提交后系统会自动汇总。')
  }
  return hints.slice(0, 3)
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

function goDrafts() {
  router.push({ name: 'entry-drafts' })
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
  padding: 12px;
  background:
    radial-gradient(circle at top left, rgba(14, 165, 233, 0.12), transparent 26%),
    radial-gradient(circle at bottom right, rgba(249, 115, 22, 0.08), transparent 26%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(246, 248, 252, 0.98));
}

.mobile-entry-stage__top {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
  gap: 6px;
}

.mobile-entry-stage__top h1 {
  margin: 4px 0 0;
  font-size: 22px;
  line-height: 1.22;
}

.mobile-entry-stage__top p {
  max-width: 28ch;
  line-height: 1.4;
}

.mobile-entry-stage__desktop-link {
  min-height: 36px;
  border-radius: 12px;
}

.mobile-entry-stage__top p,
.mobile-entry-stage__brand p,
.mobile-entry-stage__empty,
.mobile-entry-stage__fact span,
.mobile-entry-stage__machine span,
.mobile-entry-stage__role span,
.mobile-entry-stage__status span {
  margin: 0;
  color: var(--app-muted);
}

.mobile-entry-stage__empty {
  display: grid;
  gap: 8px;
  padding: 10px;
  border-radius: 14px;
  background: rgba(15, 23, 42, 0.04);
}

.mobile-entry-stage__empty p + p {
  font-size: 12px;
}

.mobile-entry-stage__action-row {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.mobile-entry-stage__action-row .el-button {
  border-radius: 14px;
  min-height: 38px;
  min-width: 122px;
}

.mobile-entry-stage__brand,
.mobile-entry-stage__cta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.mobile-entry-stage__brand {
  padding: 12px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.82);
  border: 1px solid rgba(148, 163, 184, 0.14);
}

.mobile-entry-stage__mark {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border-radius: 14px;
  background: linear-gradient(135deg, var(--text-main), var(--primary));
  color: #fff;
  font-size: 20px;
  font-weight: 800;
}

.mobile-entry-stage__brand strong,
.mobile-entry-stage__fact strong,
.mobile-entry-stage__machine strong,
.mobile-entry-stage__role strong,
.mobile-entry-stage__status strong {
  color: var(--app-text);
}

.mobile-entry-stage__facts {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.mobile-entry-stage__fact,
.mobile-entry-stage__machine,
.mobile-entry-stage__role,
.mobile-entry-stage__status {
  display: grid;
  gap: 4px;
  padding: 10px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.76);
  border: 1px solid rgba(148, 163, 184, 0.14);
}

.mobile-entry-stage__machine {
  background: linear-gradient(135deg, rgba(17, 24, 39, 0.04), rgba(29, 78, 216, 0.08));
}

.mobile-entry-stage__role {
  background: linear-gradient(135deg, rgba(2, 132, 199, 0.08), rgba(37, 99, 235, 0.06));
}

.mobile-entry-stage__cta .el-button {
  min-height: 46px;
  min-width: 142px;
  border-radius: 14px;
  font-size: 14px;
}

.mobile-entry-stage__summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
  gap: 8px;
}

.mobile-entry-stage__summary-item {
  display: grid;
  gap: 4px;
  padding: 10px;
  border-radius: 12px;
  background: rgba(248, 250, 252, 0.92);
  border: 1px solid rgba(148, 163, 184, 0.16);
}

.mobile-entry-stage__summary-item span {
  font-size: 12px;
  color: var(--app-muted);
}

.mobile-entry-stage__summary-item strong {
  font-size: 15px;
  color: var(--app-text);
}

.mobile-entry-stage__quick-grid {
  display: grid;
  gap: 8px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.mobile-entry-stage__quick-grid .el-button {
  min-height: 40px;
  border-radius: 12px;
}

.mobile-entry-stage__ai {
  display: grid;
  gap: 6px;
  padding: 10px;
  border-radius: 12px;
  background: rgba(239, 246, 255, 0.9);
  border: 1px solid rgba(59, 130, 246, 0.18);
}

.mobile-entry-stage__ai span {
  font-size: 12px;
  color: var(--app-muted);
}

.mobile-entry-stage__ai ul {
  margin: 0;
  padding-left: 18px;
  display: grid;
  gap: 4px;
}

@media (max-width: 720px) {
  .mobile-entry-stage__top,
  .mobile-entry-stage__cta,
  .mobile-entry-stage__brand {
    grid-template-columns: 1fr;
    display: grid;
  }

  .mobile-entry-stage__action-row {
    display: grid;
    grid-template-columns: 1fr;
  }

  .mobile-entry-stage__facts {
    grid-template-columns: 1fr;
  }

  .mobile-entry-stage__quick-grid {
    grid-template-columns: 1fr;
  }
}
</style>
