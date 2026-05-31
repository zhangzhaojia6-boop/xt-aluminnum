<template>
  <div class="mobile-shell entry-drafts" data-testid="entry-drafts-page">
    <div class="entry-drafts__hero mobile-top">
      <div class="entry-drafts__hero-copy">
        <span class="entry-drafts__eyebrow">DRAFT RECOVERY BAY</span>
        <h1>草稿箱</h1>
        <p>本机暂存 · 恢复后继续提交</p>
      </div>
      <div class="entry-drafts__hero-actions">
        <article class="entry-drafts__readout">
          <span>草稿</span>
          <strong>{{ drafts.length }}</strong>
        </article>
        <article class="entry-drafts__readout">
          <span>最近保存</span>
          <strong>{{ latestSavedLabel }}</strong>
        </article>
        <el-button plain class="mobile-inline-action entry-drafts__refresh" @click="loadDrafts">刷新</el-button>
      </div>
    </div>

    <section class="entry-drafts__panel panel mobile-card">
      <div v-if="!drafts.length" class="entry-drafts__empty template-empty">
        <span class="entry-drafts__empty-ring" aria-hidden="true"></span>
        <strong>暂无草稿</strong>
        <small>本机没有待恢复记录</small>
      </div>

      <div v-else class="entry-drafts__list mobile-history-list">
        <article
          v-for="(item, index) in drafts"
          :key="item.key"
          class="entry-drafts__card mobile-history-item"
          :style="{ '--draft-index': index }"
        >
          <div class="entry-drafts__card-head">
            <span class="entry-drafts__status"><i aria-hidden="true"></i>未提交</span>
            <span class="entry-drafts__seq">DRAFT {{ draftSeq(index) }}</span>
          </div>
          <div class="mobile-history-main">
            <div>
              <div class="entry-drafts__title mobile-history-title">{{ item.businessDate || '-' }}</div>
              <div class="entry-drafts__meta-line">{{ item.shiftLabel }}</div>
            </div>
            <el-tag type="warning" effect="light">待恢复</el-tag>
          </div>
          <dl class="entry-drafts__meta">
            <div>
              <dt>保存时间</dt>
              <dd>{{ item.savedAtLabel }}</dd>
            </div>
            <div>
              <dt>草稿范围</dt>
              <dd>{{ item.summary }}</dd>
            </div>
          </dl>
          <div class="entry-drafts__actions header-actions">
            <el-button type="primary" plain class="entry-drafts__continue" @click="resumeDraft(item)">继续填写</el-button>
            <el-button type="danger" plain class="entry-drafts__delete" @click="removeDraft(item.key)">删除</el-button>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'

const router = useRouter()
const drafts = ref([])
const latestSavedLabel = computed(() => drafts.value[0]?.savedAtLabel || '暂无')

function draftSeq(index) {
  return String(index + 1).padStart(2, '0')
}

function parseDrafts() {
  const entries = []
  if (typeof localStorage === 'undefined') return entries
  const keys = Object.keys(localStorage).filter((key) => key.startsWith('draft:'))
  for (const key of keys) {
    try {
      const payload = JSON.parse(localStorage.getItem(key) || 'null')
      if (!payload?.data) continue
      const segments = key.split(':')
      const businessDate = segments[3] || ''
      const shiftId = segments[2] || ''
      const savedAt = payload.saved_at ? new Date(payload.saved_at) : null
      const savedAtLabel = savedAt && !Number.isNaN(savedAt.getTime())
        ? savedAt.toLocaleString('zh-CN', { hour12: false })
        : '未知时间'
      entries.push({
        key,
        businessDate,
        shiftId,
        savedAt: payload.saved_at || '',
        savedAtLabel,
        shiftLabel: `班次 ${shiftId || '-'}`,
        summary: `${businessDate || '-'} / 班次 ${shiftId || '-'}`
      })
    } catch {
      // Ignore malformed draft item.
    }
  }
  entries.sort((a, b) => String(b.savedAt).localeCompare(String(a.savedAt)))
  return entries
}

function loadDrafts() {
  drafts.value = parseDrafts()
}

function removeDraft(key) {
  localStorage.removeItem(key)
  loadDrafts()
}

