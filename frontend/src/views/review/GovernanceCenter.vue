<template>
  <section class="page-stack governance-command" data-testid="review-governance-center">
    <header class="governance-command__hero">
      <div class="governance-command__hero-copy">
        <span class="governance-command__eyebrow">ACCESS GOVERNANCE</span>
        <h1>权限与治理中心</h1>
      </div>
      <el-button class="governance-command__refresh" :loading="loading" @click="load">刷新</el-button>
    </header>

    <section class="governance-command__stats" data-testid="governance-center-stats">
      <article
        v-for="item in statusCards"
        :key="item.key"
        class="governance-command__stat"
        :class="`governance-command__stat--${item.accent}`"
      >
        <div class="governance-command__stat-top">
          <span class="governance-command__led"></span>
          <span>{{ item.label }}</span>
        </div>
        <strong>{{ item.value }}</strong>
        <small>{{ item.unit }}</small>
      </article>
    </section>

    <section class="governance-command__grid">
      <article class="governance-command__panel governance-command__panel--matrix">
        <div class="governance-command__panel-head">
          <div>
            <span class="governance-command__eyebrow">CAPABILITY MATRIX</span>
            <h2>能力矩阵</h2>
          </div>
          <span class="governance-command__panel-chip">{{ enabledPermissionCount }} / {{ permissionRows.length }} 可用</span>
        </div>

        <div class="governance-command__table" data-testid="governance-center-permission-table">
          <el-table :data="permissionRows" stripe>
            <el-table-column prop="label" label="能力" min-width="170" />
            <el-table-column prop="scope" label="生效范围" min-width="180" />
            <el-table-column label="状态" width="120">
              <template #default="{ row }">
                <span class="governance-command__status" :data-status="row.enabled ? 'enabled' : 'disabled'">
                  {{ row.enabled ? '可用' : '不可用' }}
                </span>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div class="governance-command__mobile-list" data-testid="governance-center-permission-mobile">
          <article v-for="row in permissionRows" :key="`${row.label}-${row.scope}`">
            <div>
              <strong>{{ row.label }}</strong>
              <small>{{ row.scope }}</small>
            </div>
            <span class="governance-command__status" :data-status="row.enabled ? 'enabled' : 'disabled'">
              {{ row.enabled ? '可用' : '不可用' }}
            </span>
          </article>
        </div>
      </article>

      <article class="governance-command__panel governance-command__panel--roles">
        <div class="governance-command__panel-head">
          <div>
            <span class="governance-command__eyebrow">ROLE DISTRIBUTION</span>
            <h2>账号分布</h2>
          </div>
          <span class="governance-command__panel-chip">{{ roleDistribution.length }} 类</span>
        </div>

        <div v-if="roleDistribution.length" class="governance-command__role-list" data-testid="governance-center-role-distribution">
          <div v-for="row in roleDistribution" :key="row.role" class="governance-command__role-row">
            <span>{{ row.role }}</span>
            <strong>{{ row.count }}</strong>
          </div>
        </div>
        <div v-else class="governance-command__empty" data-testid="governance-center-role-empty">当前账号无账号分布读取权限</div>
      </article>
    </section>
  </section>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'

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

const enabledPermissionCount = computed(() => permissionRows.value.filter((row) => row.enabled).length)

