<template>
  <div class="mobile-shell mobile-shell--entry" data-testid="mobile-entry">
    <div class="mobile-top">
      <div>
        <div class="mobile-kicker">岗位直录</div>
        <h1>{{ pageTitle }}</h1>
        <p>{{ pageSubtitle }}</p>
      </div>
      <el-button v-if="auth.canAccessDesktop" plain @click="goDesktop">进入后台</el-button>
    </div>

    <el-alert
      v-if="authenticating"
      title="正在通过企业微信校验身份并进入手机填报入口，请稍候。"
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
      v-if="!authenticating && !authError && (bootstrap.phase_notice || bootstrap.data_entry_mode === 'manual_only')"
      :title="bootstrap.phase_notice || '当前阶段先由主操手工录入，系统自动校验、汇总和催报。'"
      type="info"
      show-icon
      :closable="false"
      class="panel"
    />

    <el-card class="panel mobile-card mobile-entry-card" data-testid="mobile-current-shift">
      <div v-if="authenticating" class="mobile-placeholder">正在校验企业微信身份并加载当前班次...</div>
      <div v-else-if="authError" class="mobile-placeholder">
        <div>{{ authError }}</div>
        <div class="mobile-actions mobile-actions--entry">
          <el-button type="primary" plain @click="goLogin">改用账号登录</el-button>
        </div>
      </div>
      <div v-else-if="loading" class="mobile-placeholder">正在加载当前班次与任务状态...</div>
      <div v-else-if="!current.can_submit" class="mobile-placeholder">
        {{ current.ownership_note || '当前账号暂未绑定可填报班次，请先确认车间、班组和排班配置。' }}
      </div>
      <template v-else>
        <div class="mobile-entry-card__hero">
          <div class="mobile-entry-card__brand">
            <span class="mobile-entry-card__mark">鑫</span>
            <div>
              <div class="mobile-entry-card__brand-title">鑫泰铝业</div>
              <div class="mobile-entry-card__brand-copy">只录本岗原始值，后面交给系统。</div>
            </div>
          </div>

          <div class="mobile-entry-card__identity">
            <span class="mobile-entry-card__eyebrow">当前岗位</span>
            <strong data-testid="mobile-role-bucket">{{ roleBucketMeta.title }}</strong>
            <p>{{ transitionMapping.new_action }}</p>
          </div>

          <div class="mobile-entry-card__facts">
            <div v-for="fact in currentFacts" :key="fact.label" class="mobile-entry-card__fact">
              <span>{{ fact.label }}</span>
              <strong>{{ fact.value }}</strong>
            </div>
          </div>

          <div class="mobile-entry-card__brief">
            <span>本岗负责</span>
            <strong>{{ transitionMapping.evidence_label }}</strong>
            <p>{{ roleBucketMeta.subtitle }}</p>
          </div>
        </div>

        <div class="mobile-agent-grid">
          <article
            v-for="squad in agentSquads"
            :key="squad.title"
            class="mobile-agent-card"
          >
            <div class="mobile-agent-card__top">
              <span>{{ squad.kicker }}</span>
              <strong>{{ squad.title }}</strong>
            </div>
            <p>{{ squad.summary }}</p>
            <div class="mobile-agent-card__tags">
              <span v-for="item in squad.items" :key="item">{{ item }}</span>
            </div>
          </article>
        </div>

        <div v-if="isMachineBound" class="mobile-machine-banner">
          <div class="mobile-machine-banner__title">
            {{ current.workshop_name || bootstrap.workshop_name || '-' }} / {{ current.machine_name || bootstrap.machine_name || '-' }} / {{ current.shift_name || current.shift_code || '-' }}
          </div>
          <div class="mobile-machine-banner__meta">
            <span>业务日期 {{ current.business_date }}</span>
            <span>账号 {{ auth.user?.username || '-' }}</span>
            <span>状态 {{ formatStatusLabel(current.report_status) }}</span>
          </div>
        </div>

        <div class="mobile-actions mobile-actions--entry">
          <template v-if="isMachineBound">
            <el-button type="primary" size="large" data-testid="mobile-go-report" @click="goReport">
              {{ transitionMapping.primary_cta }}
            </el-button>
          </template>
          <template v-else>
            <el-button type="primary" size="large" data-testid="mobile-go-report" @click="goReport">
              {{ transitionMapping.primary_cta }}
            </el-button>
          </template>
        </div>
      </template>
    </el-card>

    <el-card v-if="showReminderPanel" class="panel mobile-card">
      <template #header>当前提醒</template>
      <ReminderList :items="current.active_reminders || []" empty-text="当前班次没有催报或迟报记录。" />
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
const authError = ref('')
const bootstrap = ref({})
const current = ref({})
const ocrSupported = ref(false)

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
const entryModeLabel = computed(() => {
  const mode = bootstrap.value?.data_entry_mode
  if (mode === 'manual_only') return '主操手工直录'
  if (mode === 'scan_assisted') return '扫码辅助录入'
  if (mode === 'mes_assisted') return 'MES 辅助录入'
  return '-'
})
const currentFacts = computed(() => [
  { label: '业务日期', value: current.value?.business_date || '-' },
  { label: '班次', value: current.value?.shift_name || current.value?.shift_code || '-' },
  { label: '车间', value: current.value?.workshop_name || bootstrap.value?.workshop_name || '-' },
  {
    label: isMachineBound.value ? '机台' : '班组',
    value: isMachineBound.value
      ? (current.value?.machine_name || bootstrap.value?.machine_name || '-')
      : (current.value?.team_name || '-')
  },
  { label: '录入方式', value: entryModeLabel.value },
  { label: '当前状态', value: formatStatusLabel(current.value?.report_status) },
  { label: '当前负责人', value: current.value?.leader_name || auth.displayName }
])
const agentSquads = computed(() => [
  {
    kicker: 'AI 智能体联动',
    title: '采集清洗小队',
    summary: `接住${transitionMapping.value.evidence_label}，自动做字段校验、缺报提醒、异常退回和班次留痕。`,
    items: ['字段校验', '缺报提醒', '异常退回', '班次留痕']
  },
  {
    kicker: '终端可视化',
    title: '分析决策小队',
    summary: '把同班次原始值变成驾驶舱、日报、预警和月累计视图，直接给管理层看结果。',
    items: ['厂长驾驶舱', '日报摘要', '异常预警', '月累计']
  }
])
const showDebugBootstrap = computed(() => (
  auth.isLoggedIn &&
  isDev &&
  route.query.debug === '1' &&
  Boolean(bootstrap.value.current_identity_source)
))

