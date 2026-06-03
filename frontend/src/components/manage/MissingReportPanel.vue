<template>
  <section
    class="xt-missing-report"
    :class="{ 'xt-missing-report--compact': compact }"
    data-testid="missing-report-panel"
  >
    <header class="xt-missing-report__head">
      <div>
        <span>缺报追踪</span>
        <h2>{{ title }}</h2>
      </div>
      <strong>
        {{ summary.total }}
        <small v-if="compact">待补录</small>
      </strong>
    </header>
    <div class="xt-missing-report__stats">
      <template v-if="compact">
        <b v-for="item in compactRoleStats" :key="item.label">{{ item.label }} {{ item.count }}</b>
      </template>
      <template v-else>
        <b>{{ summary.workshopCount }} 车间</b>
        <b>{{ summary.shiftCount }} 班次</b>
        <b>{{ summary.roleCount }} 岗位</b>
      </template>
    </div>
    <div v-if="compact" class="xt-missing-report__chips" aria-label="缺报明细">
      <span v-if="loading" class="xt-missing-report__chip is-muted">加载中...</span>
      <span v-else-if="rows.length === 0" class="xt-missing-report__chip is-muted">暂无缺报</span>
      <template v-else>
        <span v-for="row in compactRows" :key="row.key" class="xt-missing-report__chip">
          <b>{{ row.workshopName }}</b>
          <em>{{ row.machineName }}</em>
          <i>{{ row.shiftName }} · {{ row.roleLabel }}</i>
          <small>{{ row.ownerName }} · {{ row.statusText }}</small>
        </span>
      </template>
    </div>
    <div v-else class="xt-missing-report__table">
      <table>
        <thead>
          <tr>
            <th>车间</th>
            <th>机列</th>
            <th>班次</th>
            <th>责任岗位</th>
            <th>责任人</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading">
            <td colspan="6">加载中...</td>
          </tr>
          <tr v-else-if="rows.length === 0">
            <td colspan="6">暂无缺报</td>
          </tr>
          <template v-else>
            <tr v-for="row in rows" :key="row.key">
              <td>{{ row.workshopName }}</td>
              <td><strong>{{ row.machineName }}</strong></td>
              <td>{{ row.shiftName }}</td>
              <td>{{ row.roleLabel }}</td>
              <td>{{ row.ownerName }}</td>
              <td><span>{{ row.statusText }}</span></td>
            </tr>
          </template>
        </tbody>
      </table>
    </div>
  </section>
</template>

<script setup>
import { computed } from 'vue'
import { summarizeMissingReportRows } from '../../utils/missingReportRows.js'

const props = defineProps({
  title: { type: String, default: '缺报明细' },
  rows: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  compact: { type: Boolean, default: false },
})

const summary = computed(() => summarizeMissingReportRows(props.rows))
const compactRows = computed(() => props.rows.slice(0, 3))
const compactRoleStats = computed(() => [
  { label: '主操', count: summary.value.roleBuckets?.operator || 0 },
  { label: '电工', count: summary.value.roleBuckets?.electrician || 0 },
  { label: '内勤', count: summary.value.roleBuckets?.owner || 0 },
])
</script>

