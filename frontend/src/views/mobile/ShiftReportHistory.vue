<template>
  <div class="mobile-shell history-log" data-testid="entry-history-page" data-visual-pass="stitch-image2-second-pass-mobile">
    <div class="history-log__hero mobile-top">
      <div class="history-log__hero-copy">
        <span class="history-log__eyebrow">ALL-DAY LOG</span>
        <h1>历史填报</h1>
        <p>按整日查看有权限的录入记录 · 可恢复查看</p>
      </div>
      <div class="history-log__hero-stack">
        <div class="history-log__readouts">
          <article class="history-log__readout">
            <span>记录</span>
            <strong>{{ items.length }}</strong>
          </article>
          <article class="history-log__readout">
            <span>日期</span>
            <strong>{{ businessDate }}</strong>
          </article>
        </div>
        <div class="header-actions history-log__controls">
          <el-date-picker
            v-model="businessDate"
            type="date"
            value-format="YYYY-MM-DD"
            size="small"
            class="mobile-history-date"
            @change="load"
          />
          <el-button plain class="mobile-inline-action history-log__refresh" @click="load">刷新</el-button>
        </div>
      </div>
    </div>

    <div v-if="loading" class="history-log__state mobile-inline-state panel">
      <span class="history-log__state-orbit" aria-hidden="true"></span>
      <p>正在加载历史记录…</p>
      <small>扫描整日录入链路</small>
      <el-button
        type="primary"
        plain
        class="mobile-inline-action"
        :loading="loading"
        @click="load"
      >
        重试加载
      </el-button>
      <el-button class="mobile-inline-action" plain @click="goEntry">返回首页</el-button>
    </div>

    <div v-else-if="pageError" class="history-log__state history-log__state--error mobile-inline-state panel">
      <span class="history-log__state-orbit" aria-hidden="true"></span>
      <p>{{ pageError }}</p>
      <el-button
        type="primary"
        plain
        class="mobile-inline-action"
        @click="load"
      >
        重试加载
      </el-button>
      <el-button plain class="mobile-inline-action" @click="goEntry">返回首页</el-button>
    </div>

    <section v-else class="history-log__panel panel mobile-card">
      <header class="history-log__panel-head">
        <div>
          <span class="history-log__eyebrow">RECORD TIMELINE</span>
          <strong>最近记录</strong>
        </div>
        <span class="history-log__panel-count">{{ visibleCountLabel }}</span>
      </header>

      <div v-if="!items.length" class="history-log__empty mobile-placeholder">
        <span class="history-log__empty-node" aria-hidden="true"></span>
        <strong>暂无历史填报记录。</strong>
      </div>
      <div v-else class="history-log__list mobile-history-list">
        <article
          v-for="(item, index) in items"
          :key="historyItemKey(item)"
          class="history-log__record mobile-history-item"
          data-testid="entry-history-record"
          :style="{ '--history-index': index }"
        >
          <div class="history-log__record-head">
            <span class="history-log__status" :class="historyToneClass(item)">
              <i aria-hidden="true"></i>{{ sourceTagLabel(item) }}
            </span>
            <span class="history-log__seq">LOG {{ historySeq(index) }}</span>
          </div>

          <div class="mobile-history-main">
            <div>
              <div class="history-log__title mobile-history-title">
                {{ item.business_date }} / {{ formatShiftLabel(item.shift_name || item.shift_code, '-') }}
              </div>
              <div class="history-log__meta mobile-history-meta">
                {{ historyActorMeta(item) }}
              </div>
            </div>
            <div class="mobile-history-tags">
              <el-tag :type="statusTagType(item.report_status)" effect="light">
                {{ formatStatusLabel(item.report_status) }}
              </el-tag>
            </div>
          </div>
          <div v-if="isCoilHistoryItem(item)" class="mobile-history-grid">
            <div><span>随行卡</span><strong>{{ item.tracking_card_no || '-' }}</strong></div>
            <div><span>投料</span><strong>{{ formatNumber(item.input_weight) }}</strong></div>
            <div><span>下机</span><strong>{{ formatNumber(item.output_weight) }}</strong></div>
            <div><span>废料</span><strong>{{ formatNumber(item.scrap_weight) }}</strong></div>
          </div>
          <div v-else class="mobile-history-grid">
            <div><span>产量</span><strong>{{ formatNumber(item.output_weight) }}</strong></div>
            <div><span>日电耗</span><strong>{{ formatNumber(item.electricity_daily) }}</strong></div>
            <div><span>日气耗</span><strong>{{ formatNumber(item.gas_daily) }}</strong></div>
            <div><span>图片</span><strong>{{ item.photo_file_name || '未上传' }}</strong></div>
          </div>
          <div v-if="item.created_by_name" class="mobile-history-note">录入人：{{ item.created_by_name }}</div>
          <div v-if="item.has_exception || item.exception_type" class="mobile-history-note">
            异常：{{ item.exception_type || '已标记异常' }}
          </div>
          <div v-if="item.returned_reason" class="mobile-history-note">退回原因：{{ item.returned_reason }}</div>
          <div class="mobile-history-actions">
            <span class="mobile-history-meta">最近保存：{{ item.last_saved_at || '-' }}</span>
            <el-button text type="primary" class="history-log__action" @click="openDetail(item)">{{ actionLabel(item) }}</el-button>
          </div>
        </article>
      </div>
    </section>

  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import { fetchMobileHistory } from '../../api/mobile'
