<template>
  <ReferencePageFrame
    module-number="13"
    title="权限与治理中心"
    :tags="['角色矩阵', '数据权限', '审计']"
    class="review-governance-center"
    data-testid="review-governance-center"
  >
    <template #actions>
      <el-button type="primary" :loading="loading" @click="load">刷新</el-button>
    </template>

    <section class="stat-grid">
      <article class="stat-card">
        <div class="stat-label">当前角色</div>
        <div class="stat-value">{{ roleLabel }}</div>
      </article>
      <article class="stat-card">
        <div class="stat-label">数据范围</div>
        <div class="stat-value">{{ scopeLabel }}</div>
      </article>
      <article class="stat-card">
        <div class="stat-label">审阅权限</div>
        <div class="stat-value">{{ auth.canAccessReviewSurface ? '开启' : '关闭' }}</div>
      </article>
      <article class="stat-card">
        <div class="stat-label">配置权限</div>
        <div class="stat-value">{{ auth.canAccessDesktopConfig ? '开启' : '关闭' }}</div>
      </article>
    </section>

    <el-card class="panel">
      <template #header>能力矩阵</template>
      <el-table :data="permissionRows" stripe>
        <el-table-column prop="label" label="能力" min-width="170" />
        <el-table-column prop="scope" label="生效范围" min-width="180" />
        <el-table-column label="状态" width="120">
          <template #default="{ row }">
            <el-tag :type="row.enabled ? 'success' : 'info'" effect="light">
              {{ row.enabled ? '可用' : '不可用' }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card v-if="roleDistribution.length" class="panel">
      <template #header>账号分布</template>
      <el-table :data="roleDistribution" stripe>
        <el-table-column prop="role" label="角色" min-width="180" />
        <el-table-column prop="count" label="数量" width="120" align="right" />
      </el-table>
    </el-card>
  </ReferencePageFrame>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

import ReferencePageFrame from '../../components/reference/ReferencePageFrame.vue'
import { fetchUsersPage } from '../../api/users'
import { useAuthStore } from '../../stores/auth'
import { formatRoleLabel } from '../../utils/display'

const auth = useAuthStore()
const loading = ref(false)
const roleDistribution = ref([])

const roleLabel = computed(() => formatRoleLabel(auth.role || 'unknown'))

const scopeLabel = computed(() => {
  const scope = String(auth.dataScopeType || '').trim()
  if (!scope) return '--'
  if (scope === 'all') return '全局'
  if (scope === 'self_workshop') return '本车间'
  if (scope === 'self_team') return '本班组'
  return scope
})

const permissionRows = computed(() => [
  { label: '厂级看板', scope: '审阅域', enabled: auth.canAccessFactoryDashboard },
  { label: '车间看板', scope: '审阅域', enabled: auth.canAccessWorkshopDashboard },
  { label: '数据接入', scope: '运营域', enabled: auth.canAccessReviewDesk },
  { label: '质量告警', scope: '运营域', enabled: auth.canAccessReviewDesk },
  { label: '成本核算', scope: '经营域', enabled: auth.canAccessReviewSurface },
  { label: '系统可观测', scope: '运行域', enabled: auth.canAccessReviewSurface },
  { label: '未来迭代', scope: '路线图', enabled: auth.canAccessReviewSurface },
  { label: '字段映射', scope: '配置域', enabled: auth.canAccessDesktopConfig },
  { label: '用户管理', scope: '配置域', enabled: auth.isAdmin },
])

function buildRoleDistribution(items = []) {
  const counters = new Map()
  for (const item of items) {
    const role = formatRoleLabel(item.role || 'unknown')
    counters.set(role, (counters.get(role) || 0) + 1)
  }
  return Array.from(counters.entries())
    .sort((a, b) => b[1] - a[1])
    .map(([role, count]) => ({ role, count }))
}

async function load() {
  if (!auth.isAdmin) {
    roleDistribution.value = []
    return
  }
  loading.value = true
  try {
    const page = await fetchUsersPage({ limit: 300, skip: 0 })
    roleDistribution.value = buildRoleDistribution(page.items || [])
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.review-governance-center__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 14px 16px;
}

.review-governance-center__header h1 {
  margin: 0;
  font-size: 26px;
  line-height: 1.15;
  color: var(--app-text);
}
</style>