<style scoped>
.xt-missing-report {
  position: relative;
  display: grid;
  gap: 8px;
  padding: 12px;
  border: 1px solid color-mix(in srgb, var(--xt-danger, #ff5d73) 24%, var(--xt-border-ink, rgba(125, 211, 252, 0.2)));
  border-radius: var(--xt-radius-xl, 18px);
  background:
    linear-gradient(135deg, color-mix(in srgb, var(--xt-danger, #ff5d73) 12%, transparent), transparent 48%),
    color-mix(in srgb, var(--xt-bg-ink-panel, #071b31) 86%, transparent);
  color: var(--xt-text-inverse, #e5f7ff);
  overflow: hidden;
}

.xt-missing-report::before {
  position: absolute;
  inset: 0;
  pointer-events: none;
  content: '';
  background: linear-gradient(90deg, transparent, rgba(255, 93, 115, 0.12), transparent);
  transform: translateX(-100%);
  animation: xtMissingSweep 7s ease-in-out infinite;
}

.xt-missing-report__head,
.xt-missing-report__stats,
.xt-missing-report__table,
.xt-missing-report__chips {
  position: relative;
  z-index: 1;
}

.xt-missing-report__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.xt-missing-report__head span {
  color: color-mix(in srgb, var(--xt-text-inverse, #e5f7ff) 62%, transparent);
  font-size: 12px;
  font-weight: 900;
  letter-spacing: 0.12em;
}

.xt-missing-report__head h2 {
  margin: 2px 0 0;
  font-size: 16px;
}

.xt-missing-report__head strong {
  display: inline-flex;
  flex-direction: column;
  align-items: flex-end;
  color: var(--xt-danger, #ff5d73);
  font-family: var(--xt-font-display, inherit);
  font-size: 24px;
  line-height: 1;
}

.xt-missing-report__head strong small {
  margin-top: 2px;
  color: color-mix(in srgb, var(--xt-text-inverse, #e5f7ff) 58%, transparent);
  font-size: 10px;
  font-weight: 800;
  letter-spacing: 0.06em;
}

.xt-missing-report__stats {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.xt-missing-report__stats b {
  padding: 4px 8px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.06);
  color: color-mix(in srgb, var(--xt-text-inverse, #e5f7ff) 76%, transparent);
  font-size: 12px;
}

.xt-missing-report__table {
  overflow-x: auto;
  max-height: 220px;
  overflow-y: auto;
}

.xt-missing-report table {
  width: 100%;
  min-width: 560px;
  border-collapse: collapse;
}

.xt-missing-report th,
.xt-missing-report td {
  padding: 7px 8px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  text-align: left;
  white-space: nowrap;
}

.xt-missing-report th {
  color: color-mix(in srgb, var(--xt-text-inverse, #e5f7ff) 58%, transparent);
  font-size: 12px;
}

.xt-missing-report td {
  color: color-mix(in srgb, var(--xt-text-inverse, #e5f7ff) 84%, transparent);
  font-size: 12px;
}

.xt-missing-report td span {
  display: inline-flex;
  padding: 4px 8px;
  border-radius: 999px;
  background: color-mix(in srgb, var(--xt-danger, #ff5d73) 16%, transparent);
  color: var(--xt-danger, #ff5d73);
  font-weight: 800;
}

.xt-missing-report--compact {
  grid-template-columns: auto auto minmax(0, 1fr);
  align-items: center;
  gap: 5px;
  padding: 5px 7px;
  border-radius: var(--xt-radius-md, 12px);
}

.xt-missing-report--compact .xt-missing-report__head {
  gap: 6px;
}

.xt-missing-report--compact .xt-missing-report__head h2 {
  margin-top: 0;
  font-size: 12px;
  white-space: nowrap;
}

.xt-missing-report--compact .xt-missing-report__head strong {
  font-family: var(--xt-font-mono, ui-monospace, monospace);
  font-size: 17px;
}

.xt-missing-report--compact .xt-missing-report__head span {
  display: none;
}

.xt-missing-report--compact .xt-missing-report__stats b {
  padding: 2px 5px;
  font-size: 10px;
}

.xt-missing-report--compact .xt-missing-report__stats {
  justify-content: flex-start;
  gap: 4px;
  flex-wrap: nowrap;
}

.xt-missing-report__chips {
  display: flex;
  gap: 6px;
  min-width: 0;
  overflow-x: auto;
  scrollbar-width: none;
}

.xt-missing-report__chips::-webkit-scrollbar {
  display: none;
}

.xt-missing-report__chip {
  display: inline-flex;
  flex: 0 0 auto;
  align-items: center;
  gap: 6px;
  max-width: 300px;
  padding: 4px 7px;
  border: 1px solid rgba(255, 93, 115, 0.22);
  border-radius: 999px;
  background: rgba(255, 93, 115, 0.08);
  color: color-mix(in srgb, var(--xt-text-inverse, #e5f7ff) 84%, transparent);
  font-size: 11px;
  white-space: nowrap;
}

.xt-missing-report__chip b,
.xt-missing-report__chip em,
.xt-missing-report__chip i,
.xt-missing-report__chip small {
  overflow: hidden;
  text-overflow: ellipsis;
}

.xt-missing-report__chip b {
  color: var(--xt-danger, #ff5d73);
  font-weight: 900;
}

.xt-missing-report__chip em,
.xt-missing-report__chip i,
.xt-missing-report__chip small {
  font-style: normal;
}

.xt-missing-report__chip.is-muted {
  color: color-mix(in srgb, var(--xt-text-inverse, #e5f7ff) 62%, transparent);
  border-color: rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.05);
}

@media (max-width: 760px) {
  .xt-missing-report--compact {
    grid-template-columns: 1fr;
  }

  .xt-missing-report--compact .xt-missing-report__stats {
    overflow-x: auto;
  }
}

@keyframes xtMissingSweep {
  0% { transform: translateX(-100%); }
  55% { transform: translateX(100%); }
  100% { transform: translateX(100%); }
}
</style>