import { formatNumber, formatShiftLabel, formatStatusLabel } from '../../utils/display'
import { useAuthStore } from '../../stores/auth'
import { resolveTransitionRoleBucket } from '../../utils/mobileTransition'
import { inferBusinessDate } from '../../utils/shiftClock'

const router = useRouter()
const auth = useAuthStore()
const items = ref([])
const loading = ref(true)
const pageError = ref('')
const businessDate = ref(inferBusinessDate())
const visibleCountLabel = computed(() => `${items.value.length} 条`)

const advancedRoleBuckets = [
  'machine_operator',
  'energy_stat',
  'quality_owner',
  'planning_owner',
  'energy_chief',
  'storage_owner',
  'shipment_outflow_owner',
  'recovery_owner',
  'overhaul_owner'
]

const currentUserRoleBucket = resolveTransitionRoleBucket({
  role: auth.role,
  isMachineBound: Boolean(auth.isMachineBound)
})

function isAdvancedHistoryItem(item) {
  const roleBucket = item?.role_bucket || item?.report_role_bucket || currentUserRoleBucket
  return advancedRoleBuckets.includes(roleBucket)
}

function resolveDetailRouteName(item = {}) {
  return isAdvancedHistoryItem(item) ? 'mobile-unified-entry' : 'mobile-report-form'
}

function statusTagType(status) {
  if (status === 'submitted' || status === 'approved') return 'success'
  if (status === 'returned') return 'danger'
  if (status === 'draft') return 'warning'
  return 'info'
}

function historyItemKey(item) {
  return `${item.source_type || 'shift_report'}-${item.id}`
}

function isCoilHistoryItem(item) {
  return item?.source_type === 'mobile_coil'
}

function sourceTagLabel(item) {
  if (isCoilHistoryItem(item)) return '主操逐卷'
  if (item?.source_type === 'owner_daily') return '专项每日'
  return '班次汇总'
}

function historySeq(index) {
  return String(index + 1).padStart(2, '0')
}

function historyToneClass(item) {
  if (item?.report_status === 'returned') return 'is-danger'
  if (item?.report_status === 'draft') return 'is-warning'
  if (item?.source_type === 'owner_daily') return 'is-owner'
  return 'is-normal'
}

function historyActorMeta(item) {
  const parts = [
    item.workshop_name,
    item.machine_name || item.team_name,
    item.created_by_name
  ].filter(Boolean)
  return parts.length ? parts.join(' · ') : '-'
}

function actionLabel(item) {
  return isCoilHistoryItem(item) ? '继续录入' : '继续查看'
}

async function load() {
  loading.value = true
  pageError.value = ''
  try {
    const data = await fetchMobileHistory({
      business_date: businessDate.value,
      all_day: true,
      limit: 30,
    })
    items.value = data.items || []
  } catch (error) {
    pageError.value = requestErrorMessage(error, '加载历史记录失败，请重试。')
    items.value = []
  } finally {
    loading.value = false
  }
}