const statusCards = computed(() => [
  { key: 'role', label: '当前角色', value: roleLabel.value, unit: 'ROLE', accent: 'cyan' },
  { key: 'scope', label: '数据范围', value: scopeLabel.value, unit: 'SCOPE', accent: 'blue' },
  { key: 'review', label: '审阅权限', value: auth.canAccessReviewSurface ? '开启' : '关闭', unit: 'REVIEW', accent: auth.canAccessReviewSurface ? 'cyan' : 'amber' },
  { key: 'config', label: '配置权限', value: auth.canAccessDesktopConfig ? '开启' : '关闭', unit: 'CONFIG', accent: auth.canAccessDesktopConfig ? 'cyan' : 'amber' }
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
.governance-command {
  --governance-cyan: #00f2ff;
  --governance-amber: #ffab00;
  --governance-blue: #74f5ff;
  --governance-bg: #06101f;
  --governance-panel: rgba(12, 25, 42, 0.72);
  --governance-line: rgba(0, 242, 255, 0.18);
  --governance-muted: rgba(223, 226, 235, 0.66);
  color: #dfe2eb;
}

.governance-command::before {
  position: fixed;
  inset: 0;
  z-index: -1;
  pointer-events: none;
  content: '';
  background:
    radial-gradient(circle at 12% 8%, rgba(0, 242, 255, 0.12), transparent 30%),
    radial-gradient(circle at 82% 10%, rgba(116, 245, 255, 0.1), transparent 24%),
    linear-gradient(rgba(0, 242, 255, 0.035) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0, 242, 255, 0.035) 1px, transparent 1px),
    linear-gradient(135deg, #0a0e14, var(--governance-bg));
  background-size: auto, auto, 32px 32px, 32px 32px, auto;
}

.governance-command__hero,
.governance-command__panel,
.governance-command__stat,
.governance-command__mobile-list article,
.governance-command__role-row {
  position: relative;
  overflow: hidden;
  border: 1px solid var(--governance-line);
  background: linear-gradient(180deg, rgba(38, 42, 49, 0.54), var(--governance-panel));
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06), 0 20px 54px rgba(0, 0, 0, 0.22);
  backdrop-filter: blur(14px);
}

.governance-command__hero::after,
.governance-command__panel::after,
.governance-command__stat::after {
  position: absolute;
  inset: 0;
  pointer-events: none;
  content: '';
  background: linear-gradient(115deg, transparent 0%, rgba(0, 242, 255, 0.14) 42%, transparent 62%);
  transform: translateX(-120%);
  animation: governanceSweep 7s ease-in-out infinite;
}

.governance-command__hero {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  min-height: 156px;
  padding: 28px;
  border-radius: 18px;
}

.governance-command__hero-copy,
.governance-command__refresh,
.governance-command__panel-head,
.governance-command__table,
.governance-command__mobile-list,
.governance-command__role-list,
.governance-command__empty {
  position: relative;
  z-index: 1;
}

.governance-command__eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  color: var(--governance-cyan);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.16em;
}

.governance-command__eyebrow::before {
  width: 8px;
  height: 8px;
  content: '';
  border-radius: 999px;
  background: var(--governance-cyan);
  box-shadow: 0 0 18px var(--governance-cyan);
}

.governance-command h1,
.governance-command h2 {
  margin: 0;
  color: #f6fbff;
  font-family: 'Hanken Grotesk', 'Inter', sans-serif;
  letter-spacing: -0.03em;
}

.governance-command h1 {
  margin-top: 12px;
  font-size: clamp(34px, 5vw, 58px);
  line-height: 1;
  white-space: nowrap;
  text-shadow: 0 0 28px rgba(0, 242, 255, 0.22);
}

.governance-command h2 {
  margin-top: 8px;
  font-size: 24px;
}

.governance-command__refresh {
  min-width: 112px;
  border: 1px solid rgba(0, 242, 255, 0.32);
  border-radius: 12px;
  background: linear-gradient(135deg, rgba(0, 242, 255, 0.22), rgba(0, 118, 255, 0.32));
  color: #e1fdff;
  font-weight: 800;
  box-shadow: 0 0 26px rgba(0, 242, 255, 0.16);
}

.governance-command__stats {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.governance-command__stat {
  min-height: 132px;
  padding: 18px;
  border-radius: 16px;
}

.governance-command__stat-top {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--governance-muted);
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.08em;
}

.governance-command__led {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: var(--governance-cyan);
  box-shadow: 0 0 18px var(--governance-cyan);
  animation: governancePulse 2.2s ease-in-out infinite;
}

.governance-command__stat--amber .governance-command__led {
  background: var(--governance-amber);
  box-shadow: 0 0 18px var(--governance-amber);
}

.governance-command__stat--blue .governance-command__led {
  background: var(--governance-blue);
  box-shadow: 0 0 18px var(--governance-blue);
}

.governance-command__stat strong {
  position: relative;
  z-index: 1;
  display: block;
  margin-top: 18px;
  color: #f6fbff;
  font-family: 'Hanken Grotesk', 'Inter', sans-serif;
  font-size: clamp(26px, 3.2vw, 42px);
  line-height: 0.95;
  text-shadow: 0 0 24px rgba(0, 242, 255, 0.22);
}

