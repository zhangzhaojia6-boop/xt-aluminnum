<template>
  <ReferencePageFrame
    module-number="14"
    title="管理控制台"
    :tags="['数据接入', '权限治理', '主数据模板', '系统运维']"
    data-testid="admin-home"
  >
    <section class="admin-home__grid">
      <ReferenceModuleCard
        v-for="item in modules"
        :key="item.number"
        :module-number="item.number"
        :title="item.title"
        density="dense"
      >
        <div class="admin-home__card">
          <ReferenceStatusTag :status="item.status" :label="item.statusLabel" />
          <el-button link type="primary" @click="go(item.routeName)">进入</el-button>
        </div>
      </ReferenceModuleCard>
    </section>
  </ReferencePageFrame>
</template>

<script setup>
import { useRouter } from 'vue-router'

import ReferenceModuleCard from '../../components/reference/ReferenceModuleCard.vue'
import ReferencePageFrame from '../../components/reference/ReferencePageFrame.vue'
import ReferenceStatusTag from '../../components/reference/ReferenceStatusTag.vue'

const router = useRouter()

const modules = [
  { number: '06', title: '数据接入与字段映射中心', routeName: 'admin-ingestion-center', status: 'warning', statusLabel: '改造中' },
  { number: '12', title: '系统运维与可观测', routeName: 'admin-ops-reliability', status: 'success', statusLabel: '在线' },
  { number: '13', title: '权限治理中心', routeName: 'admin-governance-center', status: 'success', statusLabel: '可配置' },
  { number: '14', title: '主数据与模板中心', routeName: 'admin-template-center', status: 'success', statusLabel: '可配置' },
  { number: '16', title: '路线图与下一步', routeName: 'admin-roadmap-center', status: 'pending', statusLabel: '排期中' }
]

function go(routeName) {
  router.push({ name: routeName })
}
</script>

<style scoped>
.admin-home__grid {
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(3, minmax(0, 1fr));
}

.admin-home__card {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: center;
}

@media (max-width: 960px) {
  .admin-home__grid {
    grid-template-columns: 1fr;
  }
}
</style>
