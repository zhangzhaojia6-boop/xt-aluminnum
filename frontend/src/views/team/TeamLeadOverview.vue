<template>
  <section class="team-lead-overview" :class="`is-${health}`" data-testid="team-lead-overview">
    <div class="team-lead-overview__metrics">
      <article v-for="item in metricItems" :key="item.key" class="team-lead-overview__metric">
        <span>{{ item.label }}</span>
        <strong>{{ item.value }}</strong>
      </article>
    </div>

    <div class="team-lead-overview__grid">
      <section class="team-lead-overview__panel is-pending">
        <header><span>待补齐</span><strong>{{ pendingTotal }}</strong></header>
        <div v-if="loading" class="team-lead-overview__state">加载中</div>
        <ul v-else-if="payload.pending_list?.length">
          <li v-for="item in payload.pending_list" :key="`${item.workshop}-${item.shift}-${item.team}`">
            <RouterLink class="team-lead-overview__pending-link" :to="pendingRoute(item)">
              <strong>{{ item.workshop }} · {{ item.shift }} · {{ item.team }}</strong>
              <span>{{ item.members.join('、') }}</span>
            </RouterLink>
          </li>
        </ul>
        <div v-else class="team-lead-overview__state">已清</div>
      </section>

      <section class="team-lead-overview__panel is-returned">
        <header><span>退回</span><strong>{{ payload.returned_count || 0 }}</strong></header>
        <div v-if="loading" class="team-lead-overview__state">加载中</div>
        <ul v-else-if="payload.returned_list?.length">
          <li v-for="item in payload.returned_list" :key="item.report_id">
            <strong>#{{ item.report_id }} {{ item.member }}</strong>
            <span>{{ item.returned_reason }}</span>
          </li>
        </ul>
        <div v-else class="team-lead-overview__state">已清</div>
      </section>

      <section class="team-lead-overview__panel is-reminder">
        <header><span>催报</span><strong>{{ payload.reminder_count || 0 }}</strong></header>
        <div v-if="loading" class="team-lead-overview__state">加载中</div>
        <ul v-else-if="payload.reminder_list?.length">
          <li v-for="item in payload.reminder_list" :key="`${item.shift}-${item.last_at}`">
            <strong>{{ item.shift }}</strong>
            <span>{{ item.count }} 次</span>
          </li>
        </ul>
        <div v-else class="team-lead-overview__state">已清</div>
      </section>

      <section class="team-lead-overview__panel is-health">
        <header><span>健康度</span><strong>{{ healthLabel }}</strong></header>
        <div class="team-lead-overview__health">
          <span>{{ payload.escalation_count || 0 }}</span>
          <strong>升级</strong>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  payload: { type: Object, required: true },
  loading: { type: Boolean, default: false }
})

const metricItems = computed(() => [
  { key: 'scheduled_count', label: '排班', value: props.payload.scheduled_count || 0 },
  { key: 'attended_count', label: '出勤', value: props.payload.attended_count || 0 },
  { key: 'reported_count', label: '已报', value: props.payload.reported_count || 0 },
  { key: 'returned_count', label: '退回', value: props.payload.returned_count || 0 },
  { key: 'reminder_count', label: '催报', value: props.payload.reminder_count || 0 }
])
const pendingTotal = computed(() => {
  return (props.payload.pending_list || []).reduce((total, item) => total + (item.members?.length || 0), 0)
})
const health = computed(() => props.payload.shift_health || 'green')
const healthLabel = computed(() => {
  if (health.value === 'red') return '红'
  if (health.value === 'yellow') return '黄'
  return '绿'
})

function pendingRoute(item) {
  if (item?.business_date && item?.shift_id) {
    return `/entry/report/${item.business_date}/${item.shift_id}`
  }
  return '/entry'
}
</script>

<style scoped>
.team-lead-overview {
  display: grid;
  gap: 12px;
  min-height: 0;
}

.team-lead-overview__metrics {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  gap: 10px;
}

.team-lead-overview__metric,
.team-lead-overview__panel {
  min-width: 0;
  border: 1px solid var(--xt-border-light);
  border-radius: 8px;
  background: var(--xt-bg-panel);
  box-shadow: var(--xt-shadow-sm);
}

.team-lead-overview__metric {
  display: grid;
  gap: 6px;
  min-height: 84px;
  padding: 14px;
}

.team-lead-overview__metric span,
.team-lead-overview__panel header span {
  color: var(--xt-text-secondary);
  font-size: 12px;
  font-weight: 850;
}

.team-lead-overview__metric strong {
  color: var(--xt-text);
  font-size: 30px;
  font-weight: 900;
  line-height: 1;
}

.team-lead-overview__grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  min-height: 0;
}

.team-lead-overview__panel {
  display: grid;
  grid-template-rows: auto minmax(0, 1fr);
  min-height: 330px;
  overflow: hidden;
}

.team-lead-overview__panel header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 12px 14px;
  border-bottom: 1px solid var(--xt-border-light);
}

.team-lead-overview__panel header strong {
  color: var(--xt-text);
  font-size: 20px;
  font-weight: 900;
}

.team-lead-overview__panel ul {
  display: grid;
  align-content: start;
  gap: 8px;
  min-height: 0;
  margin: 0;
  padding: 10px;
  overflow: auto;
  list-style: none;
}

.team-lead-overview__panel li {
  display: grid;
  gap: 4px;
  padding: 9px;
  border-radius: 8px;
  background: var(--xt-bg-panel-soft);
}

.team-lead-overview__pending-link {
  display: grid;
  gap: 4px;
  color: inherit;
  text-decoration: none;
}

.team-lead-overview__panel li strong {
  color: var(--xt-text);
  font-size: 13px;
}

.team-lead-overview__panel li span,
.team-lead-overview__state {
  color: var(--xt-text-muted);
  font-size: 12px;
  line-height: 1.45;
}

.team-lead-overview__state,
.team-lead-overview__health {
  display: grid;
  place-items: center;
  min-height: 100%;
}

.team-lead-overview__health span {
  color: var(--xt-text);
  font-size: 52px;
  font-weight: 900;
  line-height: 1;
}

.team-lead-overview__health strong {
  color: var(--xt-text-secondary);
  font-size: 13px;
}

.team-lead-overview.is-yellow .is-health {
  border-color: rgba(180, 83, 9, 0.35);
}

.team-lead-overview.is-red .is-health {
  border-color: rgba(185, 28, 28, 0.4);
}

@media (max-width: 900px) {
  .team-lead-overview__metrics,
  .team-lead-overview__grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
