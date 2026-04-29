<template>
  <div class="mobile-shell" data-testid="entry-drafts-page">
    <div class="mobile-top">
      <div>
        <h1>草稿箱</h1>
        <p>只保留本机暂存内容，恢复后继续提交。</p>
      </div>
      <el-button plain class="mobile-inline-action" @click="loadDrafts">刷新</el-button>
    </div>

    <section class="panel mobile-card">
      <div v-if="!drafts.length" class="template-empty">暂无草稿</div>

      <div v-else class="mobile-history-list">
        <article v-for="item in drafts" :key="item.key" class="mobile-history-item">
          <div class="mobile-history-main">
            <div>
              <div class="mobile-history-title">{{ item.summary }}</div>
              <div class="note">{{ item.savedAtLabel }}</div>
            </div>
            <el-tag type="warning" effect="light">未提交</el-tag>
          </div>
          <div class="header-actions">
            <el-button type="primary" plain @click="resumeDraft(item)">继续填写</el-button>
            <el-button type="danger" plain @click="removeDraft(item.key)">删除</el-button>
          </div>
        </article>
      </div>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRouter } from 'vue-router'

const router = useRouter()
const drafts = ref([])

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
    name: 'mobile-report-form-advanced',
    params: {
      businessDate: item.businessDate,
      shiftId: item.shiftId
    }
  })
}

onMounted(loadDrafts)
</script>