.governance-command__stat small {
  position: relative;
  z-index: 1;
  display: block;
  margin-top: 8px;
  color: var(--governance-muted);
  font-weight: 700;
}

.governance-command__grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.65fr);
  gap: 16px;
}

.governance-command__panel {
  padding: 22px;
  border-radius: 18px;
}

.governance-command__panel-head {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 18px;
}

.governance-command__panel-chip {
  border: 1px solid rgba(0, 242, 255, 0.16);
  border-radius: 999px;
  padding: 6px 10px;
  color: var(--governance-muted);
  background: rgba(1, 16, 31, 0.62);
  font-size: 12px;
  font-weight: 700;
  white-space: nowrap;
}

.governance-command__table {
  overflow: hidden;
  border: 1px solid rgba(0, 242, 255, 0.12);
  border-radius: 14px;
}

.governance-command__table :deep(.el-table),
.governance-command__table :deep(.el-table tr),
.governance-command__table :deep(.el-table th.el-table__cell),
.governance-command__table :deep(.el-table td.el-table__cell) {
  background: transparent;
  color: #dfe2eb;
}

.governance-command__table :deep(.el-table th.el-table__cell) {
  color: rgba(225, 253, 255, 0.82);
  font-size: 12px;
  letter-spacing: 0.04em;
}

.governance-command__table :deep(.el-table--striped .el-table__body tr.el-table__row--striped td.el-table__cell) {
  background: rgba(0, 242, 255, 0.035);
}

.governance-command__table :deep(.el-table__body tr:hover > td.el-table__cell) {
  background: rgba(0, 242, 255, 0.08);
}

.governance-command__status {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 64px;
  border-radius: 999px;
  padding: 4px 9px;
  background: rgba(0, 242, 255, 0.14);
  color: #a7fff8;
  font-size: 12px;
  font-weight: 800;
  box-shadow: 0 0 14px rgba(0, 242, 255, 0.12);
}

.governance-command__status[data-status='disabled'] {
  background: rgba(255, 171, 0, 0.14);
  color: #ffe6aa;
  box-shadow: 0 0 16px rgba(255, 171, 0, 0.16);
}

.governance-command__role-list {
  display: grid;
  gap: 10px;
}

.governance-command__role-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-radius: 14px;
  padding: 14px;
}

.governance-command__role-row span {
  color: var(--governance-muted);
  font-weight: 800;
}

.governance-command__role-row strong {
  color: #f6fbff;
  font-family: 'Hanken Grotesk', 'Inter', sans-serif;
  font-size: 28px;
}

.governance-command__empty {
  border: 1px dashed rgba(0, 242, 255, 0.2);
  border-radius: 14px;
  padding: 20px;
  color: var(--governance-muted);
  background: rgba(1, 16, 31, 0.48);
}

.governance-command__mobile-list {
  display: none;
}

.governance-command__mobile-list article {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  border-radius: 16px;
  padding: 16px;
}

.governance-command__mobile-list strong {
  display: block;
  color: #f6fbff;
  font-family: 'Hanken Grotesk', 'Inter', sans-serif;
  font-size: 18px;
}

.governance-command__mobile-list small {
  display: block;
  margin-top: 4px;
  color: var(--governance-muted);
}

@keyframes governanceSweep {
  0% { transform: translateX(-120%); opacity: 0; }
  42% { opacity: 1; }
  100% { transform: translateX(120%); opacity: 0; }
}

@keyframes governancePulse {
  0%, 100% { transform: scale(1); opacity: 0.72; }
  50% { transform: scale(1.22); opacity: 1; }
}

@media (max-width: 1180px) {
  .governance-command__stats {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .governance-command__grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 720px) {
  .governance-command__hero,
  .governance-command__panel-head {
    align-items: stretch;
    flex-direction: column;
  }

  .governance-command h1 {
    white-space: normal;
  }

  .governance-command__refresh {
    width: 100%;
  }

  .governance-command__stats {
    grid-template-columns: 1fr;
  }

  .governance-command__panel {
    padding: 16px;
  }

  .governance-command__table {
    display: none;
  }

  .governance-command__mobile-list {
    display: grid;
    gap: 12px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .governance-command__hero::after,
  .governance-command__panel::after,
  .governance-command__stat::after,
  .governance-command__led {
    animation: none;
  }
}
</style>