function resolveWecomCode() {
  return typeof route.query.code === 'string' ? route.query.code.trim() : ''
}

function parseErrorMessage(error, fallback) {
  const detail = error?.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || item).join('；')
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
    wecom_h5: '企业微信工作台入口',
    dingtalk_h5: '兼容钉钉入口',
    web_debug: '浏览器调试入口'
  }
  const identitySourceMap = {
    wecom_oauth: '企业微信免登',
    dingtalk_runtime: '企业微信运行时',
    dingtalk_binding: '兼容钉钉身份',
    signed_query: '企业微信签名参数',
    dev_fallback: '本地调试'
  }
  const entryMode = entryModeMap[bootstrap.value.entry_mode] || '浏览器调试入口'
  const identitySource = identitySourceMap[bootstrap.value.current_identity_source] || '本地调试'
  return `当前入口：${entryMode}；身份来源：${identitySource}；数据范围：${scopeLabel}`
})

async function ensureWecomSession() {
  const code = resolveWecomCode()
  if (auth.isLoggedIn || !code) return true

  authenticating.value = true
  authError.value = ''
  try {
    await auth.wecomLogin(code)
    const nextQuery = { ...route.query }
    delete nextQuery.code
    delete nextQuery.state
    await router.replace({ name: 'mobile-entry', query: nextQuery })
    return true
  } catch (error) {
    authError.value = parseErrorMessage(error, '企业微信登录失败，请联系管理员检查账号映射。')
    return false
  } finally {
    authenticating.value = false
  }
}

async function load() {
  const ready = await ensureWecomSession()
  if (!ready) {
    loading.value = false
    return
  }
  loading.value = true
  authError.value = ''
  try {
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
    authError.value = parseErrorMessage(error, '加载当前班次失败，请稍后重试或改用账号登录。')
  } finally {
    loading.value = false
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

function goDesktop() {
  router.push({ name: 'factory-dashboard' })
}

function goLogin() {
  router.push({ name: 'login', query: { redirect: '/mobile' } })
}

onMounted(load)
</script>