async function resumeDraft(item) {
  if (!item.businessDate || !item.shiftId) {
    ElMessage.warning('草稿缺少班次信息，无法恢复')
    return
  }
  const confirmed = await ElMessageBox.confirm('继续填写将打开对应班次页面。', '恢复草稿', {
    type: 'info',
    confirmButtonText: '继续填写',
    cancelButtonText: '取消'
  }).then(() => true).catch(() => false)
  if (!confirmed) return
  router.push({
    name: 'mobile-unified-entry',
    query: {
      businessDate: item.businessDate,
      shiftId: item.shiftId
    }
  })
}

onMounted(loadDrafts)
</script>

<style scoped>
.entry-drafts {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.entry-drafts::before {
  content: '';
  position: fixed;
  inset: 0 auto 0 50%;
  z-index: 0;
  width: min(100%, 600px);
  pointer-events: none;
  background:
    radial-gradient(circle at 18% 4%, rgba(0, 242, 255, 0.16), transparent 34%),
    linear-gradient(120deg, transparent 0 44%, rgba(0, 242, 255, 0.08) 48%, transparent 52% 100%);
  opacity: 0.65;
  transform: translateX(-50%);
}

.entry-drafts > * {
  position: relative;
  z-index: 1;
}

.entry-drafts__hero {
  position: relative;
  overflow: hidden;
  gap: 16px;
  padding: 18px;
  border-radius: 18px;
}

.entry-drafts__hero::after,
.entry-drafts__panel::after,
.entry-drafts__card::after {
  content: '';
  position: absolute;
  inset: 0;
  pointer-events: none;
  background: linear-gradient(110deg, transparent 0 42%, rgba(0, 242, 255, 0.14) 50%, transparent 58% 100%);
  opacity: 0;
  transform: translateX(-70%);
}

.entry-drafts__hero::after {
  animation: entryDraftScan 5.6s ease-in-out infinite;
}

.entry-drafts__hero-copy {
  min-width: 0;
}

.entry-drafts__eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
  color: rgba(0, 242, 255, 0.86);
  font-size: 10px;
  font-weight: 900;
  letter-spacing: 0.16em;
}

.entry-drafts__eyebrow::before {
  content: '';
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #00f2ff;
  box-shadow: 0 0 16px rgba(0, 242, 255, 0.76);
}

.entry-drafts__hero h1 {
  margin: 0;
  font-size: 30px;
  line-height: 1.05;
  letter-spacing: -0.04em;
}

.entry-drafts__hero p {
  margin: 8px 0 0;
}

.entry-drafts__hero-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  width: 100%;
}

.entry-drafts__readout {
  min-width: 0;
  padding: 10px 12px;
  border: 1px solid rgba(0, 242, 255, 0.18);
  border-radius: 14px;
  background: rgba(2, 10, 22, 0.38);
}

.entry-drafts__readout span,
.entry-drafts__meta dt,
.entry-drafts__seq {
  display: block;
  color: rgba(185, 218, 235, 0.66);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.12em;
}

.entry-drafts__readout strong {
  display: block;
  margin-top: 4px;
  color: #e8fdff;
  font-size: 20px;
  font-weight: 950;
  line-height: 1;
  font-variant-numeric: tabular-nums;
}

.entry-drafts__refresh {
  grid-column: 1 / -1;
  position: relative;
  overflow: hidden;
}

.entry-drafts__refresh::after,
.entry-drafts__continue::after,
.entry-drafts__delete::after {
  content: '';
  position: absolute;
  inset: -1px;
  pointer-events: none;
  background: linear-gradient(110deg, transparent, rgba(255, 255, 255, 0.26), transparent);
  opacity: 0;
  transform: translateX(-100%);
}

.entry-drafts__panel {
  position: relative;
  overflow: hidden;
  padding: 12px;
  border-radius: 18px;
}

.entry-drafts__empty {
  position: relative;
  display: grid;
  place-items: center;
  min-height: 220px;
  gap: 8px;
  overflow: hidden;
  text-align: center;
}

.entry-drafts__empty-ring {
  width: 76px;
  height: 76px;
  border-radius: 50%;
  border: 1px solid rgba(0, 242, 255, 0.34);
  background:
    radial-gradient(circle, rgba(0, 242, 255, 0.2) 0 24%, transparent 25%),
    conic-gradient(from 120deg, rgba(0, 242, 255, 0.78), transparent 32%, rgba(255, 171, 0, 0.44), transparent 72%, rgba(0, 242, 255, 0.78));
  box-shadow: 0 0 38px rgba(0, 242, 255, 0.14);
  animation: entryDraftRing 5s linear infinite;
}

.entry-drafts__empty strong {
  color: #e8fdff;
  font-size: 20px;
  font-weight: 900;
}