function requestErrorMessage(error, fallback = '操作失败') {
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

function openDetail(item) {
  const routeName = resolveDetailRouteName(item)
  if (routeName === 'mobile-unified-entry') {
    router.push({
      name: routeName,
      query: {
        businessDate: item.business_date,
        shiftId: item.shift_id
      }
    })
    return
  }
  router.push({
    name: routeName,
    params: {
      businessDate: item.business_date,
      shiftId: item.shift_id
    }
  })
}

function goEntry() {
  router.push({ name: 'mobile-entry' })
}

onMounted(load)
</script>

<style scoped>
.history-log {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 14px;
  overflow-x: hidden;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.history-log::before {
  content: '';
  position: fixed;
  inset: 0 auto 0 50%;
  z-index: 0;
  width: min(100%, 600px);
  pointer-events: none;
  background:
    radial-gradient(circle at 80% 2%, rgba(0, 242, 255, 0.14), transparent 34%),
    linear-gradient(120deg, transparent 0 42%, rgba(0, 242, 255, 0.07) 47%, transparent 52% 100%),
    repeating-linear-gradient(0deg, transparent 0 17px, rgba(0, 242, 255, 0.035) 18px 19px);
  opacity: 0.72;
  transform: translateX(-50%);
}

.history-log > * {
  position: relative;
  z-index: 1;
}

.mobile-top {
  grid-template-columns: minmax(0, 1fr);
  align-items: stretch;
}

.history-log__hero,
.history-log__panel,
.history-log__state,
.history-log__record {
  position: relative;
  overflow: hidden;
}

.history-log__hero {
  gap: 16px;
  padding: 18px;
  border-radius: 18px;
}

.history-log__hero::after,
.history-log__panel::after,
.history-log__record::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(110deg, transparent 0 40%, rgba(0, 242, 255, 0.12) 50%, transparent 60% 100%);
  opacity: 0;
  transform: translateX(-72%);
}

.history-log__hero::after {
  opacity: 0.14;
}

.history-log__hero-copy {
  min-width: 0;
}

.history-log__hero-stack {
  display: grid;
  gap: 10px;
  width: 100%;
}

.history-log__eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  margin-bottom: 8px;
  color: rgba(0, 242, 255, 0.86);
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 0.16em;
}

.history-log__eyebrow::before {
  content: '';
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #00f2ff;
  box-shadow: 0 0 16px rgba(0, 242, 255, 0.72);
}

.mobile-top h1,
.mobile-top p {
  writing-mode: horizontal-tb;
}

.mobile-top h1 {
  margin: 0;
  font-size: 30px;
  line-height: 1.05;
  letter-spacing: -0.04em;
}

.mobile-top p {
  margin: 8px 0 0;
}

.history-log__readouts {
  display: grid;
  grid-template-columns: 0.72fr 1.28fr;
  gap: 10px;
}

.history-log__readout {
  min-width: 0;
  padding: 10px 12px;
  border: 1px solid rgba(0, 242, 255, 0.18);
  border-radius: 14px;
  background: rgba(2, 10, 22, 0.4);
}

.history-log__readout span,
.history-log__seq,
.history-log__panel-count {
  display: block;
  color: rgba(185, 218, 235, 0.66);
  font-size: 10px;
  font-weight: 850;
  letter-spacing: 0.12em;
}

.history-log__readout strong {
  display: block;
  margin-top: 4px;
  color: #e8fdff;
  font-size: 20px;
  font-weight: 950;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.header-actions {
  width: 100%;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
}

.mobile-history-date {
  width: 100%;
}

.history-log__controls {
  gap: 10px;
}

.mobile-history-tags {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 6px;
  flex-wrap: wrap;
}

.mobile-inline-action {
  position: relative;
  min-height: 44px;
  overflow: hidden;
  touch-action: manipulation;
}

.history-log__refresh::after,
.history-log__action::after {
  content: '';
  position: absolute;
  inset: -1px;
  pointer-events: none;
  background: linear-gradient(110deg, transparent, rgba(255, 255, 255, 0.3), transparent);
  opacity: 0;
  transform: translateX(-100%);
}

.history-log__panel {
  padding: 12px;
  border-radius: 18px;
}

.history-log__panel-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 4px 4px 14px;
}

