<template>
  <main class="team-worker-detail" data-testid="team-lead-worker-detail" v-loading="loading">
    <header class="team-worker-detail__head">
      <RouterLink to="/team-lead">返回</RouterLink>
      <strong>{{ title }}</strong>
    </header>

    <section v-if="detail" class="team-worker-detail__panel">
      <article>
        <span>工号</span>
        <strong>{{ detail.result.employee_no || '-' }}</strong>
      </article>
      <article>
        <span>姓名</span>
        <strong>{{ detail.result.employee_name || '-' }}</strong>
      </article>
      <article>
        <span>日期</span>
        <strong>{{ detail.result.business_date || businessDate }}</strong>
      </article>
      <article>
        <span>状态</span>
        <strong>{{ statusLabel }}</strong>
      </article>
      <article>
        <span>上班</span>
        <strong>{{ detail.result.check_in_time || '-' }}</strong>
      </article>
      <article>
        <span>下班</span>
        <strong>{{ detail.result.check_out_time || '-' }}</strong>
      </article>
    </section>

    <section v-else-if="error" class="team-worker-detail__empty">{{ error }}</section>
  </main>
</template>

<script setup>
import { computed, ref } from 'vue'
import { useRoute } from 'vue-router'

import { fetchAttendanceDetail } from '../../api/attendance'
import { formatStatusLabel } from '../../utils/display'

const route = useRoute()
const loading = ref(false)
const error = ref('')
const detail = ref(null)

const employeeId = computed(() => Number(route.params.employeeId))
const businessDate = computed(() => String(route.params.businessDate || ''))
const title = computed(() => detail.value?.result?.employee_name || `员工${employeeId.value}`)
const statusLabel = computed(() => formatStatusLabel(detail.value?.result?.attendance_status))

async function loadDetail() {
  loading.value = true
  error.value = ''
  try {
    detail.value = await fetchAttendanceDetail(employeeId.value, businessDate.value)
  } catch {
    detail.value = null
    error.value = '加载失败'
  } finally {
    loading.value = false
  }
}

loadDetail()
</script>

<style scoped>
.team-worker-detail {
  display: grid;
  gap: 12px;
  min-height: 100vh;
  padding: 14px;
  background: var(--xt-bg-shell);
}

.team-worker-detail__head {
  display: flex;
  align-items: center;
  gap: 12px;
  min-height: 52px;
}

.team-worker-detail__head a {
  color: var(--xt-text-secondary);
  font-size: 13px;
  font-weight: 850;
  text-decoration: none;
}

.team-worker-detail__head strong {
  color: var(--xt-text);
  font-size: 24px;
  font-weight: 900;
}

.team-worker-detail__panel {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.team-worker-detail__panel article,
.team-worker-detail__empty {
  display: grid;
  gap: 6px;
  min-width: 0;
  min-height: 88px;
  padding: 14px;
  border: 1px solid var(--xt-border-light);
  border-radius: 8px;
  background: var(--xt-bg-panel);
}

.team-worker-detail__panel span {
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-weight: 850;
}

.team-worker-detail__panel strong {
  color: var(--xt-text);
  font-size: 22px;
  font-weight: 900;
}

.team-worker-detail__empty {
  place-items: center;
  color: var(--xt-text-muted);
  font-size: 13px;
}

@media (max-width: 900px) {
  .team-worker-detail__panel {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