.entry-drafts__empty small {
  color: rgba(185, 218, 235, 0.68);
  font-size: 12px;
}

.entry-drafts__list {
  gap: 12px;
}

.entry-drafts__card {
  position: relative;
  overflow: hidden;
  padding: 14px;
  border-radius: 16px;
  animation: entryDraftCardIn 420ms ease both;
  animation-delay: calc(var(--draft-index) * 70ms);
}

.entry-drafts__card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 12px;
}

.entry-drafts__status {
  display: inline-flex;
  align-items: center;
  gap: 7px;
  color: #ffca63;
  font-size: 11px;
  font-weight: 900;
  letter-spacing: 0.08em;
}

.entry-drafts__status i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ffab00;
  box-shadow: 0 0 0 4px rgba(255, 171, 0, 0.12), 0 0 18px rgba(255, 171, 0, 0.7);
  animation: entryDraftLed 1.8s ease-in-out infinite;
}

.entry-drafts__seq {
  text-align: right;
}

.entry-drafts__title {
  font-size: 24px;
  font-weight: 950;
  letter-spacing: -0.02em;
  font-variant-numeric: tabular-nums;
}

.entry-drafts__meta-line {
  margin-top: 4px;
  color: rgba(185, 218, 235, 0.74);
  font-size: 13px;
  font-weight: 700;
}

.entry-drafts__meta {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 8px;
  margin: 12px 0;
  padding: 0;
}

.entry-drafts__meta div {
  display: grid;
  gap: 4px;
  padding: 10px 12px;
  border: 1px solid rgba(0, 242, 255, 0.12);
  border-radius: 12px;
  background: rgba(1, 10, 22, 0.34);
}

.entry-drafts__meta dd {
  margin: 0;
  color: #e8fdff;
  font-size: 13px;
  font-weight: 800;
  word-break: break-all;
}

.entry-drafts__actions {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(92px, 0.42fr);
  gap: 10px;
}

.entry-drafts :deep(.entry-drafts__continue.el-button),
.entry-drafts :deep(.entry-drafts__delete.el-button),
.entry-drafts :deep(.entry-drafts__refresh.el-button) {
  position: relative;
  min-height: 44px;
  border-radius: 12px;
  font-weight: 900;
}

.entry-drafts :deep(.entry-drafts__continue.el-button) {
  border-color: rgba(0, 242, 255, 0.42);
  background: rgba(0, 242, 255, 0.12);
  color: #e8fdff;
}

.entry-drafts :deep(.entry-drafts__delete.el-button) {
  border-color: rgba(255, 92, 53, 0.34);
  background: rgba(255, 92, 53, 0.08);
  color: #ffb49e;
}

@media (hover: hover) {
  .entry-drafts__refresh:hover::after,
  .entry-drafts__continue:hover::after,
  .entry-drafts__delete:hover::after {
    animation: entryDraftButtonSweep 620ms ease;
  }

  .entry-drafts__card:hover {
    border-color: rgba(0, 242, 255, 0.32);
  }
}

.entry-drafts__refresh:active,
.entry-drafts__continue:active,
.entry-drafts__delete:active {
  transform: scale(0.97);
}

@keyframes entryDraftScan {
  0%, 64% {
    opacity: 0;
    transform: translateX(-70%);
  }
  76% {
    opacity: 1;
  }
  100% {
    opacity: 0;
    transform: translateX(70%);
  }
}

@keyframes entryDraftButtonSweep {
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

@keyframes entryDraftCardIn {
  from {
    opacity: 0;
    transform: translate3d(0, 12px, 0);
  }
  to {
    opacity: 1;
    transform: translate3d(0, 0, 0);
  }
}

@keyframes entryDraftLed {
  0%, 100% {
    transform: scale(0.9);
    opacity: 0.74;
  }
  50% {
    transform: scale(1.08);
    opacity: 1;
  }
}

@keyframes entryDraftRing {
  to {
    transform: rotate(360deg);
  }
}

@media (max-width: 420px) {
  .entry-drafts__hero,
  .entry-drafts__panel,
  .entry-drafts__card {
    border-radius: 14px;
  }

  .entry-drafts__hero h1 {
    font-size: 28px;
  }

  .entry-drafts__actions {
    grid-template-columns: 1fr;
  }
}

@media (prefers-reduced-motion: reduce) {
  .entry-drafts__hero::after,
  .entry-drafts__empty-ring,
  .entry-drafts__card,
  .entry-drafts__status i {
    animation: none;
  }
}
</style>