.history-log__panel-head strong {
  display: block;
  color: #e8fdff;
  font-size: 18px;
  font-weight: 950;
}

.history-log__panel-count {
  padding-top: 4px;
  text-align: right;
}

.history-log__empty,
.history-log__state {
  display: grid;
  place-items: center;
  min-height: 220px;
  gap: 8px;
  text-align: center;
}

.history-log__empty-node,
.history-log__state-orbit {
  width: 74px;
  height: 74px;
  border-radius: 50%;
  border: 1px solid rgba(0, 242, 255, 0.34);
  background:
    radial-gradient(circle, rgba(0, 242, 255, 0.2) 0 22%, transparent 23%),
    conic-gradient(from 120deg, rgba(0, 242, 255, 0.78), transparent 32%, rgba(255, 171, 0, 0.42), transparent 72%, rgba(0, 242, 255, 0.78));
  box-shadow: 0 0 38px rgba(0, 242, 255, 0.14);
}

.history-log__empty strong,
.history-log__state p {
  margin: 0;
  color: #e8fdff;
  font-size: 18px;
  font-weight: 900;
}

.history-log__state small {
  color: rgba(185, 218, 235, 0.68);
  font-size: 12px;
}

.history-log__state--error .history-log__state-orbit {
  border-color: rgba(255, 92, 53, 0.42);
  background:
    radial-gradient(circle, rgba(255, 92, 53, 0.2) 0 22%, transparent 23%),
    conic-gradient(from 120deg, rgba(255, 92, 53, 0.78), transparent 38%, rgba(0, 242, 255, 0.46), transparent 76%, rgba(255, 92, 53, 0.78));
}

.history-log__list {
  gap: 12px;
}

.history-log__record {
  padding: 14px;
  border-radius: 16px;
  animation: historyLogCardIn 420ms ease both;
  animation-delay: calc(var(--history-index) * 70ms);
}

.history-log__record-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
}

.history-log__status {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: #dffbff;
  font-size: 11px;
  font-weight: 950;
  letter-spacing: 0.08em;
}

.history-log__status i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #00f2ff;
  box-shadow: 0 0 0 4px rgba(0, 242, 255, 0.12), 0 0 18px rgba(0, 242, 255, 0.72);
}

.history-log__status.is-warning i,
.history-log__status.is-owner i {
  background: #ffab00;
  box-shadow: 0 0 0 4px rgba(255, 171, 0, 0.12), 0 0 18px rgba(255, 171, 0, 0.68);
}

.history-log__status.is-danger i {
  background: #ff5c35;
  box-shadow: 0 0 0 4px rgba(255, 92, 53, 0.12), 0 0 18px rgba(255, 92, 53, 0.7);
}

.history-log__seq {
  text-align: right;
}

.history-log__title {
  font-size: 22px;
  font-weight: 950;
  letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums;
}

.history-log__meta {
  margin-top: 4px;
  font-weight: 700;
}

.history-log__action {
  position: relative;
  overflow: hidden;
  min-height: 44px;
  padding-inline: 12px;
  border-radius: 12px;
}

@media (hover: hover) {
  .history-log__refresh:hover::after,
  .history-log__action:hover::after {
    animation: historyLogButtonSweep 620ms ease;
  }

  .history-log__record:hover {
    border-color: rgba(0, 242, 255, 0.32);
  }
}

.history-log__refresh:active,
.history-log__action:active {
  transform: scale(0.97);
}

@keyframes historyLogButtonSweep {
  0% {
    opacity: 0;
    transform: translateX(-100%);
  }
  45% {
    opacity: 1;
  }
  100% {
    opacity: 0;
    transform: translateX(100%);
  }
}

@keyframes historyLogCardIn {
  from {
    opacity: 0;
    transform: translate3d(0, 12px, 0);
  }
  to {
    opacity: 1;
    transform: translate3d(0, 0, 0);
  }
}

@media (max-width: 480px) {
  .header-actions {
    grid-template-columns: minmax(0, 1fr);
  }

  .mobile-inline-action {
    width: 100%;
    min-height: 44px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .history-log__record {
    animation: none;
  }
}
</style>
